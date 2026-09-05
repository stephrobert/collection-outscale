"""Télécharge le contrat OpenAPI d'Outscale, et le versionne tel quel.

Outscale publie son contrat dans le dépôt `outscale/osc-api`, un seul fichier
`outscale.yaml` à la racine, tagué sans préfixe `v` (`1.42.0`), sans asset de
release : le fichier se prend sur le tag. C'est la forme que le SDK Python
officiel télécharge lui-même (`.github/scripts/release-build.sh`), et c'est
le contrat canonique : `outscale/osc-api-deploy` en est un dérivé qui applique
des retouches pour les générateurs de SDK, et son README renvoie vers
`osc-api` pour l'original.

Le document est versionné octet pour octet, sans reformatage : c'est ce qui
permet à `git diff` de dire exactement ce qu'Outscale a changé.

    python scripts/sync_specs.py               # le tag épinglé ci-dessous
    python scripts/sync_specs.py --tag 1.43.0  # un autre tag, pour trier une dérive

**Le tag est épinglé, et c'est délibéré.** Le SDK installé embarque sa propre
copie du contrat et refuse une action ou un paramètre que sa copie ne connaît
pas ; sa version suit celle du contrat (0.42.0 embarque 1.42.0). Suivre le
dernier tag sans suivre le SDK ferait générer un module que le SDK refuserait.
La dérive se mesure donc en deux temps : `--tag <dernier>` pour voir ce qui a
bougé, puis relever les deux ensemble.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_ROOT = ROOT / "specs" / "outscale"

#: Le tag du contrat que ce dépôt suit. Relevé avec le SDK, jamais seul.
PINNED_TAG = "1.42.0"
SOURCE_URL = "https://raw.githubusercontent.com/outscale/osc-api/refs/tags/{tag}/outscale.yaml"
VERSION = "v1"
TIMEOUT_SECONDS = 60


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "outscale-ansible-generator"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise SystemExit(f"{url} : HTTP {response.status}")
        payload: bytes = response.read()
        return payload


def main(argv: list[str]) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--tag", default=PINNED_TAG, help=f"tag d'osc-api (défaut : {PINNED_TAG})")
    arguments = parseur.parse_args(argv[1:])
    url = SOURCE_URL.format(tag=arguments.tag)
    target = SPEC_ROOT / f"outscale.{VERSION}.yml"
    try:
        payload = download(url)
    except (urllib.error.URLError, urllib.error.HTTPError) as error:
        # Un échec ne laisse jamais un fichier périmé passer pour un contrat à jour.
        print(f"échec : {url} : {error}", file=sys.stderr)
        return 1
    previous = target.read_bytes() if target.is_file() else b""
    target.write_bytes(payload)
    etat = "inchangé" if payload == previous else "mis à jour"
    print(f"{target.relative_to(ROOT)} : {len(payload)} octets, tag {arguments.tag}, {etat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
