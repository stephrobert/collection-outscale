"""Le changelog se compose avec l'`ansible-doc` de ce dépôt, pas celui du PATH."""

from __future__ import annotations

import changelog


def test_la_composition_nomme_lansible_doc_a_cote_de_linterpreteur() -> None:
    """Mesuré : le PATH d'une session ouverte ailleurs portait un autre venv."""
    command = changelog.commande(
        ["changelog.py", "release", "--version", "0.1.0"], "/venv/bin/python"
    )
    assert command[:3] == ["/venv/bin/python", "-m", "antsibull_changelog"]
    assert command[-2:] == ["--ansible-doc-bin", "/venv/bin/ansible-doc"]


def test_un_ansible_doc_donne_nest_pas_double() -> None:
    argv = ["changelog.py", "release", "--ansible-doc-bin", "/ailleurs/ansible-doc"]
    assert changelog.commande(argv, "/venv/bin/python").count("--ansible-doc-bin") == 1


def test_juger_les_fragments_ne_demande_pas_ansible_doc() -> None:
    assert "--ansible-doc-bin" not in changelog.commande(
        ["changelog.py", "lint"], "/venv/bin/python"
    )
