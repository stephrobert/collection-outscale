# Instructions Claude Code : collection-outscale

Ce dépôt produit une **collection Ansible Day-2 pour Outscale**, et surtout le
générateur qui l'écrit. Le code généré n'est pas le produit : le produit est le
contrat versionné, les règles de classification, et les quelques overrides
explicites qui transforment une API technique en interface Ansible cohérente.

Il transpose l'architecture de `collection-scaleway` et les leçons de
`collection-exoscale`, pas leurs fichiers. Chaque écart est mesuré sur le
contrat d'Outscale, et la mesure est écrite à côté de la décision qu'elle
justifie.

## Objectif majeur (l'étoile polaire)

**Un module généré doit être celui qu'un opérateur aurait écrit à la main, en
mieux tenu.** Un test unitaire vert ne prouve rien : la preuve est qu'un
playbook réel passe, et qu'un utilisateur comprend le module sans lire l'API
Outscale.

Le corollaire, qui tranche toutes les ambiguïtés de design :

```text
Terraform provisionne les ressources. Ansible exploite les ressources existantes.
```

Une opération qui crée, supprime ou relie des ressources n'a pas sa place ici,
même si le générateur sait la produire.

## Ce qu'Outscale fait autrement, mesuré

Ces faits sont ceux du contrat `outscale/osc-api` au tag 1.42.0 (236 chemins,
236 opérations, 655 schémas, 50 tags). Chacun a changé le code.

| fait mesuré | conséquence dans le code |
|---|---|
| **tout est un POST sur `/<OperationId>`** : 236 sur 236, aucun paramètre de chemin ni de requête | les six règles de Scaleway rendent **190 ACTION et 0 INFO** (leur dernière règle est « POST hors création = action ») ; celles d'Exoscale, 163 ACTION ; les 74 lectures y sont classées ACTION dans les deux cas. Ici c'est le **verbe de l'`operationId`** qui tranche, en 21 valeurs mesurées, et la méthode est vérifiée, pas interprétée : **1 UNKNOWN sur 236** (`CheckAuthentication`, tag non indexé), 0 sur les 22 produits indexés |
| **un tag par opération, aucune liste `tags` racine, aucune hiérarchie** | `products.txt` indexe des tags tels que le contrat les écrit ; le nom du produit est le tag en snake_case ; `python -m generator products --classify` recense les 50 tags avec leurs UNKNOWN |
| **la ressource se lit dans l'identifiant**, pas dans le chemin : `ReadVms`, `StartVms`, `UpdateVm` | `derive_resource` retire le verbe et singularise : `vm`, `vm_type`, `net_peering`. Le produit n'est pas redoublé dans le nom du module (`vm_type_info`, pas `vm_vm_type_info`) |
| **une lecture par ressource**, et `ReadVms` filtré sur `VmIds` est la lecture unitaire | un module INFO porte **une** opération et ses filtres, dont les clés viennent des 67 propriétés de `FiltersVm` ; pas de couple GET/LIST |
| **36 lectures sur 74 paginent par `NextPageToken`**, requête et réponse ensemble | l'IR porte `page_token`, le runtime enchaîne les pages ; 38 lectures rendent leur réponse en une fois et le rapport le dit |
| **toute réponse porte `ResponseContext`** ; 86 rendent un objet, 57 une liste, 79 rien, 14 plusieurs propriétés | le contexte est retiré avant de décider ; une charge utile indécidable rend la réponse entière et se lit dans les limites (`ReadAdminPassword`) |
| **`DryRun` sur 226 requêtes**, `ResultsPerPage` sur 44 | ni options ni envoyés : le check mode d'Ansible n'envoie rien, et la pagination est l'affaire du runtime |
| **une action répond tout de suite, et la ressource change d'état ensuite** : `StopVms` rend `stopping` | pas d'objet `operation` ; l'état visé se déclare par un override `wait`, et le runtime relit la ressource par la lecture de la même ressource, filtrée sur le sélecteur (`VmIds` tel quel, `NetPeeringId` au pluriel dans `FiltersNetPeering`), lien lu dans les propriétés du schéma, jamais deviné |
| **`required` déclaré sur 164 corps sur 236** ; 15 `oneOf`, tous `string(date) \| string(date-time)` ; aucun `allOf` | le mapping s'en sert ; un `oneOf` de variantes du même type scalaire est ce type, toute autre composition reste inconnue |
| **le SDK Python officiel embarque sa copie du contrat** et refuse une action ou un paramètre qu'elle ne connaît pas ; 0.42.0 embarque 1.42.0 | le runtime appelle `Gateway.<OperationId>`, un test exige que le SDK installé connaisse chaque action et chaque paramètre qu'un module envoie, et `sync:api` épingle le tag : contrat et SDK se relèvent ensemble |
| **`OSC_ENDPOINT_API` porte le chemin `/api/v1`**, et c'est ce que le SDK, `octl`, le fournisseur Terraform 1.7+ et `feint env outscale` lisent | l'URL de l'émulateur est honorée de bout en bout sans rien écrire ; un `eval $(feint env outscale)` suffit |
| **feint sert 100 routes sur 236** et Terraform y est `supported, provenInCI` | la plateforme d'exemple est en HCL, avec le fournisseur officiel, le même outil qu'un utilisateur réel |

