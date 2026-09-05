# La plateforme d'exemple : ce que la collection exploite, bâti par Terraform
# et le fournisseur officiel d'Outscale, le même outil qu'un utilisateur réel.
#
# Terraform provisionne, Ansible exploite : cette stack ne contient que ce que
# les modules de la collection lisent ou font changer d'état. Elle est reprise
# de la stack que feint fait tourner sur chaque pull request
# (`examples/stacks/outscale/main.tf` de stephrobert/feint), en gardant ses
# leçons mesurées (l'endpoint porte `/api/v1`, les sous-régions se demandent
# à l'API, une machine nomme son placement, le NAT vit dans un sous-réseau qui
# route déjà vers Internet) et en retirant ce qu'aucun module n'exerce.
#
# Trois Nets : `workload` porte les machines ; `services` reçoit un peering
# que Terraform propose **sans l'accepter**, pour que `net_peering_action`
# l'accepte ; `sandbox` en reçoit un second, que le même module refuse. Un
# peering ne se crée qu'une fois par paire de Nets, d'où le troisième.
#
# **Aucun identifiant n'est écrit ici.** Le fournisseur lit `OSC_ACCESS_KEY`,
# `OSC_SECRET_KEY`, `OSC_REGION` et `OSC_ENDPOINT_API` dans l'environnement,
# ce que `feint env outscale` exporte : contre l'émulateur, ce sont des
# valeurs factices ; contre le vrai cloud, ce seraient celles du mainteneur,
# et ce dépôt ne les demande jamais.

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    outscale = {
      source = "outscale/outscale"
      # 1.7 est la génération qui lit son endpoint avec son chemin depuis
      # OSC_ENDPOINT_API (`http://…/api/v1`) ; 1.1.x l'ajoute lui-même, et
      # feint a mesuré la frontière. Une résolution en deçà changerait en
      # silence la façon de viser l'émulateur.
      version = "~> 1.7"
    }
  }
}

variable "prefix" {
  type        = string
  description = "Le préfixe des noms de cette exécution : chaque run a le sien, et le contrôle de résidu s'en sert."
}

variable "region" {
  type    = string
  default = "eu-west-2"
}

variable "vm_type" {
  type        = string
  description = "Le type de machine. Doit exister dans le catalogue de la cible."
  default     = "tinav5.c1r1p2"
}

variable "image_name" {
  type        = string
  description = "L'image du catalogue que les machines démarrent."
  default     = "Ubuntu-24.04-2025.01"
}

provider "outscale" {
  region = var.region
}

# ---------------------------------------------------------------------------
# Où les machines peuvent aller se demande, il ne se suppose pas.
# ---------------------------------------------------------------------------

data "outscale_subregions" "all" {}

locals {
  az_a = data.outscale_subregions.all.subregions[0].subregion_name
  az_b = data.outscale_subregions.all.subregions[1].subregion_name
}

# ---------------------------------------------------------------------------
# Les Nets, depuis un module : un sous-réseau public par sous-région, un privé.
# ---------------------------------------------------------------------------

module "workload" {
  source = "./modules/net"

  name     = "${var.prefix}-workload"
  ip_range = "10.50.0.0/16"

  subnets = {
    public-a = { ip_range = "10.50.1.0/24", subregion_name = local.az_a }
    public-b = { ip_range = "10.50.3.0/24", subregion_name = local.az_b }
    private  = { ip_range = "10.50.2.0/24", subregion_name = local.az_a }
  }
}

module "services" {
  source = "./modules/net"

  name     = "${var.prefix}-services"
  ip_range = "10.60.0.0/16"

  subnets = {
    services = { ip_range = "10.60.1.0/24" }
  }
}

module "sandbox" {
  source = "./modules/net"

  name     = "${var.prefix}-sandbox"
  ip_range = "10.70.0.0/16"

  subnets = {
    sandbox = { ip_range = "10.70.1.0/24" }
  }
}

