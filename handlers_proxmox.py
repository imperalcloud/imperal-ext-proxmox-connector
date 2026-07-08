from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from imperal_sdk.chat import ActionResult

from app import chat
from models_proxmox import (
    ProxmoxConnectionList,
    ProxmoxConnectionRecord,
    ProxmoxGuestList,
    ProxmoxGuestRecord,
    ProxmoxNodeList,
    ProxmoxSnapshotList,
    ProxmoxStatusRecord,
    ProxmoxStorageList,
    ProxmoxStorageRecord,
    ProxmoxTaskList,
    ProxmoxTaskRecord,
)
from providers import (
    ProxmoxError,
    bool_to_proxmox_flag,
    build_client_from_connection,
    build_lxc_net0,
    build_qemu_net0,
    build_rootfs_value,
    build_scsi_disk_value,
    connect_and_persist,
    delete_connection,
    ensure_bridge_exists,
    ensure_guest_exists,
    ensure_guest_id_free,
    ensure_node_exists,
    ensure_positive_int,
    ensure_storage_content_exists,
    ensure_storage_exists,
    guest_path,
    list_connections,
    next_guest_id,
    node_storage_path,
    normalize_tag_string,
    parse_volume_reference,
    resolve_connection,
    update_connection,
    wait_for_task,
    ensure_guest_type_for_create,
)


class EmptyParams(BaseModel):
    pass


class ConnectProxmoxParams(BaseModel):
    base_url: str = Field(description="Proxmox API base URL, for example https://pve.example.com:8006")
    auth_mode: Literal["api_token", "password"] = Field(description="Authentication mode")
    realm: str = Field(default="pam", description="Authentication realm like pam, pve, or ldap")
    username: str = Field(default="", description="Proxmox username, with or without @realm")
    user: str = Field(default="", description="Compatibility alias for UIs that submit user instead of username.")
    login: str = Field(default="", description="Compatibility alias for UIs that submit login instead of username.")
    password: str = Field(default="", description="Password when auth_mode=password")
    token_id: str = Field(default="", description="API token identifier when auth_mode=api_token")
    token_secret: str = Field(default="", description="API token secret when auth_mode=api_token")
    token_principal: str = Field(default="", description="Combined API token principal like root@pam!imperal-ext-connector. Optional shortcut; if set, username and token_id are derived from it.")
    tls_verify: bool = Field(default=True, description="Whether to verify TLS certificates")
    label: str = Field(default="", description="Optional friendly connection name")


class ConnectionIdParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")


class UpdateConnectionParams(BaseModel):
    connection_id: str = Field(description="Saved Proxmox connection identifier")
    label: str = Field(default="", description="New friendly name. Empty = keep current")
    tls_verify: Optional[bool] = Field(default=None, description="Override TLS verification flag. Null = keep current")


class ListGuestsParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(default="", description="Optional node filter")
    guest_type: Literal["all", "qemu", "lxc"] = Field(default="all", description="Return all guests, only qemu VMs, or only lxc containers")
    status: str = Field(default="", description="Optional status filter, for example running or stopped")


class GuestParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node name that owns the guest")
    guest_id: int = Field(description="VMID or CTID")
    guest_type: Literal["qemu", "lxc"] = Field(description="qemu or lxc")


class GuestPowerParams(GuestParams):
    action: Literal["start", "stop", "shutdown", "reboot", "resume", "suspend"] = Field(description="Lifecycle action")


class SnapshotCreateParams(GuestParams):
    snapshot: str = Field(description="Snapshot name")
    description: str = Field(default="", description="Optional snapshot description")
    include_ram: bool = Field(default=False, description="When true, request VM state/RAM snapshot if supported")


class SnapshotDeleteParams(GuestParams):
    snapshot: str = Field(description="Snapshot name to delete")


class TaskStatusParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node name that owns the task")
    task_id: str = Field(description="UPID task identifier returned by Proxmox")


class StorageListParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(default="", description="Optional node filter")
    enabled_only: bool = Field(default=False, description="Return only enabled storages")


class StorageContentParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node name")
    storage: str = Field(description="Storage identifier")
    content: str = Field(default="", description="Optional content filter like images, iso, vztmpl, backup, snippets")


class CreateGuestParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node to create the guest on")
    guest_type: Literal["qemu", "lxc"] = Field(description="Guest type to create")
    guest_id: Optional[int] = Field(default=None, description="Desired VMID/CTID. Empty = ask Proxmox for the next free ID")
    name: str = Field(description="Guest name")
    cores: Optional[int] = Field(default=None, description="CPU cores")
    sockets: Optional[int] = Field(default=None, description="CPU sockets for QEMU")
    memory_mb: Optional[int] = Field(default=None, description="Memory in MB")
    swap_mb: Optional[int] = Field(default=None, description="LXC swap in MB")
    description: str = Field(default="", description="Optional description")
    onboot: bool = Field(default=False, description="Start automatically on host boot")
    tags: str = Field(default="", description="Comma-separated tags")
    start_after_create: bool = Field(default=False, description="Start the guest after creation finishes")
    wait_for_completion: bool = Field(default=True, description="Wait until create task finishes before returning")
    start_timeout_seconds: int = Field(default=900, description="How long to wait for create/start tasks")
    qemu_ostype: str = Field(default="l26", description="QEMU guest OS type")
    qemu_machine: str = Field(default="", description="Optional QEMU machine type, for example q35")
    qemu_bios: str = Field(default="", description="Optional BIOS type, for example ovmf or seabios")
    qemu_agent: bool = Field(default=False, description="Enable QEMU guest agent flag")
    qemu_cpu_type: str = Field(default="", description="Optional CPU type, for example host or x86-64-v2-AES")
    qemu_balloon_mb: Optional[int] = Field(default=None, description="Optional balloon target memory in MB")
    qemu_scsi_storage: str = Field(default="", description="Storage for a new empty system disk")
    qemu_scsi_gb: Optional[int] = Field(default=None, description="Size of empty system disk in GB")
    qemu_scsi_format: str = Field(default="", description="Optional disk format, for example qcow2 or raw")
    qemu_iso_storage: str = Field(default="", description="Storage containing ISO")
    qemu_iso_file: str = Field(default="", description="ISO file name or full volid, e.g. debian.iso or local:iso/debian.iso")
    qemu_bridge: str = Field(default="vmbr0", description="Network bridge")
    qemu_model: str = Field(default="virtio", description="NIC model, for example virtio or e1000")
    qemu_vlan_tag: Optional[int] = Field(default=None, description="Optional VLAN tag for NIC")
    qemu_boot_order: str = Field(default="", description="Optional boot order string like order=scsi0;ide2;net0")
    qemu_ci_user: str = Field(default="", description="Optional cloud-init username")
    qemu_ci_password: str = Field(default="", description="Optional cloud-init password")
    qemu_ci_ssh_keys: str = Field(default="", description="Optional cloud-init SSH public keys")
    qemu_ci_ipconfig0: str = Field(default="", description="Optional cloud-init ipconfig0 value")
    qemu_ci_nameserver: str = Field(default="", description="Optional cloud-init nameserver")
    qemu_ci_searchdomain: str = Field(default="", description="Optional cloud-init search domain")
    qemu_ci_upgrade: bool = Field(default=False, description="Enable cloud-init package upgrade")
    qemu_ci_custom: str = Field(default="", description="Optional cicustom value")
    qemu_ci_storage: str = Field(default="", description="Storage for cloud-init drive; required when any cloud-init field is used")
    lxc_ostemplate: str = Field(default="", description="Container template volid like local:vztmpl/debian-12.tar.zst")
    lxc_rootfs_storage: str = Field(default="", description="Storage for rootfs")
    lxc_rootfs_gb: Optional[int] = Field(default=None, description="Root filesystem size in GB")
    lxc_bridge: str = Field(default="vmbr0", description="LXC network bridge")
    lxc_ip_config: str = Field(default="dhcp", description="Container IP mode/value for net0, e.g. dhcp or 192.168.1.50/24")
    lxc_vlan_tag: Optional[int] = Field(default=None, description="Optional VLAN tag for LXC net0")
    lxc_hostname: str = Field(default="", description="Optional explicit container hostname")
    lxc_password: str = Field(default="", description="Optional root password for LXC")
    lxc_ssh_public_keys: str = Field(default="", description="Optional SSH public keys for the container")
    lxc_nameserver: str = Field(default="", description="Optional nameserver for LXC")
    lxc_searchdomain: str = Field(default="", description="Optional search domain for LXC")
    lxc_unprivileged: bool = Field(default=True, description="Create LXC as unprivileged")


class CloneGuestParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Source node")
    guest_type: Literal["qemu", "lxc"] = Field(description="Source guest type")
    source_guest_id: int = Field(description="Source VMID/CTID")
    new_guest_id: int = Field(description="New VMID/CTID")
    name: str = Field(default="", description="Optional new guest name")
    target_node: str = Field(default="", description="Optional target node")
    target_storage: str = Field(default="", description="Optional target storage")
    full: bool = Field(default=True, description="Full clone if supported")
    snapshot: str = Field(default="", description="Optional snapshot to clone from")
    start_after_clone: bool = Field(default=False, description="Start the clone after the task is queued")


class CreateProxmoxVmParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node to create the VM on")
    guest_id: Optional[int] = Field(default=None, description="Desired VMID. Empty = ask Proxmox for next free ID")
    name: str = Field(description="VM name")
    cores: int = Field(description="CPU cores")
    memory_mb: int = Field(description="Memory in MB")
    sockets: int = Field(default=1, description="CPU sockets")
    description: str = Field(default="", description="Optional description")
    onboot: bool = Field(default=False, description="Start automatically on host boot")
    tags: str = Field(default="", description="Comma-separated tags")
    start_after_create: bool = Field(default=False, description="Start the VM after creation finishes")
    wait_for_completion: bool = Field(default=True, description="Wait until create task finishes before returning")
    start_timeout_seconds: int = Field(default=900, description="How long to wait for create/start tasks")
    qemu_ostype: str = Field(default="l26", description="QEMU guest OS type")
    qemu_machine: str = Field(default="", description="Optional QEMU machine type, for example q35")
    qemu_bios: str = Field(default="", description="Optional BIOS type, for example ovmf or seabios")
    qemu_agent: bool = Field(default=False, description="Enable QEMU guest agent flag")
    qemu_cpu_type: str = Field(default="", description="Optional CPU type, for example host")
    qemu_balloon_mb: Optional[int] = Field(default=None, description="Optional balloon target memory in MB")
    qemu_scsi_storage: str = Field(description="Storage for a new empty system disk")
    qemu_scsi_gb: int = Field(description="Size of empty system disk in GB")
    qemu_scsi_format: str = Field(default="", description="Optional disk format, for example qcow2 or raw")
    qemu_iso_storage: str = Field(default="", description="Storage containing ISO")
    qemu_iso_file: str = Field(default="", description="ISO file name or full volid, e.g. debian.iso or local:iso/debian.iso")
    qemu_bridge: str = Field(default="vmbr0", description="Network bridge")
    qemu_model: str = Field(default="virtio", description="NIC model, for example virtio or e1000")
    qemu_vlan_tag: Optional[int] = Field(default=None, description="Optional VLAN tag for NIC")
    qemu_boot_order: str = Field(default="", description="Optional boot order string like order=scsi0;ide2;net0")
    qemu_ci_user: str = Field(default="", description="Optional cloud-init username")
    qemu_ci_password: str = Field(default="", description="Optional cloud-init password")
    qemu_ci_ssh_keys: str = Field(default="", description="Optional cloud-init SSH public keys")
    qemu_ci_ipconfig0: str = Field(default="", description="Optional cloud-init ipconfig0 value")
    qemu_ci_nameserver: str = Field(default="", description="Optional cloud-init nameserver")
    qemu_ci_searchdomain: str = Field(default="", description="Optional cloud-init search domain")
    qemu_ci_upgrade: bool = Field(default=False, description="Enable cloud-init package upgrade")
    qemu_ci_custom: str = Field(default="", description="Optional cicustom value")
    qemu_ci_storage: str = Field(default="", description="Storage for cloud-init drive; required when any cloud-init field is used")


