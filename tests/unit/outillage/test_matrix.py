"""La matrice ansible-core se dérive, elle ne se recopie pas.

Chez collection-exoscale, trois endroits tenaient la liste à la main. Ce
fichier mesure la dérivation, et la porte qui exige que la CI la porte.
"""

from __future__ import annotations

import ansible_matrix
import pytest


def test_la_matrice_va_de_la_borne_basse_a_la_mineure_du_verrou() -> None:
    assert ansible_matrix.matrix(">=2.17.0", (2, 21)) == [
        ">=2.17,<2.18",
        ">=2.18,<2.19",
        ">=2.19,<2.20",
        ">=2.20,<2.21",
        ">=2.21,<2.22",
    ]


def test_une_borne_egale_au_verrou_donne_une_seule_plage() -> None:
    assert ansible_matrix.matrix(">=2.21", (2, 21)) == [">=2.21,<2.22"]


def test_une_borne_au_dela_du_verrou_est_refusee() -> None:
    """Une version promise et jamais éprouvée est une promesse sans preuve."""
    with pytest.raises(ansible_matrix.MatrixError, match="jamais été éprouvée"):
        ansible_matrix.matrix(">=2.22.0", (2, 21))


def test_une_declaration_sans_borne_est_refusee() -> None:
    with pytest.raises(ansible_matrix.MatrixError, match="borne"):
        ansible_matrix.matrix("2.17", (2, 21))


def test_la_ci_et_le_ruleset_portent_la_matrice_derivee() -> None:
    """Le contrôle réel, sur les fichiers du dépôt : un écart rougit ici avant la CI."""
    plages = ansible_matrix.expected()
    assert plages
    assert ansible_matrix.check(plages) == []