# Un jeu d'options DHCP propre au Net workload : c'est la seule forme
# d'UpdateNet qu'un client atteint, et `dhcp_option_info` le lit.
resource "outscale_dhcp_option" "workload" {
  domain_name         = "platform.internal"
  domain_name_servers = ["192.0.2.53", "192.0.2.54"]
  ntp_servers         = ["192.0.2.123"]

  tags {
    key   = "Name"
    value = "${var.prefix}-dopt"
  }

  depends_on = [module.workload]
}

resource "outscale_net_attributes" "workload" {
  net_id              = module.workload.net_id
  dhcp_options_set_id = outscale_dhcp_option.workload.dhcp_options_set_id
}

# Les deux peerings, proposés et **jamais acceptés ici** : c'est le module
# d'action qui accepte le premier et refuse le second. Un peering accepté
# par Terraform n'aurait rien laissé à Ansible.
resource "outscale_net_peering" "to_services" {
  accepter_net_id = module.services.net_id
  source_net_id   = module.workload.net_id

  tags {
    key   = "Name"
    value = "${var.prefix}-peering-services"
  }
}

resource "outscale_net_peering" "to_sandbox" {
  accepter_net_id = module.sandbox.net_id
  source_net_id   = module.workload.net_id

  tags {
    key   = "Name"
    value = "${var.prefix}-peering-sandbox"
  }
}

# ---------------------------------------------------------------------------
# La porte publique : un service Internet, une table de routage, la route.
# ---------------------------------------------------------------------------

resource "outscale_internet_service" "main" {
  tags {
    key   = "Name"
    value = "${var.prefix}-igw"
  }
}

resource "outscale_internet_service_link" "main" {
  internet_service_id = outscale_internet_service.main.internet_service_id
  net_id              = module.workload.net_id
}

resource "outscale_route_table" "public" {
  net_id = module.workload.net_id

  tags {
    key   = "Name"
    value = "${var.prefix}-public"
  }
}

resource "outscale_route" "default" {
  route_table_id       = outscale_route_table.public.route_table_id
  destination_ip_range = "0.0.0.0/0"
  gateway_id           = outscale_internet_service.main.internet_service_id

  depends_on = [outscale_internet_service_link.main]
}

resource "outscale_route_table_link" "public" {
  for_each = toset(["public-a", "public-b"])

  route_table_id = outscale_route_table.public.route_table_id
  subnet_id      = module.workload.subnet_ids[each.key]
}

# ---------------------------------------------------------------------------
# La sortie privée : un service NAT avec sa propre adresse, et sa table.
# ---------------------------------------------------------------------------

resource "outscale_public_ip" "nat" {
  tags {
    key   = "Name"
    value = "${var.prefix}-nat-ip"
  }
}

resource "outscale_nat_service" "main" {
  subnet_id    = module.workload.subnet_ids["public-a"]
  public_ip_id = outscale_public_ip.nat.public_ip_id

  # Un service NAT vit dans un sous-réseau qui route déjà vers Internet.
  depends_on = [outscale_route_table_link.public]
}

resource "outscale_route_table" "private" {
  net_id = module.workload.net_id

  tags {
    key   = "Name"
    value = "${var.prefix}-private"
  }
}

resource "outscale_route" "private_default" {
  route_table_id       = outscale_route_table.private.route_table_id
  destination_ip_range = "0.0.0.0/0"
  nat_service_id       = outscale_nat_service.main.nat_service_id
}

resource "outscale_route_table_link" "private" {
  route_table_id = outscale_route_table.private.route_table_id
  subnet_id      = module.workload.subnet_ids["private"]
}

# ---------------------------------------------------------------------------
# Les groupes de sécurité, un par étage.
# ---------------------------------------------------------------------------

resource "outscale_security_group" "web" {
  description         = "${var.prefix} web tier"
  security_group_name = "${var.prefix}-web"
  net_id              = module.workload.net_id
}

resource "outscale_security_group_rule" "web_http" {
  flow              = "Inbound"
  security_group_id = outscale_security_group.web.security_group_id
  from_port_range   = 80
  to_port_range     = 80
  ip_protocol       = "tcp"
  ip_range          = "0.0.0.0/0"
}