class CreateProxmoxLxcParams(BaseModel):
    connection_id: str = Field(default="", description="Saved Proxmox connection identifier. Empty = first saved connection")
    node: str = Field(description="Node to create the container on")
    guest_id: Optional[int] = Field(default=None, description="Desired CTID. Empty = ask Proxmox for next free ID")
    name: str = Field(description="Container name")
    cores: int = Field(description="CPU cores")
    memory_mb: int = Field(description="Memory in MB")
    swap_mb: int = Field(default=512, description="Swap in MB")
    description: str = Field(default="", description="Optional description")
    onboot: bool = Field(default=False, description="Start automatically on host boot")
    tags: str = Field(default="", description="Comma-separated tags")
    start_after_create: bool = Field(default=False, description="Start the container after creation finishes")
    wait_for_completion: bool = Field(default=True, description="Wait until create task finishes before returning")
    start_timeout_seconds: int = Field(default=900, description="How long to wait for create/start tasks")
    lxc_ostemplate: str = Field(description="Container template volid like local:vztmpl/debian-12.tar.zst")
    lxc_rootfs_storage: str = Field(description="Storage for rootfs")
    lxc_rootfs_gb: int = Field(description="Root filesystem size in GB")
    lxc_bridge: str = Field(default="vmbr0", description="LXC network bridge")
    lxc_ip_config: str = Field(default="dhcp", description="Container IP mode/value for net0, e.g. dhcp or 192.168.1.50/24")
    lxc_vlan_tag: Optional[int] = Field(default=None, description="Optional VLAN tag for LXC net0")
    lxc_hostname: str = Field(default="", description="Optional explicit container hostname")
    lxc_password: str = Field(default="", description="Optional root password for LXC")
    lxc_ssh_public_keys: str = Field(default="", description="Optional SSH public keys for the container")
    lxc_nameserver: str = Field(default="", description="Optional nameserver for LXC")
    lxc_searchdomain: str = Field(default="", description="Optional search domain for LXC")
    lxc_unprivileged: bool = Field(default=True, description="Create LXC as unprivileged")


class DeleteGuestParams(GuestParams):
    purge_unreferenced_disks: bool = Field(default=False, description="Also remove unreferenced disks where supported")
    destroy_owned_volumes: bool = Field(default=True, description="Destroy owned storage volumes together with the guest")


def _task_payload(connection: dict[str, Any], node: str, upid: Any, task_type: str, description: str) -> dict[str, Any]:
    return {
        "connection_id": connection["connection_id"],
        "node": node,
        "task_id": upid,
        "task_type": task_type,
        "status": "queued",
        "description": description,
    }


@chat.function("connect_proxmox", action_type="write", event="connection.created", data_model=ProxmoxConnectionRecord,
               description="Connect a user's Proxmox VE host or cluster using API token or username/password and save the connection for future actions.")
async def connect_proxmox(ctx, params: ConnectProxmoxParams) -> ActionResult:
    username = (params.username or params.user or params.login or "").strip()
    token_id = (params.token_id or "").strip()
    token_principal = (params.token_principal or "").strip()
    if token_principal:
        if "!" not in token_principal:
            return ActionResult.error("token_principal must look like root@pam!token-name")
        principal_username, principal_token_id = token_principal.split("!", 1)
        username = username or principal_username.strip()
        token_id = token_id or principal_token_id.strip()

    try:
        record = await connect_and_persist(
            ctx,
            base_url=params.base_url,
            auth_mode=params.auth_mode,
            realm=params.realm,
            username=username,
            password=params.password,
            token_id=token_id,
            token_secret=params.token_secret,
            tls_verify=params.tls_verify,
            label=params.label,
        )
    except ProxmoxError as e:
        message = str(e)
        return ActionResult.error(message, summary=f"Connect failed: {message}")
    return ActionResult.success(data=record, summary=f"Connected Proxmox '{record['label']}' at {record['base_url']}")


@chat.function("list_proxmox_connections", action_type="read", data_model=ProxmoxConnectionList,
               description="List saved Proxmox connections for the current user.")
async def list_proxmox_connections(ctx, params: EmptyParams) -> ActionResult:
    items = await list_connections(ctx)
    return ActionResult.success(data={"items": items}, summary=f"{len(items)} Proxmox connection(s)")


@chat.function("update_proxmox_connection", action_type="write", event="connection.updated", data_model=ProxmoxConnectionRecord,
               description="Rename a saved Proxmox connection or change its TLS verification setting.")
async def update_proxmox_connection(ctx, params: UpdateConnectionParams) -> ActionResult:
    updates: dict[str, Any] = {}
    if params.label:
        updates["label"] = params.label
    if params.tls_verify is not None:
        updates["tls_verify"] = params.tls_verify
    if not updates:
        return ActionResult.error("Nothing to update. Provide label and/or tls_verify.")
    try:
        record = await update_connection(ctx, params.connection_id, updates)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    return ActionResult.success(data=record, summary=f"Updated connection '{record.get('label') or record['connection_id']}'")


@chat.function("disconnect_proxmox", action_type="destructive", event="connection.deleted", data_model=ProxmoxConnectionRecord,
               description="Delete a saved Proxmox connection and remove its stored secret.")
