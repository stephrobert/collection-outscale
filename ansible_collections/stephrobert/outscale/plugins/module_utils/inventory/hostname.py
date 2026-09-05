# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Le choix de `inventory_hostname`, et le refus des collisions.

Chez Outscale, le nom d'une machine est un tag (`Name`), et rien n'empêche
deux machines de porter le même : ni dans une sous-région, ni dans le compte.
Un inventaire qui l'ignore appelle `add_host` deux fois avec la même clé, et
la seconde machine **écrase** la première, ses variables et ses groupes. Sans
un mot.

Ce module rend ce cas impossible : le nom retenu est désambiguïsé de façon
déterministe, et la collision est signalée.
"""

from __future__ import annotations

from .models import InventoryHost

#: Préfixe qui lit un tag par sa clé : `tag:Name` lit `tags["Name"]`.
TAG_PREFIX = "tag:"

#: Les champs du modèle qu'une source de nom peut lire, et **rien d'autre**.
#: Sans cette table, une faute de frappe donnerait un inventaire vide.
SOURCES: tuple[str, ...] = ("name", "id", "public_ipv4", "private_ipv4")


def is_known_source(source: str) -> bool:
    """Vrai pour une source que `resolve_source` sait lire."""
    if source.startswith(TAG_PREFIX):
        return bool(source[len(TAG_PREFIX) :].strip())
    return source in SOURCES


def resolve_source(host: InventoryHost, source: str) -> str | None:
    """La valeur d'une source pour cette machine, ou `None` si elle manque."""
    if source.startswith(TAG_PREFIX):
        cle = source[len(TAG_PREFIX) :]
        valeur = str(host.tags.get(cle, "") or "").strip()
        return valeur or None

    if source not in SOURCES:
        return None
    valeur = getattr(host, source, None)
    if isinstance(valeur, tuple):
        return valeur[0] if valeur else None
    if isinstance(valeur, str):
        return valeur or None
    return None


def pick_hostname(host: InventoryHost, sources: tuple[str, ...]) -> tuple[str, str] | None:
    """Le premier nom disponible, avec la source qui l'a fourni."""
    for source in sources:
        valeur = resolve_source(host, source)
        if valeur:
            return valeur, source
    return None


def assign_hostnames(
    hosts: tuple[InventoryHost, ...],
    sources: tuple[str, ...],
) -> tuple[tuple[tuple[InventoryHost, str], ...], tuple[str, ...]]:
    """Attribue un nom unique à chaque machine, et dit ce qu'il a fallu faire.

    La désambiguïsation est déterministe et documentée : au premier conflit,
    la région est ajoutée ; si le conflit persiste, l'identifiant. Un
    identifiant Outscale étant unique, la boucle se termine toujours.

    Les machines sont traitées dans l'ordre reçu, et cet ordre est
    déterministe parce que les providers trient. Deux exécutions produisent
    donc le même inventaire, y compris les noms désambiguïsés.
    """
    attribues: list[tuple[InventoryHost, str]] = []
    avertissements: list[str] = []
    pris: set[str] = set()

    for host in hosts:
        choix = pick_hostname(host, sources)
        if choix is None:
            avertissements.append(
                f"{host.id} ({host.product}) : aucune des sources {list(sources)} "
                "ne donne de nom, machine écartée"
            )
            continue

        nom, source = choix
        if nom not in pris:
            pris.add(nom)
            attribues.append((host, nom))
            continue

        for suffixe in (host.region, host.id):
            if not suffixe:
                continue
            candidat = f"{nom}_{suffixe}"
            if candidat not in pris:
                pris.add(candidat)
                attribues.append((host, candidat))
                avertissements.append(
                    f"nom '{nom}' déjà pris (source {source}) : {host.id} devient '{candidat}'"
                )
                break
        else:  # pragma: no cover - un identifiant Outscale est unique
            avertissements.append(f"{host.id} : impossible de désambiguïser '{nom}', écartée")

    return tuple(attribues), tuple(avertissements)
