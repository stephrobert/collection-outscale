# Copyright: (c) 2026, Stéphane Robert
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = r"""
name: vm
short_description: Outscale VM dynamic inventory
version_added: 0.1.0
author:
  - Stéphane Robert (@stephrobert)
requirements:
  - osc-sdk-python >= 0.42
description:
  - Builds an Ansible inventory from the virtual machines of an Outscale account.
  - >-
    Discovers them region by region with C(ReadVms), page after page, with the
    OAPI filters you give, then names, addresses, filters and groups them.
  - Uses a configuration file whose name ends with C(outscale.yml) or C(osc.yml).
extends_documentation_fragment:
  - constructed
  - inventory_cache
notes:
  - >-
    Nothing is required. The SDK reads C(~/.osc/config.json) and the C(OSC_*)
    environment by itself; the options below take precedence when set.
  - >-
    The credential options are declared here rather than inherited from the
    module documentation fragment. A module option carries no C(env) key, so
    its default would silently win over the environment.
  - >-
    The API host carries the region, so the plugin builds one client per
    region. When I(api_url) is set, a single client serves every region,
    which is what a local emulator expects.
  - >-
    A failed C(ReadVms) is an error, never an empty region. A refused
    credential, a missing permission and an API failure give three different
    messages.
options:
  plugin:
    description: The name of this plugin.
    required: true
    choices: ['stephrobert.outscale.vm']
    type: str
  access_key:
    description: Outscale access key.
    type: str
    env:
      - name: OSC_ACCESS_KEY
  secret_key:
    description: Outscale secret key. Never written to the cache key nor to a message.
    type: str
    env:
      - name: OSC_SECRET_KEY
  profile:
    description: Name of a profile in C(~/.osc/config.json).
    type: str
    env:
      - name: OSC_PROFILE
  api_url:
    description:
      - Full base URL of the API, C(/api/v1) included, replacing the one built from each region.
      - Point it at a local emulator to build an inventory without a real account.
    type: str
    env:
      - name: OSC_ENDPOINT_API
      - name: OUTSCALE_API_URL
  regions:
    description:
      - Regions to query, for example V(eu-west-2) or V(cloudgouv-eu-west-1).
      - >-
        Empty means the region the SDK resolves itself, from E(OSC_REGION),
        then the profile, then V(eu-west-2).
    type: list
    elements: str
    default: []
  filters:
    description:
      - Filters sent to C(ReadVms) as they are, with the names of the C(FiltersVm) schema.
      - >-
        For example C(VmStateNames: [running]) or C(Tags: ["Name=web"]). A name
        the API does not know is reported with the API's own message.
    type: dict
    default: {}
  hostnames:
    description:
      - Sources for C(inventory_hostname), in order of precedence.
      - >-
        Accepts C(tag:KEY), which reads the value of the tag C(KEY), C(name),
        which reads the C(Name) tag, C(id), C(public_ipv4) and C(private_ipv4).
      - Collisions are resolved by appending the region, then the machine ID.
    type: list
    elements: str
    default: ['tag:Name', id]
  address_priority:
    description:
      - Address families to try, in order, when setting C(ansible_host).
    type: list
    elements: str
    default: [public_ipv4, private_ipv4]
  entry_role:
    description:
      - >-
        Role of the machines Ansible reaches directly. A machine whose
        I(entry_tag) tag carries this value gets its public address as
        C(ansible_host); every other machine gets its private address, to be
        reached through a C(ProxyJump). Overrides I(address_priority).
    type: str
  entry_tag:
    description: The tag that carries the role read by I(entry_role).
    type: str
    default: role
  require_address:
    description:
      - Drop hosts for which no address could be selected.
      - >-
        False keeps them without C(ansible_host), which is still useful for
        tasks delegated to localhost that act through the Outscale API.
    type: bool
    default: false
  states:
    description: Only keep hosts in these states, after the API filters.
    type: list
    elements: str
    default: []
  tags:
    description:
      - Only keep hosts carrying these tags, as a C(key) to C(value) mapping.
      - An empty value keeps every host carrying the key, whatever its value.
    type: dict
    default: {}
  tags_match:
    description: Whether a host must carry any or all of the requested tags.
    type: str
    choices: [any, all]
    default: any
  exclude_tags:
    description:
      - Drop hosts carrying these tags, as a C(key) to C(value) mapping, before every other filter.
      - An empty value drops every host carrying the key, whatever its value.
    type: dict
    default: {}
  exclude_vm_ids:
    description: Drop these machines, by ID, before every other filter.
    type: list
    elements: str
    default: []
  group_by:
    description:
      - Axes used to build the native C(osc_*) groups.
    type: list
    elements: str
    choices: [region, subregion, state, tags, net, subnet, vm_type, keypair]
    default: [region, subregion, state, tags]
  include_raw:
    description:
      - Expose the raw API object as C(outscale_raw). Off by default, because
        it carries C(UserData), which may hold secrets, into the cache.
    type: bool
    default: false
  strict:
    description:
      - Fail the inventory when a region fails, instead of warning.
    type: bool
    default: true
"""