async def disconnect_proxmox(ctx, params: ConnectionIdParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        removed = await delete_connection(ctx, connection["connection_id"])
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    return ActionResult.success(data=removed, summary=f"Disconnected '{removed.get('label') or removed['connection_id']}'")


@chat.function("test_proxmox_connection", action_type="read", data_model=ProxmoxStatusRecord,
               description="Test a saved Proxmox connection and return a quick status summary.")
async def test_proxmox_connection(ctx, params: ConnectionIdParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        version = await client.request("GET", "/version")
        nodes = await client.request("GET", "/nodes")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = {
        "connection_id": connection["connection_id"],
        "base_url": connection["base_url"],
        "cluster_name": connection.get("cluster_name") or connection.get("label"),
        "nodes_online": len(nodes or []),
        "nodes_total": len(nodes or []),
        "guests_running": 0,
        "guests_total": 0,
        "qemu_total": 0,
        "lxc_total": 0,
        "storage_total": 0,
        "status": "ok",
        "description": f"Reachable · Proxmox {version.get('version') or 'unknown'} · {len(nodes or [])} node(s)",
    }
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("get_proxmox_status", action_type="read", data_model=ProxmoxStatusRecord,
               description="Get cluster-wide summary for a connected Proxmox environment: nodes, guests and storage totals.")
async def get_proxmox_status(ctx, params: ConnectionIdParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        cluster_status = await client.request("GET", "/cluster/status")
        resources = await client.request("GET", "/cluster/resources")
    except ProxmoxError as e:
        return ActionResult.error(str(e))

    nodes_total = nodes_online = guests_total = guests_running = qemu_total = lxc_total = storage_total = 0
    if isinstance(cluster_status, list):
        for item in cluster_status:
            if item.get("type") == "node":
                nodes_total += 1
                if item.get("online"):
                    nodes_online += 1
    if isinstance(resources, list):
        for item in resources:
            typ = item.get("type")
            if typ == "qemu":
                qemu_total += 1
                guests_total += 1
                if item.get("status") == "running":
                    guests_running += 1
            elif typ == "lxc":
                lxc_total += 1
                guests_total += 1
                if item.get("status") == "running":
                    guests_running += 1
            elif typ == "storage":
                storage_total += 1

    data = {
        "connection_id": connection["connection_id"],
        "base_url": connection["base_url"],
        "cluster_name": connection.get("cluster_name") or connection.get("label"),
        "nodes_online": nodes_online,
        "nodes_total": nodes_total,
        "guests_running": guests_running,
        "guests_total": guests_total,
        "qemu_total": qemu_total,
        "lxc_total": lxc_total,
        "storage_total": storage_total,
        "status": "ok" if nodes_online == nodes_total else "degraded",
        "description": f"{guests_running}/{guests_total} guests running across {nodes_online}/{nodes_total} online nodes",
    }
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("list_proxmox_nodes", action_type="read", data_model=ProxmoxNodeList,
               description="List nodes in the connected Proxmox VE cluster.")
async def list_proxmox_nodes(ctx, params: ConnectionIdParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        items = await client.request("GET", "/nodes")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for item in items or []:
        rows.append({**item, "connection_id": connection["connection_id"], "description": f"CPU {item.get('cpu', 0):.2f}, mem {item.get('mem', 0)}/{item.get('maxmem', 0)}"})
    return ActionResult.success(data={"items": rows}, summary=f"{len(rows)} node(s)")


@chat.function("list_proxmox_storage", action_type="read", data_model=ProxmoxStorageList,
               description="List Proxmox storages on one node or across all nodes.")
async def list_proxmox_storage(ctx, params: StorageListParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        nodes = [params.node] if params.node else [n.get("node") for n in (await client.request("GET", "/nodes")) or [] if n.get("node")]
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for node in nodes:
        try:
            items = await client.request("GET", node_storage_path(node))
        except ProxmoxError:
            continue
        for item in items or []:
            if params.enabled_only and not item.get("enabled", 1):
                continue
            rows.append({
                **item,
                "connection_id": connection["connection_id"],
                "node": node,
                "description": f"{item.get('type', 'storage')} on {node} · {item.get('content', '')}",
            })
    return ActionResult.success(data={"items": rows}, summary=f"{len(rows)} storage target(s)")


@chat.function("list_proxmox_storage_content", action_type="read", data_model=ProxmoxStorageList,
               description="List content items inside one Proxmox storage, such as ISOs, templates, backups or disk images.")
async def list_proxmox_storage_content(ctx, params: StorageContentParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        query = {"content": params.content} if params.content else None
        items = await client.request("GET", node_storage_path(params.node, params.storage) + "/content", params=query)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for item in items or []:
        rows.append({
            "connection_id": connection["connection_id"],
            "node": params.node,
            "storage": params.storage,
            "content_type": item.get("content"),
            "volid": item.get("volid"),
            "size": item.get("size"),
            "status": "ok",
            "description": item.get("volid") or item.get("text") or item.get("content") or "storage item",
        })
    return ActionResult.success(data={"items": rows}, summary=f"{len(rows)} storage item(s)")


@chat.function("list_proxmox_guests", action_type="read", data_model=ProxmoxGuestList,
               description="List virtual machines and containers from the connected Proxmox VE environment.")
async def list_proxmox_guests(ctx, params: ListGuestsParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        items = await client.request("GET", "/cluster/resources", params={"type": "vm"})
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for item in items or []:
        typ = item.get("type")
        if typ not in {"qemu", "lxc"}:
            continue
        if params.guest_type != "all" and typ != params.guest_type:
            continue
        if params.node and item.get("node") != params.node:
            continue
        if params.status and item.get("status") != params.status:
            continue
        rows.append({
            **item,
            "connection_id": connection["connection_id"],
            "guest_type": typ,
            "description": f"{typ.upper()} {item.get('vmid')} on {item.get('node')} · {item.get('status', 'unknown')}",
        })
    return ActionResult.success(data={"items": rows}, summary=f"{len(rows)} guest(s)")


@chat.function("get_proxmox_guest", action_type="read", data_model=ProxmoxGuestRecord,
               description="Get detailed status for one Proxmox VM or container.")
async def get_proxmox_guest(ctx, params: GuestParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        current = await client.request("GET", guest_path(params.guest_type, params.node, params.guest_id) + "/status/current")
        config = await client.request("GET", guest_path(params.guest_type, params.node, params.guest_id) + "/config")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = {
        **current,
        **config,
        "connection_id": connection["connection_id"],
        "node": params.node,
        "vmid": params.guest_id,
        "guest_type": params.guest_type,
        "description": f"{params.guest_type.upper()} {params.guest_id} on {params.node}",
    }
    return ActionResult.success(data=data, summary=f"Fetched {params.guest_type.upper()} {params.guest_id} on {params.node}")


async def _finalize_create_task(client, connection: dict[str, Any], node: str, guest_type: str, guest_id: int, create_upid: Any,
                                *, start_after_create: bool, wait_for_completion: bool, timeout_seconds: int) -> ActionResult:
    create_status = await wait_for_task(client, node, create_upid, timeout_seconds=timeout_seconds) if wait_for_completion else {"status": "queued", "exitstatus": None}
    if start_after_create:
        start_upid = await client.request("POST", guest_path(guest_type, node, guest_id) + "/status/start")
        start_status = await wait_for_task(client, node, start_upid, timeout_seconds=timeout_seconds) if wait_for_completion else {"status": "queued", "exitstatus": None}
        description = f"{guest_type.upper()} {guest_id} created on {node} and started"
        data = {
            "connection_id": connection["connection_id"],
            "node": node,
            "task_id": start_upid,
            "task_type": f"create-and-start-{guest_type}",
            "status": start_status.get("status") or "queued",
            "exitstatus": start_status.get("exitstatus"),
            "description": description,
            "vmid": guest_id,
            "create_task_id": create_upid,
            "create_status": create_status.get("status"),
            "create_exitstatus": create_status.get("exitstatus"),
        }
        return ActionResult.success(data=data, summary=description)
    description = f"{guest_type.upper()} {guest_id} created on {node}"
    data = {
        "connection_id": connection["connection_id"],
        "node": node,
        "task_id": create_upid,
        "task_type": f"create-{guest_type}",
        "status": create_status.get("status") or "queued",
        "exitstatus": create_status.get("exitstatus"),
        "description": description,
        "vmid": guest_id,
    }
    return ActionResult.success(data=data, summary=description)


@chat.function("create_proxmox_vm", action_type="write", event="guest.created", data_model=ProxmoxTaskRecord,
               description="Create a Proxmox QEMU VM with live preflight checks for node, storage, bridge, VMID and optional ISO/cloud-init assets.")
async def create_proxmox_vm(ctx, params: CreateProxmoxVmParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        await ensure_node_exists(client, params.node)
        await ensure_storage_exists(client, params.node, params.qemu_scsi_storage)
        await ensure_bridge_exists(client, params.node, params.qemu_bridge)
        guest_id = params.guest_id or await next_guest_id(client)
        await ensure_guest_id_free(client, guest_id)
        if params.qemu_iso_file:
            if ":" in params.qemu_iso_file:
                iso_volid = parse_volume_reference(params.qemu_iso_file, field_name="qemu_iso_file")
                iso_storage = iso_volid.split(":", 1)[0]
                await ensure_storage_content_exists(client, params.node, iso_storage, volid=iso_volid, content_type="iso")
            else:
                if not params.qemu_iso_storage:
                    return ActionResult.error("qemu_iso_storage is required when qemu_iso_file is given without full volid.")
                await ensure_storage_content_exists(client, params.node, params.qemu_iso_storage, file_name=params.qemu_iso_file, content_type="iso")
        cloud_init_requested = any([
            params.qemu_ci_user,
            params.qemu_ci_password,
            params.qemu_ci_ssh_keys,
            params.qemu_ci_ipconfig0,
            params.qemu_ci_nameserver,
            params.qemu_ci_searchdomain,
            params.qemu_ci_upgrade,
            params.qemu_ci_custom,
            params.qemu_ci_storage,
        ])
        if cloud_init_requested:
            if not params.qemu_ci_storage:
                return ActionResult.error("qemu_ci_storage is required when using cloud-init fields.")
            await ensure_storage_exists(client, params.node, params.qemu_ci_storage)
        cores = ensure_positive_int(params.cores, "cores")
        sockets = ensure_positive_int(params.sockets, "sockets")
        memory_mb = ensure_positive_int(params.memory_mb, "memory_mb")
        disk_gb = ensure_positive_int(params.qemu_scsi_gb, "qemu_scsi_gb")
        balloon_mb = ensure_positive_int(params.qemu_balloon_mb, "qemu_balloon_mb")
        timeout_seconds = ensure_positive_int(params.start_timeout_seconds, "start_timeout_seconds") or 900
        payload: dict[str, Any] = {
            "vmid": guest_id,
            "name": params.name,
            "cores": cores,
            "memory": memory_mb,
            "sockets": sockets,
            "ostype": (params.qemu_ostype or "l26").strip(),
            "scsihw": "virtio-scsi-pci",
            "net0": build_qemu_net0(params.qemu_model, params.qemu_bridge, params.qemu_vlan_tag),
            "scsi0": build_scsi_disk_value(params.qemu_scsi_storage, disk_gb, params.qemu_scsi_format),
        }
        if params.description:
            payload["description"] = params.description
        clean_tags = normalize_tag_string(params.tags)
        if clean_tags:
            payload["tags"] = clean_tags
        onboot_flag = bool_to_proxmox_flag(params.onboot)
        if onboot_flag is not None:
            payload["onboot"] = onboot_flag
        if params.qemu_machine:
            payload["machine"] = params.qemu_machine.strip()
        if params.qemu_bios:
            payload["bios"] = params.qemu_bios.strip()
        agent_flag = bool_to_proxmox_flag(params.qemu_agent)
        if agent_flag is not None:
            payload["agent"] = agent_flag
        if params.qemu_cpu_type:
            payload["cpu"] = params.qemu_cpu_type.strip()
        if balloon_mb is not None:
            if balloon_mb > memory_mb:
                return ActionResult.error("qemu_balloon_mb cannot be greater than memory_mb.")
            payload["balloon"] = balloon_mb
        if params.qemu_iso_file:
            if ":" in params.qemu_iso_file:
                payload["ide2"] = parse_volume_reference(params.qemu_iso_file, field_name="qemu_iso_file")
            else:
                payload["ide2"] = parse_volume_reference(f"{params.qemu_iso_storage}:{params.qemu_iso_file}", field_name="qemu_iso_file", default_kind="iso")
        if cloud_init_requested:
            payload["ide3"] = f"{params.qemu_ci_storage.strip()}:cloudinit"
            if params.qemu_ci_user:
                payload["ciuser"] = params.qemu_ci_user
            if params.qemu_ci_password:
                payload["cipassword"] = params.qemu_ci_password
            if params.qemu_ci_ssh_keys:
                payload["sshkeys"] = params.qemu_ci_ssh_keys
            if params.qemu_ci_ipconfig0:
                payload["ipconfig0"] = params.qemu_ci_ipconfig0
            if params.qemu_ci_nameserver:
                payload["nameserver"] = params.qemu_ci_nameserver
            if params.qemu_ci_searchdomain:
                payload["searchdomain"] = params.qemu_ci_searchdomain
            ciupgrade_flag = bool_to_proxmox_flag(params.qemu_ci_upgrade)
            if ciupgrade_flag is not None:
                payload["ciupgrade"] = ciupgrade_flag
            if params.qemu_ci_custom:
                payload["cicustom"] = params.qemu_ci_custom
        payload["boot"] = params.qemu_boot_order.strip() if params.qemu_boot_order else ("order=ide2;scsi0;net0" if params.qemu_iso_file else "order=scsi0;net0")
        upid = await client.request("POST", f"/nodes/{params.node}/qemu", data=payload)
        return await _finalize_create_task(client, connection, params.node, "qemu", guest_id, upid,
                                           start_after_create=params.start_after_create,
                                           wait_for_completion=params.wait_for_completion,
                                           timeout_seconds=timeout_seconds)
    except ProxmoxError as e:
        return ActionResult.error(str(e))


@chat.function("create_proxmox_lxc", action_type="write", event="guest.created", data_model=ProxmoxTaskRecord,
               description="Create a Proxmox LXC container with live preflight checks for node, storage, bridge, template and CTID.")
async def create_proxmox_lxc(ctx, params: CreateProxmoxLxcParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        await ensure_node_exists(client, params.node)
        await ensure_storage_exists(client, params.node, params.lxc_rootfs_storage)
        await ensure_bridge_exists(client, params.node, params.lxc_bridge)
        template_volid = parse_volume_reference(params.lxc_ostemplate, field_name="lxc_ostemplate", default_kind="vztmpl")
        template_storage = template_volid.split(":", 1)[0]
        await ensure_storage_content_exists(client, params.node, template_storage, volid=template_volid, content_type="vztmpl")
        guest_id = params.guest_id or await next_guest_id(client)
        await ensure_guest_id_free(client, guest_id)
        cores = ensure_positive_int(params.cores, "cores")
        memory_mb = ensure_positive_int(params.memory_mb, "memory_mb")
        swap_mb = ensure_positive_int(params.swap_mb, "swap_mb")
        rootfs_gb = ensure_positive_int(params.lxc_rootfs_gb, "lxc_rootfs_gb")
        timeout_seconds = ensure_positive_int(params.start_timeout_seconds, "start_timeout_seconds") or 900
        payload: dict[str, Any] = {
            "vmid": guest_id,
            "hostname": params.lxc_hostname or params.name,
            "cores": cores,
            "memory": memory_mb,
            "swap": swap_mb,
            "ostemplate": template_volid,
            "rootfs": build_rootfs_value(params.lxc_rootfs_storage, rootfs_gb),
            "net0": build_lxc_net0(params.lxc_bridge, params.lxc_ip_config, vlan_tag=params.lxc_vlan_tag),
            "unprivileged": bool_to_proxmox_flag(params.lxc_unprivileged),
        }
        if params.description:
            payload["description"] = params.description
        clean_tags = normalize_tag_string(params.tags)
        if clean_tags:
            payload["tags"] = clean_tags
        onboot_flag = bool_to_proxmox_flag(params.onboot)
        if onboot_flag is not None:
            payload["onboot"] = onboot_flag
        if params.lxc_password:
            payload["password"] = params.lxc_password
        if params.lxc_ssh_public_keys:
            payload["ssh-public-keys"] = params.lxc_ssh_public_keys
        if params.lxc_nameserver:
            payload["nameserver"] = params.lxc_nameserver
        if params.lxc_searchdomain:
            payload["searchdomain"] = params.lxc_searchdomain
        upid = await client.request("POST", f"/nodes/{params.node}/lxc", data=payload)
        return await _finalize_create_task(client, connection, params.node, "lxc", guest_id, upid,
                                           start_after_create=params.start_after_create,
                                           wait_for_completion=params.wait_for_completion,
                                           timeout_seconds=timeout_seconds)
    except ProxmoxError as e:
        return ActionResult.error(str(e))


@chat.function("create_proxmox_guest", action_type="write", event="guest.created", data_model=ProxmoxTaskRecord,
               description="Legacy combined create flow. Prefer create_proxmox_vm or create_proxmox_lxc for a stricter and more correct create path.")
async def create_proxmox_guest(ctx, params: CreateGuestParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        guest_type = ensure_guest_type_for_create(params.guest_type)
        guest_id = params.guest_id or await next_guest_id(client)
        cores = ensure_positive_int(params.cores, "cores")
        memory_mb = ensure_positive_int(params.memory_mb, "memory_mb")
        start_timeout_seconds = ensure_positive_int(params.start_timeout_seconds, "start_timeout_seconds") or 900
        payload: dict[str, Any] = {
            "vmid": guest_id,
            "name": params.name,
        }
        if cores is not None:
            payload["cores"] = cores
        if memory_mb is not None:
            payload["memory"] = memory_mb
        if params.description:
            payload["description"] = params.description
        clean_tags = normalize_tag_string(params.tags)
        if clean_tags:
            payload["tags"] = clean_tags
        onboot_flag = bool_to_proxmox_flag(params.onboot)
        if onboot_flag is not None:
            payload["onboot"] = onboot_flag

        await ensure_node_exists(client, params.node)
        await ensure_guest_id_free(client, guest_id)

        if guest_type == "qemu":
            disk_gb = ensure_positive_int(params.qemu_scsi_gb, "qemu_scsi_gb")
            sockets = ensure_positive_int(params.sockets, "sockets")
            balloon_mb = ensure_positive_int(params.qemu_balloon_mb, "qemu_balloon_mb")
            if not params.qemu_scsi_storage or disk_gb is None:
                return ActionResult.error("For qemu creation, qemu_scsi_storage and qemu_scsi_gb are required.")
            await ensure_storage_exists(client, params.node, params.qemu_scsi_storage)
            await ensure_bridge_exists(client, params.node, params.qemu_bridge)
            payload["ostype"] = (params.qemu_ostype or "l26").strip()
            payload["scsihw"] = "virtio-scsi-pci"
            payload["net0"] = build_qemu_net0(params.qemu_model, params.qemu_bridge, params.qemu_vlan_tag)
            payload["scsi0"] = build_scsi_disk_value(params.qemu_scsi_storage, disk_gb, params.qemu_scsi_format)
            if sockets is not None:
                payload["sockets"] = sockets
            if params.qemu_machine:
                payload["machine"] = params.qemu_machine.strip()
            if params.qemu_bios:
                payload["bios"] = params.qemu_bios.strip()
            agent_flag = bool_to_proxmox_flag(params.qemu_agent)
            if agent_flag is not None:
                payload["agent"] = agent_flag
            if params.qemu_cpu_type:
                payload["cpu"] = params.qemu_cpu_type.strip()
            if balloon_mb is not None:
                if memory_mb is None:
                    return ActionResult.error("qemu_balloon_mb requires memory_mb to be set.")
                if balloon_mb > memory_mb:
                    return ActionResult.error("qemu_balloon_mb cannot be greater than memory_mb.")
                payload["balloon"] = balloon_mb
            if params.qemu_iso_file:
                if ":" in params.qemu_iso_file:
                    iso_volid = parse_volume_reference(params.qemu_iso_file, field_name="qemu_iso_file")
                    iso_storage = iso_volid.split(":", 1)[0]
                    await ensure_storage_content_exists(client, params.node, iso_storage, volid=iso_volid, content_type="iso")
                    payload["ide2"] = iso_volid
                else:
                    if not params.qemu_iso_storage:
                        return ActionResult.error("qemu_iso_storage is required when qemu_iso_file is given without full volid.")
                    await ensure_storage_content_exists(client, params.node, params.qemu_iso_storage, file_name=params.qemu_iso_file, content_type="iso")
                    payload["ide2"] = parse_volume_reference(
                        f"{params.qemu_iso_storage}:{params.qemu_iso_file}",
                        field_name="qemu_iso_file",
                        default_kind="iso",
                    )
            cloud_init_requested = any([
                params.qemu_ci_user,
                params.qemu_ci_password,
                params.qemu_ci_ssh_keys,
                params.qemu_ci_ipconfig0,
                params.qemu_ci_nameserver,
                params.qemu_ci_searchdomain,
                params.qemu_ci_upgrade,
                params.qemu_ci_custom,
                params.qemu_ci_storage,
            ])
            if cloud_init_requested:
                if not params.qemu_ci_storage:
                    return ActionResult.error("qemu_ci_storage is required when using cloud-init fields.")
                await ensure_storage_exists(client, params.node, params.qemu_ci_storage)
                payload["ide3"] = f"{params.qemu_ci_storage.strip()}:cloudinit"
                if params.qemu_ci_user:
                    payload["ciuser"] = params.qemu_ci_user
                if params.qemu_ci_password:
                    payload["cipassword"] = params.qemu_ci_password
                if params.qemu_ci_ssh_keys:
                    payload["sshkeys"] = params.qemu_ci_ssh_keys
                if params.qemu_ci_ipconfig0:
                    payload["ipconfig0"] = params.qemu_ci_ipconfig0
                if params.qemu_ci_nameserver:
                    payload["nameserver"] = params.qemu_ci_nameserver
                if params.qemu_ci_searchdomain:
                    payload["searchdomain"] = params.qemu_ci_searchdomain
                ciupgrade_flag = bool_to_proxmox_flag(params.qemu_ci_upgrade)
                if ciupgrade_flag is not None:
                    payload["ciupgrade"] = ciupgrade_flag
                if params.qemu_ci_custom:
                    payload["cicustom"] = params.qemu_ci_custom
            if params.qemu_boot_order:
                payload["boot"] = params.qemu_boot_order.strip()
            elif params.qemu_iso_file:
                payload["boot"] = "order=ide2;scsi0;net0"
            else:
                payload["boot"] = "order=scsi0;net0"
        else:
            rootfs_gb = ensure_positive_int(params.lxc_rootfs_gb, "lxc_rootfs_gb")
            swap_mb = ensure_positive_int(params.swap_mb, "swap_mb")
            if memory_mb is None:
                return ActionResult.error("For lxc creation, memory_mb is required.")
            if not params.lxc_ostemplate:
                return ActionResult.error("For lxc creation, lxc_ostemplate is required.")
            if not params.lxc_rootfs_storage or rootfs_gb is None:
                return ActionResult.error("For lxc creation, lxc_rootfs_storage and lxc_rootfs_gb are required.")
            payload["hostname"] = params.lxc_hostname or params.name
            payload["ostemplate"] = parse_volume_reference(params.lxc_ostemplate, field_name="lxc_ostemplate", default_kind="vztmpl")
            template_storage = payload["ostemplate"].split(":", 1)[0]
            await ensure_storage_exists(client, params.node, params.lxc_rootfs_storage)
            await ensure_bridge_exists(client, params.node, params.lxc_bridge)
            await ensure_storage_content_exists(client, params.node, template_storage, volid=payload["ostemplate"], content_type="vztmpl")
            payload["rootfs"] = build_rootfs_value(params.lxc_rootfs_storage, rootfs_gb)
            payload["unprivileged"] = bool_to_proxmox_flag(params.lxc_unprivileged)
            payload["net0"] = build_lxc_net0(params.lxc_bridge, params.lxc_ip_config, vlan_tag=params.lxc_vlan_tag)
            if swap_mb is not None:
                payload["swap"] = swap_mb
            if params.lxc_password:
                payload["password"] = params.lxc_password
            if params.lxc_ssh_public_keys:
                payload["ssh-public-keys"] = params.lxc_ssh_public_keys
            if params.lxc_nameserver:
                payload["nameserver"] = params.lxc_nameserver
            if params.lxc_searchdomain:
                payload["searchdomain"] = params.lxc_searchdomain

        upid = await client.request("POST", f"/nodes/{params.node}/{guest_type}", data=payload)
        create_status = await wait_for_task(client, params.node, upid, timeout_seconds=start_timeout_seconds) if params.wait_for_completion else {"status": "queued", "exitstatus": None}
        if params.start_after_create:
            start_upid = await client.request("POST", guest_path(guest_type, params.node, guest_id) + "/status/start")
            start_status = await wait_for_task(client, params.node, start_upid, timeout_seconds=start_timeout_seconds) if params.wait_for_completion else {"status": "queued", "exitstatus": None}
            description = f"{guest_type.upper()} {guest_id} created on {params.node} and started"
            data = {
                "connection_id": connection["connection_id"],
                "node": params.node,
                "task_id": start_upid,
                "task_type": f"create-and-start-{guest_type}",
                "status": start_status.get("status") or "queued",
                "exitstatus": start_status.get("exitstatus"),
                "description": description,
                "vmid": guest_id,
                "create_task_id": upid,
                "create_status": create_status.get("status"),
                "create_exitstatus": create_status.get("exitstatus"),
            }
            return ActionResult.success(data=data, summary=description)
        description = f"{guest_type.upper()} {guest_id} created on {params.node}"
        data = {
            "connection_id": connection["connection_id"],
            "node": params.node,
            "task_id": upid,
            "task_type": f"create-{guest_type}",
            "status": create_status.get("status") or "queued",
            "exitstatus": create_status.get("exitstatus"),
            "description": description,
            "vmid": guest_id,
        }
        return ActionResult.success(data=data, summary=description)
    except ProxmoxError as e:
        return ActionResult.error(str(e))


@chat.function("delete_proxmox_guest", action_type="destructive", event="guest.deleted", data_model=ProxmoxTaskRecord,
               description="Delete a Proxmox VM or container, with optional owned-volume destroy and unreferenced-disk purge.")
async def delete_proxmox_guest(ctx, params: DeleteGuestParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        await ensure_node_exists(client, params.node)
        await ensure_guest_exists(client, params.guest_type, params.node, params.guest_id)
        payload: dict[str, Any] = {}
        destroy_flag = bool_to_proxmox_flag(params.destroy_owned_volumes)
        if destroy_flag is not None:
            payload["destroy-unreferenced-disks"] = destroy_flag
        if params.purge_unreferenced_disks and params.guest_type == "qemu":
            payload["purge"] = 1
        upid = await client.request("DELETE", guest_path(params.guest_type, params.node, params.guest_id), data=payload or None)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = _task_payload(connection, params.node, upid, f"delete-{params.guest_type}", f"Deletion requested for {params.guest_type.upper()} {params.guest_id} on {params.node}")
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("clone_proxmox_guest", action_type="write", event="guest.cloned", data_model=ProxmoxTaskRecord,
               description="Clone an existing Proxmox VM or container to a new VMID/CTID.")
async def clone_proxmox_guest(ctx, params: CloneGuestParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        payload: dict[str, Any] = {
            "newid": params.new_guest_id,
            "full": 1 if params.full else 0,
        }
        if params.name:
            payload["name"] = params.name
        if params.target_node:
            payload["target"] = params.target_node
        if params.target_storage:
            payload["storage"] = params.target_storage
        if params.snapshot:
            payload["snapname"] = params.snapshot
        upid = await client.request("POST", guest_path(params.guest_type, params.node, params.source_guest_id) + "/clone", data=payload)
        target_node = params.target_node or params.node
        if params.start_after_clone:
            await wait_for_task(client, target_node, upid, timeout_seconds=900)
            start_upid = await client.request("POST", guest_path(params.guest_type, target_node, params.new_guest_id) + "/status/start")
            start_status = await wait_for_task(client, target_node, start_upid, timeout_seconds=900)
            description = f"Clone of {params.guest_type.upper()} {params.source_guest_id} to {params.new_guest_id} completed and started"
            data = {
                "connection_id": connection["connection_id"],
                "node": target_node,
                "task_id": start_upid,
                "task_type": f"clone-and-start-{params.guest_type}",
                "status": start_status.get("status") or "queued",
                "exitstatus": start_status.get("exitstatus"),
                "description": description,
                "clone_task_id": upid,
            }
            return ActionResult.success(data=data, summary=description)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    summary = f"Clone of {params.guest_type.upper()} {params.source_guest_id} to {params.new_guest_id} queued"
    data = _task_payload(connection, params.target_node or params.node, upid, f"clone-{params.guest_type}", summary)
    return ActionResult.success(data=data, summary=summary)


@chat.function("power_proxmox_guest", action_type="write", event="guest.power.changed", data_model=ProxmoxTaskRecord,
               description="Start, stop, shutdown, reboot, resume, or suspend a Proxmox VM or container.")
async def power_proxmox_guest(ctx, params: GuestPowerParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        action_path = guest_path(params.guest_type, params.node, params.guest_id) + f"/status/{params.action}"
        upid = await client.request("POST", action_path)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = _task_payload(connection, params.node, upid, params.action, f"{params.action} requested for {params.guest_type.upper()} {params.guest_id} on {params.node}")
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("list_proxmox_snapshots", action_type="read", data_model=ProxmoxSnapshotList,
               description="List snapshots for a Proxmox VM or container.")
async def list_proxmox_snapshots(ctx, params: GuestParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        items = await client.request("GET", guest_path(params.guest_type, params.node, params.guest_id) + "/snapshot")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for item in items or []:
        rows.append({**item, "connection_id": connection["connection_id"], "node": params.node, "vmid": params.guest_id, "guest_type": params.guest_type})
    return ActionResult.success(data={"items": rows}, summary=f"{len(rows)} snapshot(s)")


@chat.function("create_proxmox_snapshot", action_type="write", event="guest.snapshot.created", data_model=ProxmoxTaskRecord,
               description="Create a snapshot for a Proxmox VM or container.")
async def create_proxmox_snapshot(ctx, params: SnapshotCreateParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        payload = {"snapname": params.snapshot}
        if params.description:
            payload["description"] = params.description
        if params.include_ram and params.guest_type == "qemu":
            payload["vmstate"] = 1
        upid = await client.request("POST", guest_path(params.guest_type, params.node, params.guest_id) + "/snapshot", data=payload)
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = _task_payload(connection, params.node, upid, "snapshot", f"Snapshot '{params.snapshot}' requested for {params.guest_type.upper()} {params.guest_id}")
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("delete_proxmox_snapshot", action_type="destructive", event="guest.snapshot.deleted", data_model=ProxmoxTaskRecord,
               description="Delete a snapshot from a Proxmox VM or container.")
async def delete_proxmox_snapshot(ctx, params: SnapshotDeleteParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        upid = await client.request("DELETE", guest_path(params.guest_type, params.node, params.guest_id) + f"/snapshot/{params.snapshot}")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = _task_payload(connection, params.node, upid, "snapshot-delete", f"Snapshot '{params.snapshot}' deletion requested for {params.guest_type.upper()} {params.guest_id}")
    return ActionResult.success(data=data, summary=data["description"])


@chat.function("list_proxmox_tasks", action_type="read", data_model=ProxmoxTaskList,
               description="List recent tasks on all nodes of a connected Proxmox environment.")
async def list_proxmox_tasks(ctx, params: ConnectionIdParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        nodes = await client.request("GET", "/nodes")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    rows = []
    for node in nodes or []:
        node_name = node.get("node")
        if not node_name:
            continue
        try:
            tasks = await client.request("GET", f"/nodes/{node_name}/tasks", params={"limit": 20})
        except ProxmoxError:
            continue
        for item in tasks or []:
            rows.append({
                "connection_id": connection["connection_id"],
                "node": node_name,
                "task_id": item.get("upid"),
                "task_type": item.get("type"),
                "starttime": item.get("starttime"),
                "endtime": item.get("endtime"),
                "user": item.get("user"),
                "exitstatus": item.get("exitstatus"),
                "status": item.get("status") or ("ok" if item.get("endtime") else "running"),
                "description": item.get("id") or item.get("upid") or item.get("status") or "task",
            })
    rows.sort(key=lambda x: x.get("starttime") or 0, reverse=True)
    return ActionResult.success(data={"items": rows[:100]}, summary=f"{min(len(rows), 100)} recent task(s)")


@chat.function("get_proxmox_task_status", action_type="read", data_model=ProxmoxTaskRecord,
               description="Check the status of one Proxmox task using its UPID.")
async def get_proxmox_task_status(ctx, params: TaskStatusParams) -> ActionResult:
    try:
        connection = await resolve_connection(ctx, params.connection_id)
        client = await build_client_from_connection(ctx, connection)
        status = await client.request("GET", f"/nodes/{params.node}/tasks/{params.task_id}/status")
    except ProxmoxError as e:
        return ActionResult.error(str(e))
    data = {
        **status,
        "connection_id": connection["connection_id"],
        "node": params.node,
        "task_id": params.task_id,
        "task_type": status.get("type") or status.get("status") or "task",
        "description": f"Task {params.task_id} on {params.node}",
    }
    return ActionResult.success(data=data, summary=f"Task {params.task_id}: {status.get('status') or status.get('exitstatus') or 'unknown'}")
