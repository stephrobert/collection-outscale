"""Construit l'archive de la collection, l'installe, et vérifie qu'elle sert.

Une archive qui existe ne prouve rien. Ce script fait les trois choses, dans
cet ordre, et la troisième est celle qui compte :

1. **construire** avec `ansible-galaxy collection build`, depuis la collection
   telle qu'elle est rangée dans `ansible_collections/<namespace>/<nom>/` ;
2. **contrôler le contenu** de l'archive. Le générateur, le contrat et les
   tests n'ont rien à faire chez un utilisateur, et une archive qui les
   emporte est une fuite, pas un détail de taille. Et l'inverse : tout ce que
   `plugins/` porte sur le disque doit être dans l'archive ;
3. **installer et interroger**. La preuve est qu'`ansible-doc` charge un
   module depuis la collection installée et rend sa documentation. Un fichier
   présent dans une archive n'est pas un module qu'Ansible sait charger.

**Aucun nom de module, de plugin ou de produit n'est écrit ici.** Ce script a
été transposé de `collection-scaleway`, où quatre contrôles en une journée ont
survécu au renommage de ce qu'ils contrôlaient parce qu'ils portaient un nom
en dur. Tout ce que ce script attend, il le lit sur le disque.

    python scripts/package.py
    python scripts/package.py --keep    # garder l'installation temporaire
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from generator.ansible.collection import Collection, load_collection

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "build" / "dist"

#: Ce qu'une archive livrée ne doit jamais contenir. La liste est celle des
#: répertoires du dépôt qui n'ont aucun sens chez un utilisateur.
FORBIDDEN: tuple[str, ...] = ("generator", "specs", "scripts", "tests", ".venv")

#: Ce que l'archive doit porter en plus des plugins : l'identité et les
#: métadonnées qu'Ansible et Galaxy lisent.
REQUIRED_METADATA: tuple[str, ...] = (
    "MANIFEST.json",
    "LICENSE",
    "CHANGELOG.rst",
    "changelogs/changelog.yaml",
    "meta/runtime.yml",
    "meta/execution-environment.yml",
    "meta/ee-requirements.txt",
)

#: Le paramètre commun que chaque module documente. Il vient du fragment de
#: documentation, et c'est lui qui prouve que le fragment a suivi l'archive.
COMMON_OPTION = "region"


class PackageError(RuntimeError):
    """L'archive n'a pas été produite, ou elle ne tient pas ses promesses."""


def executable(name: str) -> str:
    beside_python = Path(sys.executable).parent / name
    return str(beside_python) if beside_python.is_file() else name


def archive_name(collection: Collection) -> str:
    """`stephrobert-outscale-0.1.0.tar.gz`, le nom que Galaxy impose."""
    return f"{collection.namespace}-{collection.name}-{collection.version}.tar.gz"


def members(archive: Path) -> tuple[str, ...]:
    """Les fichiers que l'archive porte, triés. Les répertoires n'en sont pas."""
    with tarfile.open(archive, "r:gz") as tar:
        return tuple(sorted(member.name for member in tar.getmembers() if member.isfile()))


def entries(archive: Path) -> tuple[str, ...]:
    """**Tout** ce que l'archive porte, répertoires compris.

    La distinction n'est pas théorique : l'archive de Scaleway emportait un
    répertoire `tests/` vide, et le contrôle des fuites ne le voyait pas parce
    qu'il ne regardait que les fichiers. Un lecteur du tarball y lit pourtant
    que la collection livre ses tests, et le jour où un fichier s'y glisse,
    c'est le `build_ignore` qui décide seul.
    """
    with tarfile.open(archive, "r:gz") as tar:
        return tuple(sorted(member.name for member in tar.getmembers()))


def shipped_plugins(collection: Collection) -> tuple[str, ...]:
    """Tout ce que `plugins/` porte sur le disque, et que l'archive doit porter.

    Lu sur le disque plutôt que déclaré : un module renommé, un plugin ajouté
    ou une couche de `module_utils` nouvelle entrent dans le contrôle sans
    qu'on y pense, et c'est le point.
    """
    racine = collection.path / "plugins"
    return tuple(
        sorted(
            str(chemin.relative_to(collection.path))
            for chemin in racine.rglob("*.py")
            if "__pycache__" not in chemin.parts
        )
    )


def required_entries(collection: Collection) -> tuple[str, ...]:
    """Ce que l'archive doit contenir pour être autre chose qu'une coquille."""
    return (*REQUIRED_METADATA, *shipped_plugins(collection))


def leaks(all_entries: tuple[str, ...]) -> list[str]:
    """Les répertoires interdits que l'archive porte, fichiers **ou** répertoires.

    Fonction pure, pour que le cas du répertoire vide se teste sans archive.
    """
    return sorted(
        {chemin.split("/", 1)[0] for chemin in all_entries if chemin.split("/", 1)[0] in FORBIDDEN}
    )


def check_contents(archive: Path, collection: Collection) -> tuple[str, ...]:
    """Refuse une archive qui emporte le générateur, ou qui oublie un plugin.

    Les deux moitiés comptent : sans la seconde, une archive vide passerait
    tous les contrôles de la première.
    """
    contenu = members(archive)

    fuites = leaks(entries(archive))
    if fuites:
        raise PackageError(f"l'archive emporte ce qui doit rester au dépôt : {fuites}")

    manquants = [attendu for attendu in required_entries(collection) if attendu not in contenu]
    if manquants:
        raise PackageError(f"l'archive n'emporte pas {manquants}")

    return contenu


def modules_on_disk(collection: Collection) -> tuple[str, ...]:
    """Les modules livrés, par leur nom, lus dans `plugins/modules/`."""
    return tuple(
        sorted(
            chemin.stem
            for chemin in collection.modules_dir.glob("*.py")
            if not chemin.name.startswith("_")
        )
    )


def check_installed(collections_path: Path, collection: Collection, module: str) -> None:
    """Interroge un module depuis la collection installée.

    `ansible-doc` charge la collection comme Ansible le fera, et rend la
    documentation du module. C'est la seule preuve que l'archive sert.
    """
    fqcn = collection.module_fqcn(module)
    result = subprocess.run(
        [executable("ansible-doc"), "--json", fqcn],
        env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collections_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PackageError(
            f"`ansible-doc {fqcn}` a échoué depuis l'archive installée :\n{result.stderr}"
        )

    payload = json.loads(result.stdout or "{}")
    documentation = payload.get(fqcn, {}).get("doc", {})
    options = documentation.get("options", {})
    if COMMON_OPTION not in options:
        raise PackageError(
            f"{fqcn} installé ne documente pas {COMMON_OPTION!r} : le fragment de "
            f"documentation n'a pas suivi l'archive ({sorted(options)})"
        )
    courte = documentation.get("short_description")
    print(f"  {fqcn} : {len(options)} option(s), short_description « {courte} »")


def inventory_plugins(collection: Collection) -> tuple[str, ...]:
    """Les plugins d'inventaire livrés, lus sur le disque."""
    dossier = collection.path / "plugins" / "inventory"
    if not dossier.is_dir():
        return ()
    return tuple(sorted(f.stem for f in dossier.glob("*.py") if not f.stem.startswith("_")))