## Architecture

```text
LE PRODUCTEUR, à la racine
generator/source/       lecture du contrat versionné, découpage par tag, jamais du réseau
generator/parser/       OpenAPI 3.0 -> IR canonique ; traduit, ne décide rien
generator/ir/           dataclasses gelées, sérialisation déterministe
generator/classifier/   les règles d'Outscale, sur le verbe ; ce qui reste est UNKNOWN
generator/overrides/    les décisions humaines, chacune avec sa raison
generator/ansible/      noms de modules, types, modèle du module
generator/renderer/     Jinja2, rendu seul
generator/report/       texte, JSON, Markdown
scripts/                sync, rapport, golden, dérive, sanity, archive, release, compteurs,
                        falsification, matrice, exemple, résidu
specs/outscale/         le contrat, et products.txt qui indexe des tags
tests/fixtures/widget/  un contrat de laboratoire qui reproduit les formes d'Outscale
examples/stack/         la plateforme d'exemple, en HCL
docs/                   publié, en anglais : le générateur, le contrat, Scorecard
.github/                onze workflows, CODEOWNERS, dependabot, le ruleset de main

LE LIVRABLE, à l'emplacement qu'Ansible impose
ansible_collections/stephrobert/outscale/
    galaxy.yml          l'identité, seule source du namespace
    plugins/module_utils/outscale.py   client SDK, pagination, relecture d'état, erreurs
    plugins/module_utils/inventory/    le moteur d'inventaire, en couches sans nom de produit
    plugins/inventory/vm.py            le dialogue avec Ansible, et rien d'autre
    plugins/modules/    les modules générés
    plugins/doc_fragments/  les paramètres communs, et le fragment `wait`
    meta/               requires_ansible, dont la matrice de CI se dérive
    changelogs/         les fragments, et le changelog qu'ils composent
```

**Aucun nom en dur dans un contrôle.** Chez scaleway, quatre contrôles en une
journée ont survécu au renommage de ce qu'ils contrôlaient. Ici, `package.py`
lit `plugins/` sur le disque, `readme_counters.py` lit l'index des produits,
les modules et le contrat, `ansible_matrix.py` lit `meta/runtime.yml` et le
verrou. Ne coder aucun nom de module, de plugin ni de produit dans un contrôle.

## Le compte réel ne se touche pas

**Aucun appel au compte Outscale réel depuis ce dépôt, jamais, sans l'accord
explicite du mainteneur, demandé à chaque fois.** Ni `mise run example:reel`,
ni `terraform apply` avec de vrais identifiants, ni un appel authentifié qui
crée, modifie ou supprime quoi que ce soit, ni même un `Create*` pour valider
une syntaxe. Deux raisons, et la première suffit :

