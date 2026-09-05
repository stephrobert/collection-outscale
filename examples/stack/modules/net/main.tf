# Un Net et ses sous-réseaux, comme module réutilisable : la forme que toute
# stack Outscale substantielle adopte, et que feint applique sur chaque pull
# request. Le module porte sa propre contrainte de fournisseur : sans elle,
# Terraform résout l'`outscale` non qualifié d'un module enfant vers
# `hashicorp/outscale`, qui n'existe pas.

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    outscale = {
      source  = "outscale/outscale"
      version = "~> 1.7"
    }
  }
}

variable "name" {
  type = string
}

variable "ip_range" {
  type = string
}

variable "subnets" {
  # `subregion_name` reste facultatif : un sous-réseau qui n'en nomme pas
  # prend celle de la région par défaut, et les deux chemins doivent relire
  # ce qui a été écrit.
  type = map(object({
    ip_range       = string
    subregion_name = optional(string)
  }))
}

resource "outscale_net" "this" {
  ip_range = var.ip_range

  tags {
    key   = "Name"
    value = var.name
  }
}

resource "outscale_subnet" "this" {
  for_each = var.subnets

  net_id         = outscale_net.this.net_id
  ip_range       = each.value.ip_range
  subregion_name = each.value.subregion_name

  tags {
    key   = "Name"
    value = "${var.name}-${each.key}"
  }
}

output "net_id" {
  value = outscale_net.this.net_id
}

output "subnet_ids" {
  value = { for name, subnet in outscale_subnet.this : name => subnet.subnet_id }
}
