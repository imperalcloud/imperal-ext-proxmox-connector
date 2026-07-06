# Imperal Proxmox Connector

Imperal extension for connecting a user's own Proxmox VE cluster and managing it through Imperal Cloud.

## MVP status

This is now a usable operational MVP.

It supports:
- connecting one or more Proxmox VE endpoints per user
- auth with either API token or username/password
- secure secret storage through Imperal secrets
- test connection / health summary
- cluster status summary
- node listing
- storage listing across nodes
- storage content browsing for ISOs, templates, backups and images
- VM/container listing with filters
- guest detail lookup
- controlled guest power actions
- split, strict create flows for QEMU VMs and LXC containers with live preflight validation
- legacy combined guest creation flow kept for compatibility
- optional automatic start after successful creation
- QEMU cloud-init fields for username/password/SSH keys/IP config
- guest cloning
- snapshot listing, creation, and deletion
- recent task listing
- per-task status lookup by UPID
- connection rename / TLS policy update
- connection deletion / disconnect

## Included chat tools

- `connect_proxmox`
- `list_proxmox_connections`
- `update_proxmox_connection`
- `disconnect_proxmox`
- `test_proxmox_connection`
- `get_proxmox_status`
- `list_proxmox_nodes`
- `list_proxmox_storage`
- `list_proxmox_storage_content`
- `list_proxmox_guests`
- `get_proxmox_guest`
- `create_proxmox_vm`
- `create_proxmox_lxc`
- `create_proxmox_guest`
- `clone_proxmox_guest`
- `delete_proxmox_guest`
- `power_proxmox_guest`
- `list_proxmox_snapshots`
- `create_proxmox_snapshot`
- `delete_proxmox_snapshot`
- `list_proxmox_tasks`
- `get_proxmox_task_status`

## Authentication

Two modes are supported:

1. `api_token`
   - user provides `username`, `realm`, `token_id`, `token_secret`
   - extension authenticates with `Authorization: PVEAPIToken=...`

2. `password`
   - user provides `username`, `realm`, `password`
   - extension logs in via `/access/ticket` and uses the returned ticket + CSRF token

Secrets are stored separately from normal connection metadata.

## Guest creation scope

### QEMU
Current create flow now supports:
- VMID
- name
- cores and optional sockets
- memory
- optional balloon target memory
- tags / description / onboot
- one empty `scsi0` disk with optional format
- one bridge NIC with selectable model and optional VLAN tag
- optional ISO attachment through `ide2`
- optional machine / BIOS / CPU type
- optional guest agent flag
- optional boot order
- optional cloud-init drive + user/password/SSH keys/IP config/DNS/search domain/package upgrade/custom cicustom
- synchronous wait for create task completion
- optional auto-start after successful create

### LXC
Current create flow now supports:
- CTID
- name / hostname
- cores
- required memory and optional swap
- tags / description / onboot
- template-based create with validated Proxmox template volid
- rootfs storage + size
- DHCP or explicit IP network config on selected bridge
- optional VLAN tag on net0
- optional root password
- optional SSH public keys
- optional nameserver and search domain
- unprivileged mode flag
- synchronous wait for create task completion
- optional auto-start after successful create

## Current limits of this MVP

Still intentionally MVP-sized:
- no full VM hardware editing yet after create
- no extra-disk / second-NIC post-create helpers yet
- no live console/VNC proxy yet
- no backup job scheduling yet
- no ISO upload yet
- no advanced network/firewall management yet
- no panel forms yet — chat tools are the real interface for now
- no template/image import pipeline yet

## Create flow behavior

The create flow is now much more correct and production-friendly for a base MVP:
- `guest_id` may be omitted and the extension will request the next free VMID from Proxmox
- numeric fields are validated as positive before the API call
- tags are normalized into Proxmox-safe semicolon-separated values
- QEMU gets sane default boot order:
  - with ISO: `ide2 -> scsi0 -> net0`
  - without ISO: `scsi0 -> net0`
- ISO and LXC template references are validated into proper Proxmox volume IDs
- cloud-init automatically attaches a cloud-init drive when cloud-init fields are used
- QEMU balloon memory is validated against total memory
- LXC now supports DHCP or explicit IP config and optional VLAN tagging on `net0`
- create waits for task completion by default and surfaces task failure instead of pretending success
- `start_after_create` now really starts the guest after successful creation
- `start_after_clone` now waits for clone completion and really starts the cloned guest

## Local structure

- `app.py` — extension registration
- `main.py` — import bootstrap
- `models_proxmox.py` — SDL entities
- `providers.py` — Proxmox API client + connection persistence
- `handlers_proxmox.py` — chat tools
- `panels.py` — simple panel landing page
- `imperal.json` — manifest

## Git repository

Target repo:
`https://github.com/imperalcloud/imperal-ext-proxmox-connector`