* ça coûte de l'argent sur son compte, et la décision de dépenser lui
  appartient ;
* une ressource qui survit à un run raté est un résidu payant, et la garantie
  de résidu zéro de ce dépôt n'a encore rien prouvé sur le vrai cloud.

Le précédent existe : le 30 avril 2026, une validation de syntaxe par
`osc-cli api CreateAccessKey` a créé trois clés d'accès sur le compte racine du
mainteneur. `osc-cli` n'a pas de mode simulation, et un appel sans paramètre
est déjà un appel.

Tout le reste se fait sans demander : feint émule Outscale (`feint env
outscale`, 100 routes sur 236), et c'est contre lui que la plateforme
d'exemple, le lanceur, le plugin de rappel, le contrôle de résidu et la porte
de couverture s'exercent. Quand un run réel apporterait quelque chose que
l'émulateur ne peut pas donner, **s'arrêter et demander**, en disant
précisément ce que ce run prouverait et ce qu'il coûterait.

**Le port.** feint est développé sur cette machine ; collection-scaleway
écoute sur 4877, collection-exoscale sur 4993. Cet exercice écoute sur
**127.0.0.1:4811**, et `refuser_emulateur_habite()` refuse d'adopter un
émulateur qui héberge déjà des machines.

## Moins de modules, tous exercés

Chez collection-exoscale, 136 modules étaient écrits et 40 appelés par
l'exemple : une porte dont la liste d'exceptions vaut 96 entrées ne garde plus
rien. La règle de ce dépôt :

* `products.txt` n'indexe que les tags que feint sert **et** que la stack HCL
  touche : 22 sur 50. Les 28 autres sont recensés à chaque exécution avec
  leur nombre d'opérations et leurs UNKNOWN, jamais générés ;
* dans un produit indexé, une lecture que feint décline n'est pas générée :
  un override `expose: false` **avec sa raison** la retire des modules, elle
  reste classée et comptée, et le rapport la liste sous « classées, mais sans
  module, par décision » ;
* `SANS_CIBLE` et `PRODUITS_SANS_CIBLE` de `scripts/example_coverage.py` sont
  **vides**, et `coverage:check` dans `mise run check` refuse tout module
  livré qu'aucune clé de tâche d'`examples/playbooks/` n'appelle ;
* on élargit quand l'exemple suit, jamais avant.

## Règles non négociables

1. **Aucune opération ne disparaît.** Une opération qu'aucune règle ne tranche
   est `UNKNOWN` et fait échouer `report --strict`. Une opération hors des
   tags indexés est comptée par `products`, jamais oubliée.
2. **Un override porte une raison.** Le chargeur refuse un changement de
   classification, un renommage, un typage, un masquage de paramètre ou un
   retrait de module sans `reason`, et refuse un champ inconnu.
3. **Le générateur ne devine pas.** Un type absent lève plutôt que de devenir
   un `str` ; un filtre de relecture absent du schéma `Filters` est dit dans
   les limites ; un nom d'option n'est jamais retraduit vers le contrat.
4. **Le parser ne décide pas, le classifieur ne nomme pas, la source ne
   traduit pas.** Chaque étape a une responsabilité.
5. **Aucune logique dans un template.**
6. **La génération est déterministe.** Même contrat, mêmes fichiers.
7. **`OSC_ENDPOINT_API` reste honoré de bout en bout**, pour un émulateur.
8. **Pas de `git push` sans accord explicite.** Commits locaux. Le dépôt
   GitHub existe et sa première poussée a été autorisée ; les suivantes se
   demandent.
9. **Codes de sortie stables** : `0`, `1` erreur, `2` non trié ou orphelin,
   `3` dérive du contrat.