def check_inventory_plugin(collections_path: Path, collection: Collection, plugin: str) -> None:
    """Interroge un plugin d'inventaire depuis la collection installée.

    Un plugin d'inventaire est plus fragile qu'un module dans une archive : il
    dépend d'un paquet entier sous `module_utils/`, et un répertoire oublié au
    build ne se voit pas dans la liste des fichiers. `ansible-doc -t inventory`
    charge le plugin comme Ansible le fera, et un plugin sans option dit que
    l'archive porte le fichier sans porter le plugin.
    """
    fqcn = f"{collection.fqcn}.{plugin}"
    result = subprocess.run(
        [executable("ansible-doc"), "-t", "inventory", "--json", fqcn],
        env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collections_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise PackageError(
            f"`ansible-doc -t inventory {fqcn}` a échoué depuis l'archive installée :"
            f"\n{result.stderr}"
        )
    payload = json.loads(result.stdout or "{}")
    options = payload.get(fqcn, {}).get("doc", {}).get("options", {})
    if "plugin" not in options:
        raise PackageError(
            f"{fqcn} installé ne documente pas son option `plugin` : le fichier est dans "
            "l'archive, mais Ansible n'en voit pas la configuration"
        )
    print(f"  {fqcn} : plugin d'inventaire chargé, {len(options)} option(s)")


def check_playbooks(collections_path: Path, collection: Collection) -> None:
    """Vérifie que les playbooks livrés, s'il y en a, s'appellent par leur nom complet."""
    racine = collections_path / "ansible_collections" / collection.namespace / collection.name
    dossier = racine / "playbooks"
    if not dossier.is_dir():
        print("  aucun playbook livré")
        return
    noms = sorted(chemin.stem for chemin in dossier.glob("*.yml"))
    for nom in noms:
        fqcn = f"{collection.fqcn}.{nom}"
        result = subprocess.run(
            [executable("ansible-playbook"), "--list-tasks", fqcn],
            env={**os.environ, "ANSIBLE_COLLECTIONS_PATH": str(collections_path)},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise PackageError(f"`ansible-playbook {fqcn}` ne résout pas :\n{result.stderr}")
        print(f"  {fqcn} : résolu depuis la collection installée")


def main(argv: list[str]) -> int:
    collection = load_collection()
    modules = modules_on_disk(collection)
    if not modules:
        raise PackageError(
            f"aucun module dans {os.path.relpath(collection.modules_dir, ROOT)} : lancer "
            "`mise run generate`. Une archive sans module passerait tous les contrôles."
        )
    workdir = Path(tempfile.mkdtemp(prefix="outscale-package-"))

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    built = subprocess.run(
        [
            executable("ansible-galaxy"),
            "collection",
            "build",
            "--force",
            "--output-path",
            str(DIST_DIR),
            str(collection.path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if built.returncode != 0:
        print(built.stdout + built.stderr, file=sys.stderr)
        raise PackageError("ansible-galaxy n'a pas construit l'archive")

    archive = DIST_DIR / archive_name(collection)
    if not archive.is_file():
        raise PackageError(f"archive attendue et absente : {archive}")

    contenu = check_contents(archive, collection)
    taille = archive.stat().st_size
    print(f"{os.path.relpath(archive, ROOT)} : {len(contenu)} fichier(s), {taille // 1024} Kio")

    installation = workdir / "installed"
    installed = subprocess.run(
        [
            executable("ansible-galaxy"),
            "collection",
            "install",
            str(archive),
            "--force",
            "-p",
            str(installation),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if installed.returncode != 0:
        print(installed.stdout + installed.stderr, file=sys.stderr)
        raise PackageError("l'archive ne s'installe pas")

    print(f"installée dans {installation}")
    # Le premier module du disque, et pas un nom écrit ici : un module renommé
    # ne doit pas faire accuser l'archive.
    check_installed(installation, collection, modules[0])
    for plugin in inventory_plugins(collection):
        check_inventory_plugin(installation, collection, plugin)
    check_playbooks(installation, collection)

    print(
        "\npour l'installer chez soi :\n"
        f"  ansible-galaxy collection install {os.path.relpath(archive, ROOT)}"
    )

    if "--keep" not in argv[1:]:
        subprocess.run(["rm", "-rf", str(workdir)], check=False)
    else:
        print(f"\ninstallation conservée : {installation}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except PackageError as error:
        print(f"erreur : {error}", file=sys.stderr)
        raise SystemExit(1) from error