resource "outscale_security_group" "app" {
  description         = "${var.prefix} application tier"
  security_group_name = "${var.prefix}-app"
  net_id              = module.workload.net_id
}

resource "outscale_security_group_rule" "app_from_web" {
  flow              = "Inbound"
  security_group_id = outscale_security_group.app.security_group_id
  from_port_range   = 8080
  to_port_range     = 8080
  ip_protocol       = "tcp"
  ip_range          = "10.50.1.0/24"
}

# ---------------------------------------------------------------------------
# La clé que les machines démarrent avec.
# ---------------------------------------------------------------------------

resource "outscale_keypair" "platform" {
  keypair_name = "${var.prefix}-keypair"
  public_key   = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIr6pEFlAFO3YU0DNW/r8SkpjdbptN9ockkO2BtIolSD platform@example"
}

# ---------------------------------------------------------------------------
# Une image dorée, depuis un volume et son instantané.
# ---------------------------------------------------------------------------

resource "outscale_volume" "golden" {
  subregion_name = local.az_a
  size           = 10

  tags {
    key   = "Name"
    value = "${var.prefix}-golden"
  }
}

resource "outscale_snapshot" "golden" {
  volume_id = outscale_volume.golden.volume_id

  tags {
    key   = "Name"
    value = "${var.prefix}-golden"
  }
}

resource "outscale_image" "golden" {
  image_name = "${var.prefix}-golden"

  block_device_mappings {
    device_name = "/dev/sda1"
    bsu {
      snapshot_id = outscale_snapshot.golden.snapshot_id
    }
  }
}

# ---------------------------------------------------------------------------
# Les machines : deux web, une par sous-région, une applicative.
# ---------------------------------------------------------------------------

data "outscale_images" "catalogue" {
  filter {
    name   = "image_names"
    values = [var.image_name]
  }
}

locals {
  web_tier = {
    a = { subnet = "public-a", subregion = local.az_a }
    b = { subnet = "public-b", subregion = local.az_b }
  }
}

resource "outscale_vm" "web" {
  for_each = local.web_tier

  image_id           = data.outscale_images.catalogue.images[0].image_id
  vm_type            = var.vm_type
  keypair_name       = outscale_keypair.platform.keypair_name
  subnet_id          = module.workload.subnet_ids[each.value.subnet]
  security_group_ids = [outscale_security_group.web.security_group_id]

  placement_subregion_name = each.value.subregion
  placement_tenancy        = "default"

  tags {
    key   = "Name"
    value = "${var.prefix}-web-${each.key}"
  }
  tags {
    key   = "role"
    value = "web"
  }
  tags {
    key   = "exemple"
    value = var.prefix
  }
}

resource "outscale_public_ip" "web" {
  for_each = local.web_tier

  tags {
    key   = "Name"
    value = "${var.prefix}-web-${each.key}-ip"
  }
}

resource "outscale_public_ip_link" "web" {
  for_each = local.web_tier

  vm_id     = outscale_vm.web[each.key].vm_id
  public_ip = outscale_public_ip.web[each.key].public_ip
}

resource "outscale_vm" "app" {
  image_id           = data.outscale_images.catalogue.images[0].image_id
  vm_type            = var.vm_type
  keypair_name       = outscale_keypair.platform.keypair_name
  subnet_id          = module.workload.subnet_ids["private"]
  security_group_ids = [outscale_security_group.app.security_group_id]

  placement_subregion_name = local.az_a
  placement_tenancy        = "default"

  tags {
    key   = "Name"
    value = "${var.prefix}-app"
  }
  tags {
    key   = "role"
    value = "app"
  }
  tags {
    key   = "exemple"
    value = var.prefix
  }
}

# Une interface créée à part et attachée explicitement : c'est celle que
# `nic_info` lit avec son attachement.
resource "outscale_nic" "app_data_plane" {
  subnet_id          = module.workload.subnet_ids["private"]
  security_group_ids = [outscale_security_group.app.security_group_id]
  description        = "${var.prefix} app data plane"

  tags {
    key   = "Name"
    value = "${var.prefix}-app-nic"
  }
}