EXAMPLES = r"""
# The minimal case: credentials and region come from the environment.
plugin: stephrobert.outscale.vm

---
# Production: two regions, only the running machines, grouped by tag.
plugin: stephrobert.outscale.vm
regions:
  - eu-west-2
  - cloudgouv-eu-west-1
filters:
  VmStateNames:
    - running
tags:
  env: production
group_by:
  - region
  - subregion
  - tags
  - vm_type
cache: true

---
# A bastion reached through its public address, every other machine through its private one.
plugin: stephrobert.outscale.vm
entry_role: bastion
exclude_tags:
  managed_by: talos

---
# Groups and variables built by Ansible itself.
plugin: stephrobert.outscale.vm
compose:
  ansible_user: "'outscale'"
keyed_groups:
  - prefix: image
    key: outscale_image_id
"""

from ansible.errors import AnsibleError, AnsibleParserError  # noqa: E402
from ansible.module_utils.basic import missing_required_lib  # noqa: E402
from ansible.plugins.inventory import (  # noqa: E402
    BaseInventoryPlugin,
    Cacheable,
    Constructable,
)

from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory import (  # noqa: E402
    config as configuration,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory import (  # noqa: E402
    discovery,
    filtering,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.address import (  # noqa: E402
    select_ansible_host,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.groups import (  # noqa: E402
    group_names,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.hostname import (  # noqa: E402
    assign_hostnames,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.models import (  # noqa: E402
    InventoryHost,
)
from ansible_collections.stephrobert.outscale.plugins.module_utils.inventory.providers.base import (  # noqa: E402
    DiscoveryContext,
)

#: Les suffixes que le plugin accepte pour son fichier de configuration.
ALLOWED_SUFFIXES = ("outscale.yaml", "outscale.yml", "osc.yaml", "osc.yml")

#: Le produit que ce plugin découvre. Le cœur en connaît d'autres par sa table.
PRODUCTS = ("vm",)

#: Le préfixe des hostvars.
PREFIX = "outscale_"

#: Le cœur lit des options aux noms génériques ; celles du plugin nomment ce
#: qu'elles touchent. `exclude_vm_ids` exclut des machines virtuelles, et
#: c'est ici, dans le seul fichier qui a le droit de les nommer, que la
#: traduction se fait.
OPTION_NAMES = {"exclude_ids": "exclude_vm_ids"}


def _plain(valeur):
    """Réduit une valeur à des structures qu'un cache sait écrire.

    Le SDK rend du JSON, donc presque tout passe tel quel ; ce qui n'a pas
    d'équivalent JSON devient sa représentation textuelle plutôt que de faire
    échouer l'écriture du cache.
    """
    if valeur is None or isinstance(valeur, (str, int, float, bool)):
        return valeur
    if isinstance(valeur, dict):
        return {str(cle): _plain(item) for cle, item in valeur.items()}
    if isinstance(valeur, (list, tuple, set)):
        return [_plain(item) for item in valeur]
    return str(valeur)


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """Le dialogue avec Ansible, et rien d'autre.

    Toutes les décisions vivent dans `module_utils/inventory/`, en couches qui
    se testent seules. Ce fichier lit les options, appelle le moteur, et pose
    le résultat dans l'inventaire.
    """

    NAME = "stephrobert.outscale.vm"

    def verify_file(self, path):
        if not super().verify_file(path):
            return False
        if not path.endswith(ALLOWED_SUFFIXES):
            self.display.vvv(
                "Skipping due to inventory source file name mismatch. "
                "The file name has to end with one of: " + ", ".join(ALLOWED_SUFFIXES)
            )
            return False
        return True

    def _option(self, nom):
        """Une option du plugin, sous le nom que le cœur emploie."""
        return self.get_option(OPTION_NAMES.get(nom, nom))

    def parse(self, inventory, loader, path, cache=True):
        super().parse(inventory, loader, path, cache)
        self._read_config_data(path)

        if not discovery.HAS_SDK:
            raise AnsibleError(missing_required_lib("osc-sdk-python"))

        try:
            settings = configuration.from_options(self._option, discovery.group_axes(PRODUCTS))
        except configuration.ConfigError as erreur:
            raise AnsibleParserError(str(erreur)) from erreur

        self.load_cache_plugin()
        identite = f"{self.get_option('access_key') or ''}|{self.get_option('profile') or ''}"
        empreinte = settings.cache_fingerprint(self.get_option("api_url"), identite)
        cache_key = f"{self.get_cache_key(path)}_{empreinte}"

        demande = self.get_option("cache")
        lire = demande and cache
        ecrire = demande and not cache

        materiel = None
        if lire:
            try:
                materiel = self._cache[cache_key]
                self.display.vvv(f"outscale: cache hit ({cache_key})")
            except KeyError:
                ecrire = True

        if materiel is None:
            materiel = self._collect(settings)
            self.display.vvv("outscale: cache miss, découverte effectuée")

        if ecrire:
            self._cache[cache_key] = materiel

        self._populate(materiel, settings)

    def _collect(self, settings):
        """Découvre, filtre, et rend une structure que n'importe quel cache accepte."""
        client_for = discovery.client_factory(
            self.get_option("access_key"),
            self.get_option("secret_key"),
            self.get_option("profile"),
            self.get_option("api_url"),
        )
        try:
            regions = discovery.resolve_regions(settings.regions, client_for)
        except ValueError as erreur:
            raise AnsibleParserError(str(erreur)) from erreur

        context = DiscoveryContext(
            regions=regions,
            api_filters=settings.api_filters,
            include_raw=settings.include_raw,
        )

        try:
            resultat, report = discovery.discover(
                client_for, context, PRODUCTS, strict=settings.strict
            )
        except discovery.AuthenticationFailed as erreur:
            raise AnsibleError(f"outscale: {erreur}") from erreur

        if settings.strict and report.errors:
            raise AnsibleError("la découverte a échoué : " + " ; ".join(report.errors))

        gardes = []
        ecartes = []
        for host in resultat.hosts:
            garde, raison = filtering.keep(host.id, host.tags, host.state, settings.filters)
            if garde:
                gardes.append(host)
            else:
                ecartes.append(f"{host.name or host.id} ({host.region}) : {raison}")
        return {
            "hosts": [self._serialise(host) for host in gardes],
            "report": report.lines() + ["écartée : " + raison for raison in ecartes],
        }

    @staticmethod
    def _serialise(host):
        """Le modèle normalisé, en structures sérialisables."""
        return {
            "id": host.id,
            "product": host.product,
            "name": host.name,
            "region": host.region,
            "subregion": host.subregion,
            "state": host.state,
            "tags": dict(host.tags),
            "public_ipv4": list(host.public_ipv4),
            "private_ipv4": list(host.private_ipv4),
            "net_id": host.net_id,
            "subnet_id": host.subnet_id,
            "security_group_ids": list(host.security_group_ids),
            "metadata": _plain(dict(host.metadata)),
            "raw": _plain(host.raw),
        }

    @staticmethod
    def _deserialise(donnees):
        return InventoryHost(
            id=donnees["id"],
            product=donnees["product"],
            name=donnees.get("name"),
            region=donnees.get("region"),
            subregion=donnees.get("subregion"),
            state=donnees.get("state"),
            tags=dict(donnees.get("tags") or {}),
            public_ipv4=tuple(donnees.get("public_ipv4") or ()),
            private_ipv4=tuple(donnees.get("private_ipv4") or ()),
            net_id=donnees.get("net_id"),
            subnet_id=donnees.get("subnet_id"),
            security_group_ids=tuple(donnees.get("security_group_ids") or ()),
            metadata=donnees.get("metadata") or {},
            raw=donnees.get("raw"),
        )

    def _populate(self, materiel, settings):
        """Pose les hosts, leurs variables et leurs groupes dans l'inventaire."""
        for ligne in materiel["report"]:
            self.display.vvv("outscale: " + ligne)

        hosts = tuple(self._deserialise(donnees) for donnees in materiel["hosts"])
        attribues, collisions = assign_hostnames(hosts, settings.hostnames)
        for avertissement in collisions:
            self.display.warning("outscale: " + avertissement)

        strict = settings.strict
        axes = discovery.group_axes(PRODUCTS)

        for host, nom in attribues:
            selection = select_ansible_host(host, settings.address)
            self.display.vvvv("outscale: " + selection.explain(nom))

            if not selection.found and settings.require_address:
                self.display.warning(f"outscale: {nom} écartée, {selection.source}")
                continue

            self.inventory.add_host(nom)
            if selection.found:
                self.inventory.set_variable(nom, "ansible_host", selection.address)

            variables = self._host_variables(host, selection)
            for cle, valeur in variables.items():
                self.inventory.set_variable(nom, cle, valeur)

            for groupe in group_names(host, settings.group_by, axes):
                self.inventory.add_group(groupe)
                self.inventory.add_child(groupe, nom)

            # Les mécanismes natifs d'Ansible, appelés et non seulement hérités.
            self._set_composite_vars(self.get_option("compose"), variables, nom, strict)
            self._add_host_to_composed_groups(self.get_option("groups"), variables, nom, strict)
            self._add_host_to_keyed_groups(self.get_option("keyed_groups"), variables, nom, strict)

    @staticmethod
    def _host_variables(host, selection):
        """Les hostvars stables, celles sur lesquelles un playbook peut compter.

        `outscale_id` et `outscale_region` sont ce qui permet d'enchaîner sur
        les modules Day-2 sans lookup supplémentaire. Ce qui n'appartient
        qu'au produit (`vm_type`, `image_id`, `keypair_name`) est posé à plat
        sous le même préfixe, avec le nom que le provider lui a donné.
        """
        variables = {
            PREFIX + "id": host.id,
            PREFIX + "name": host.name,
            PREFIX + "state": host.state,
            PREFIX + "region": host.region,
            PREFIX + "subregion": host.subregion,
            PREFIX + "net_id": host.net_id,
            PREFIX + "subnet_id": host.subnet_id,
            PREFIX + "public_ipv4": host.public_ipv4[0] if host.public_ipv4 else None,
            PREFIX + "private_ipv4": host.private_ipv4[0] if host.private_ipv4 else None,
            PREFIX + "private_ipv4s": list(host.private_ipv4),
            PREFIX + "tags": dict(host.tags),
            PREFIX + "security_group_ids": list(host.security_group_ids),
            PREFIX + "address_source": selection.source,
        }
        for cle, valeur in host.metadata.items():
            variables[PREFIX + str(cle)] = valeur
        if host.raw is not None:
            variables[PREFIX + "raw"] = host.raw
        return variables
