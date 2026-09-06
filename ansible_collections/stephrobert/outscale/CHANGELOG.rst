==================================
stephrobert.outscale Release Notes
==================================

.. contents:: Topics

v0.1.0
======

Release Summary
---------------

First release of the generated Day-2 collection for the Outscale API: information modules for every resource the example platform touches, action modules for virtual machines and Net peerings, state modules that read a setting before writing it and report a change only when something differs, and a dynamic inventory plugin. Terraform provisions resources, this collection operates existing ones. Nothing here has been run against a real Outscale account yet: every module is exercised against the feint emulator on every pull request, and every setting is written twice to prove the second pass changes nothing.

New Plugins
-----------

Inventory
~~~~~~~~~

- stephrobert.outscale.vm - Outscale Vm dynamic inventory.

New Modules
-----------

- stephrobert.outscale.dhcp_option_info - Gather information about Outscale dhcp options.
- stephrobert.outscale.image - Manage the settings of an Outscale image.
- stephrobert.outscale.image_info - Gather information about Outscale images.
- stephrobert.outscale.internet_service_info - Gather information about Outscale internet services.
- stephrobert.outscale.keypair_info - Gather information about Outscale keypairs.
- stephrobert.outscale.load_balancer - Manage the settings of an Outscale load balancer.
- stephrobert.outscale.load_balancer_info - Gather information about Outscale load balancers.
- stephrobert.outscale.nat_service_info - Gather information about Outscale nat services.
- stephrobert.outscale.net - Manage the settings of an Outscale net.
- stephrobert.outscale.net_info - Gather information about Outscale nets.
- stephrobert.outscale.net_peering_action - Perform an action on Outscale net peerings.
- stephrobert.outscale.net_peering_info - Gather information about Outscale net peerings.
- stephrobert.outscale.nic - Manage the settings of an Outscale nic.
- stephrobert.outscale.nic_info - Gather information about Outscale nics.
- stephrobert.outscale.public_ip_info - Gather information about Outscale public ips.
- stephrobert.outscale.public_ip_range_info - Gather information about Outscale public ip ranges.
- stephrobert.outscale.region_info - Gather information about Outscale regions.
- stephrobert.outscale.route_table_info - Gather information about Outscale route tables.
- stephrobert.outscale.security_group_info - Gather information about Outscale security groups.
- stephrobert.outscale.snapshot_info - Gather information about Outscale snapshots.
- stephrobert.outscale.subnet - Manage the settings of an Outscale subnet.
- stephrobert.outscale.subnet_info - Gather information about Outscale subnets.
- stephrobert.outscale.subregion_info - Gather information about Outscale subregions.
- stephrobert.outscale.tag_info - Gather information about Outscale tags.
- stephrobert.outscale.vm - Manage the settings of an Outscale vm.
- stephrobert.outscale.vm_action - Perform an action on Outscale vms.
- stephrobert.outscale.vm_admin_password_info - Read the Outscale admin password.
- stephrobert.outscale.vm_info - Gather information about Outscale vms.
- stephrobert.outscale.vm_state_info - Gather information about Outscale vm states.
- stephrobert.outscale.vm_type_info - Gather information about Outscale vm types.
- stephrobert.outscale.volume - Manage the settings of an Outscale volume.
- stephrobert.outscale.volume_info - Gather information about Outscale volumes.