resource "outscale_nic_link" "app_data_plane" {
  device_number = "1"
  vm_id         = outscale_vm.app.vm_id
  nic_id        = outscale_nic.app_data_plane.nic_id
}

resource "outscale_volume" "app_data" {
  subregion_name = local.az_a
  size           = 20

  tags {
    key   = "Name"
    value = "${var.prefix}-app-data"
  }
}

resource "outscale_volume_link" "app_data" {
  device_name = "/dev/xvdb"
  volume_id   = outscale_volume.app_data.volume_id
  vm_id       = outscale_vm.app.vm_id
}

# ---------------------------------------------------------------------------
# Le load balancer devant l'étage web.
# ---------------------------------------------------------------------------

resource "outscale_load_balancer" "front" {
  load_balancer_name = "${var.prefix}-front"
  load_balancer_type = "internet-facing"
  subnets            = [module.workload.subnet_ids["public-a"]]
  security_groups    = [outscale_security_group.web.security_group_id]

  listeners {
    backend_port           = 80
    backend_protocol       = "HTTP"
    load_balancer_protocol = "HTTP"
    load_balancer_port     = 80
  }

  tags {
    key   = "Name"
    value = "${var.prefix}-front"
  }

  depends_on = [outscale_route_table_link.public]
}

resource "outscale_load_balancer_vms" "front" {
  load_balancer_name = outscale_load_balancer.front.load_balancer_name
  backend_vm_ids     = [for vm in outscale_vm.web : vm.vm_id]
}

# ---------------------------------------------------------------------------
# Ce que le lanceur et le playbook lisent. Un identifiant sort tel que l'API
# le rend, jamais préfixé ni recomposé.
# ---------------------------------------------------------------------------

output "prefix" {
  value = var.prefix
}

output "region" {
  value = var.region
}

output "subregions" {
  value = [local.az_a, local.az_b]
}

output "vm_ids" {
  value = merge({ for name, vm in outscale_vm.web : "web-${name}" => vm.vm_id }, { app = outscale_vm.app.vm_id })
}

output "net_ids" {
  value = { workload = module.workload.net_id, services = module.services.net_id, sandbox = module.sandbox.net_id }
}

output "subnet_ids" {
  value = module.workload.subnet_ids
}

output "net_peering_ids" {
  value = {
    to_services = outscale_net_peering.to_services.net_peering_id
    to_sandbox  = outscale_net_peering.to_sandbox.net_peering_id
  }
}

output "load_balancer_name" {
  value = outscale_load_balancer.front.load_balancer_name
}

output "keypair_name" {
  value = outscale_keypair.platform.keypair_name
}

output "image_id" {
  value = outscale_image.golden.image_id
}

output "snapshot_id" {
  value = outscale_snapshot.golden.snapshot_id
}

output "volume_ids" {
  value = { golden = outscale_volume.golden.volume_id, app_data = outscale_volume.app_data.volume_id }
}

output "security_group_ids" {
  value = { web = outscale_security_group.web.security_group_id, app = outscale_security_group.app.security_group_id }
}

output "public_ip_ids" {
  value = merge({ for name, ip in outscale_public_ip.web : "web-${name}" => ip.public_ip_id }, { nat = outscale_public_ip.nat.public_ip_id })
}

output "nic_id" {
  value = outscale_nic.app_data_plane.nic_id
}

output "route_table_ids" {
  value = { public = outscale_route_table.public.route_table_id, private = outscale_route_table.private.route_table_id }
}

output "internet_service_id" {
  value = outscale_internet_service.main.internet_service_id
}

output "nat_service_id" {
  value = outscale_nat_service.main.nat_service_id
}

output "dhcp_options_set_id" {
  value = outscale_dhcp_option.workload.dhcp_options_set_id
}

output "expected" {
  description = "Ce que l'inventaire doit trouver : le nombre de machines, par rôle."
  value       = { total = length(outscale_vm.web) + 1, web = length(outscale_vm.web), app = 1 }
}