10. **Un module ne ment pas sur `changed`.** Une action est acceptée tout de
    suite ; le module relit la ressource jusqu'à l'état visé, ou dit qu'il
    n'a pas attendu, et rend `changed=false` quand l'état était déjà là.
11. **Aucune publication sur Galaxy depuis ce dépôt.** Le jeton et le tag
    appartiennent au mainteneur.

## La métrique ne se maquille pas

```text
couverture Day-2 = (AUTO + OVERRIDE) / (INFO + ACTION + MANAGE + WORKFLOW)
```

Mesuré sur vm : 12 opérations, 10 candidates Day-2, 100 % classées pour la
génération automatique, 2 LIFECYCLE écartées avec leur raison. Ce chiffre dit
que 10 opérations sur 10 sont classées, pas qu'un module les porte : le compte
rendu de génération publie les deux ratios : `UpdateVm` porte le module `vm`,
et deux lectures sont classées sans module par décision.
Toute phrase publiée sur la couverture nomme son dénominateur.

## Un commentaire n'est pas un contrôle

Une garde dont la suppression laisse tous les tests verts est un commentaire.
`mise run falsify` neutralise chaque garde déclarée dans
`tests/falsify/specs.json` dans une copie hors dépôt et exige que le test nommé
échoue. À lancer après tout ajout de garde.

## Les pièges propres à Outscale

* **Une règle qui décide faux est pire qu'une règle qui ne décide pas.** Les
  règles de Scaleway appliquées ici ne rendent pas 236 UNKNOWN, elles rendent
  190 ACTION, lectures comprises : un rapport vert sur une classification
  fausse. C'est pourquoi le classifieur vérifie la méthode et refuse tout
  verbe qu'il ne connaît pas, plutôt que d'avoir une règle de repli.
* **`RegisterVmsInLoadBalancer` donne la ressource `vm_in_load_balancer`.**
  La dérivation depuis l'identifiant est mécanique et ce nom n'est pas celui
  qu'un opérateur choisirait ; il est LIFECYCLE, sans module, et le rapport
  l'affiche. Corriger par override, jamais par une règle qui regarderait le
  milieu de l'identifiant.
* **`UpdateRouteTableLink` est MANAGE sur `route_table_link`**, pas sur
  `route_table` : la règle du verbe ne sait pas que c'est une liaison. Le
  modèle Ansible l'écarte parce qu'aucune lecture ne rend cette ressource,
  donc rien ne peut juger l'écriture ; même sort pour `UpdateRoute`. Le compte
  rendu de génération le dit, module par module, avec la raison.
* **Un module MANAGE n'expose que ce qu'il sait relire.** `UpdateVm` accepte
  `SecurityGroupIds`, et `Vm` rend `SecurityGroups[]` : l'option n'existe pas,
  et le compte rendu de génération le dit dans ses limites. Exposer une option
  qu'on ne peut pas comparer
  rendrait `changed` à chaque passage, ce que l'exemple mesure en jouant
  chaque réglage deux fois.
* **L'état d'un peering est un objet.** `NetPeering.State` porte `Name` et
  `Message` : le champ d'attente s'écrit `State.Name`, et le runtime lit un
  chemin pointé.
* **Un peering accepté par Terraform ne laisse rien à Ansible.** La stack
  propose un peering sans l'accepter, et `net_peering_action` l'accepte.
  **Un peering refusé ne se supprime plus** : `409 9029 ResourceConflict,
  the Net peering ... is rejected and cannot be deleted`, mesuré contre
  feint et conforme à la documentation de l'API. Refuser un peering que
  Terraform gère rendait la destruction impossible ; `reject` n'est donc
  pas joué par l'exemple, et le playbook le dit avec sa mesure.
* **Le SDK valide avant d'envoyer.** `Gateway` refuse un paramètre absent de
  sa copie du contrat par une exception héritant de `NotImplementedError`, et
  une erreur de l'API est un `requests.HTTPError` dont `.response` porte
  `Errors[]`. Le runtime distingue les deux.

