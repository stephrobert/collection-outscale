"""Classification d'une opération de l'API d'Outscale en intention Ansible.

Le classifieur répond à une seule question : *qu'est-ce que cette opération est
pour un utilisateur Ansible ?* Il ne décide ni du nom du module, ni de son
contenu.

Deux principes gouvernent ce fichier :

* **aucune opération ne disparaît.** Ce que les règles ne savent pas trancher
  est classé `UNKNOWN`, apparaît dans le rapport, et fait échouer la CI tant
  que personne ne l'a tranché par un override ;
* **les règles sont mécaniques et peu nombreuses.** Une règle qui aurait besoin
  de connaître une opération en particulier n'est pas une règle : c'est un
  override, et il se déclare dans `generator/overrides/`.

**Ces règles ne sont ni celles de Scaleway ni celles d'Exoscale, et c'est
mesuré.** Les 236 opérations du contrat 1.42.0 sont toutes des `POST` sur un
chemin qui est leur `operationId` (`POST /StartVms`) : la méthode HTTP ne
discrimine rien. Les six règles de Scaleway, qui tranchent sur le verbe HTTP,
ne rendent pourtant **aucun UNKNOWN** ici : leur dernière règle est « POST hors
création = action », et elles classent **190 opérations ACTION dont les 74
lectures**. Celles d'Exoscale font pareil, 163 ACTION avec les mêmes 74
lectures. Une règle qui décide faux est pire qu'une règle qui ne décide pas :
un rapport vert sur une classification fausse. C'est pourquoi il n'y a ici
aucune règle de repli sur la méthode. Ce qui porte le sens est le préfixe
verbal de l'`operationId`, et il ne prend que 21 valeurs, mesurées :

| verbe | n | classe | ce que ça veut dire |
|---|---:|---|---|
| `Read` | 74 | INFO | lecture, paginée ou non |
| `Create`, `Delete` | 92 | LIFECYCLE | création et suppression, périmètre Terraform |
| `Link`, `Unlink`, `Register`, `Deregister`, `Add`, `Remove` | 26 | LIFECYCLE | relie ou
  délie deux ressources, périmètre Terraform |
| `Update`, `Put`, `Set` | 30 | MANAGE | écriture d'un état durable |
| `Start`, `Stop`, `Reboot`, `Accept`, `Reject`, `Enable`, `Disable`, `Scale` | 13 | ACTION |
  opération ponctuelle sur l'existant |
| autre | 1 | **UNKNOWN** | `CheckAuthentication`, tranché par override le jour où
  `Account` est indexé |

Mesuré sur le contrat entier après ces règles : 1 UNKNOWN sur 236, dans un
tag non indexé. Ce n'est pas une preuve qu'elles ont raison, seulement
qu'elles ont décidé, et c'est pourquoi le rapport affiche la raison de chaque
décision.
"""

from __future__ import annotations

from dataclasses import dataclass

from generator.ir.enums import DAY2_KINDS, GenerationMode, HTTPMethod, OperationKind
from generator.ir.models import ApiOperation
from generator.parser.naming import split_words

#: Verbes de lecture. Outscale n'en a qu'un, et il ouvre 74 identifiants.
_READ_VERBS: frozenset[str] = frozenset({"read"})

#: Verbes de création et de suppression : la responsabilité de Terraform.
_LIFECYCLE_VERBS: frozenset[str] = frozenset({"create", "delete"})

#: Verbes qui relient ou délient deux ressources existantes : `LinkVolume`,
#: `UnlinkPublicIp`, `RegisterVmsInLoadBalancer`, `AddUserToUserGroup`. C'est
#: la frontière du projet : une liaison est une dépendance entre ressources,
#: et Terraform la porte dans son graphe.
_LINK_VERBS: frozenset[str] = frozenset(
    {"link", "unlink", "register", "deregister", "add", "remove"}
)

#: Écriture d'un état durable : `UpdateVm`, `PutUserPolicy`,
#: `SetDefaultPolicyVersion`.
_UPDATE_VERBS: frozenset[str] = frozenset({"update", "put", "set"})

#: Opération ponctuelle sur une ressource existante, dont l'effet est un
#: changement d'état : `StartVms`, `AcceptNetPeering`, `ScaleUpVmGroup`.
_ACTION_VERBS: frozenset[str] = frozenset(
    {"start", "stop", "reboot", "accept", "reject", "enable", "disable", "scale"}
)


@dataclass(frozen=True)
class Classification:
    """Décision de classification d'une opération, avec sa justification."""

    key: str
    kind: OperationKind
    mode: GenerationMode
    #: Règle ou override qui a produit la décision, affiché dans le rapport.
    reason: str

    @property
    def is_day2(self) -> bool:
        return self.kind in DAY2_KINDS


def verb_of(operation: ApiOperation) -> str:
    """Premier mot de l'`operationId`, en minuscules : `StartVms` -> `start`."""
    words = split_words(operation.id)
    return words[0] if words else ""


def classify(operation: ApiOperation) -> Classification:
    """Classe une opération à partir du verbe de son `operationId`.

    La méthode HTTP est vérifiée, pas interprétée : une opération qui ne
    serait pas un POST est une forme que le contrat ne porte pas aujourd'hui,
    et elle reste UNKNOWN plutôt que d'être classée sur un verbe dont on ne
    sait plus ce qu'il veut dire.
    """
    verb = verb_of(operation)
    method = operation.http_method

    if method is not HTTPMethod.POST:
        return _decision(
            operation,
            OperationKind.UNKNOWN,
            f"méthode {method.value} inattendue : le contrat ne porte que des POST",
        )

    if verb in _READ_VERBS:
        return _decision(operation, OperationKind.INFO, "verbe de lecture : rien n'est écrit")

    if verb in _LIFECYCLE_VERBS:
        return _decision(
            operation,
            OperationKind.LIFECYCLE,
            f"verbe {verb!r} : création ou suppression de ressource, périmètre Terraform",
        )

    if verb in _LINK_VERBS:
        return _decision(
            operation,
            OperationKind.LIFECYCLE,
            f"verbe {verb!r} : relie ou délie deux ressources, périmètre Terraform",
        )

    if verb in _UPDATE_VERBS:
        return _decision(
            operation, OperationKind.MANAGE, f"verbe {verb!r} : écriture d'un état durable"
        )

    if verb in _ACTION_VERBS:
        return _decision(
            operation,
            OperationKind.ACTION,
            f"verbe d'action {verb!r} : opération ponctuelle sur l'existant",
        )

    return _decision(
        operation,
        OperationKind.UNKNOWN,
        f"aucune règle pour le verbe {verb!r}",
    )


def _decision(operation: ApiOperation, kind: OperationKind, reason: str) -> Classification:
    return Classification(key=operation.key, kind=kind, mode=GenerationMode.AUTO, reason=reason)