## Avant de pousser

```bash
mise run check     # lint, types, tests, recensement et rapport strict, dérive des golden,
                   # fragments de changelog, falsification, matrice, compteurs des README,
                   # porte de couverture, archive
```

`check` porte tout ce que le job Générateur et le job Archive de la CI
portent : c'est la promesse de son nom, et l'archive y est parce qu'un défaut
a voyagé jusqu'en CI chez scaleway faute d'y être.

| ce que le changement touche | à lancer en plus | ce que ça prouve |
|---|---|---|
| une règle de classification, une règle de nommage | `mise run report` et lire le diff | que la décision change là où on croit |
| une garde, une validation, un refus | `mise run falsify` | que le test mord sans le correctif |
| le parser, l'IR | `mise run golden:update` puis lire le diff | ce que le changement fait vraiment aux opérations |
| un module généré, un template, le runtime | `mise run sanity` | qu'Ansible accepte le fichier produit, sur la version du verrou ; la matrice de CI fait les autres |
| un module, un plugin, une option d'inventaire | `mise run example` | que ça marche contre l'émulateur : plateforme bâtie, inventaire découvert, module joué, tout détruit sans résidu |
| le contrat | `python scripts/sync_specs.py --tag <dernier>`, `mise run drift`, `mise run check` | ce qui a bougé, tag par tag, indexé ou non ; puis relever le SDK avec |
| un workflow, une action, `.github/` | `mise run security` | qu'actionlint, zizmor et poutine acceptent le pipeline |
| `pyproject.toml` | `mise run lock` puis lire le diff | quelle dépendance apparaît vraiment, et sous quelle empreinte |
| `meta/runtime.yml` | `mise run matrix:check`, puis la matrice de CI | que la borne est mesurée, pas estimée |

## Ce qui est prouvé, et ce qui ne l'est pas

Les modules s'importent, leur `argument_spec` est accepté par Ansible, le
runtime est mesuré par des doubles, le SDK installé connaît chaque action et
chaque paramètre qu'un module envoie, et l'archive s'installe et répond à
`ansible-doc`. La plateforme d'exemple (`examples/`, skill
`example-stack-author`) se bâtit par Terraform contre feint, l'inventaire la
découvre, le playbook appelle **chaque** module livré, et le contrôle de
résidu différentiel dit qu'il ne reste rien. **Aucun module n'a été joué
contre le cloud réel**, et ça ne se fait pas sans demander. Le dire vaut mieux
qu'un vert qui ne mesure pas ça.

## L'inventaire : un cœur qui ne nomme aucun produit

`plugins/module_utils/inventory/` est en couches, et un test parcourt le code
de chaque couche du cœur par AST pour y refuser tout nom de produit : ajouter
un produit coûte un fichier de provider et une ligne dans `discovery.py`,
jamais une modification du cœur. Un second test confronte les champs que le
provider lit, lus dans son code, au schéma `Vm` du contrat versionné : un
champ renommé en amont rougit la CI au lieu de rendre un parc muet.

## Langue

La frontière est **ce qui est publié**, pas le fichier qui le produit.

| quoi | langue |
|---|---|
| les deux README, `docs/`, `SECURITY.md`, `galaxy.yml`, les fragments de changelog | **anglais** |
| ce que `DOCUMENTATION`, `EXAMPLES` et `RETURN` portent | **anglais**, il vient du contrat |
| le code, les commentaires, les docstrings, la stack HCL | **français**, avec les accents |
| les noms de tests, les raisons de mutation, les raisons d'override | **français** |
| la sortie des programmes : rapports, messages d'erreur, falsification | **français** |
| les workflows, leurs commentaires et les noms de jobs | **français** |
| les messages de commit | **français** |

Les identifiants Python, les noms de modules Ansible et le vocabulaire de l'API
restent en anglais partout : ce sont des noms propres, pas de la prose.

Ne jamais utiliser le tiret cadratin, dans les deux langues.
