from __future__ import annotations

from imperal_sdk import ui
from app import ext


NAV_ITEMS = [
    ("overview", "Overview", "LayoutDashboard"),
    ("connect", "Connect", "Plug"),
    ("connections", "Connections", "Server"),
    ("guests", "Guests", "Monitor"),
    ("power", "Power", "Power"),
    ("snapshots", "Snapshots", "Camera"),
    ("create-vm", "Create VM", "PlusSquare"),
    ("create-lxc", "Create LXC", "Package"),
    ("tasks", "Tasks", "ListTodo"),
]


def _nav_item(active: str, panel: str, title: str, icon: str):
    return ui.Button(
        label=title,
        icon=icon,
        variant="primary" if active == panel else "outline",
        on_click=ui.Call("__panel__tools", panel=panel, _sidebar_panel=panel),
        disabled=active == panel,
    )


async def _connections(ctx):
    try:
        result = await ctx.extensions.call("list_proxmox_connections", {})
        items = result.get("items", []) if isinstance(result, dict) else []
        call_error = result.get("error") if isinstance(result, dict) else None
        if call_error:
            return ui.Alert(title="Connections failed", message=str(call_error), type="error")
    except Exception as exc:
        return ui.Alert(title="Connections failed", message=str(exc), type="error")

    if not items:
        return ui.Stack([
            ui.Empty(message="No Proxmox connections yet", icon="Server"),
            ui.Button("Open connect form", icon="Plug", variant="primary",
                      on_click=ui.Call("__panel__tools", panel="connect")),
        ], gap=2)

    rows = []
    for item in items:
        cid = item.get("id", "")
        title = item.get("title", cid or "connection")
        rows.append(ui.ListItem(
            id=cid or title,
            title=title,
            subtitle=cid,
            expandable=True,
            expanded_content=[
                ui.Stack([
                    ui.Button("Test", icon="Activity", variant="secondary",
                              on_click=ui.Call("test_proxmox_connection", connection_id=cid)),
                    ui.Button("Load guests", icon="Monitor", variant="outline",
                              on_click=ui.Call("__panel__tools", panel="guests", connection_id=cid)),
                    ui.Button("Load tasks", icon="ListTodo", variant="outline",
                              on_click=ui.Call("__panel__tools", panel="tasks", connection_id=cid)),
                    ui.Button("Delete", icon="Trash2", variant="danger",
                              on_click=ui.Call("disconnect_proxmox", connection_id=cid)),
                ], direction="h", gap=2, wrap=True),
            ],
        ))

    return ui.Stack([
        ui.Header("Saved connections", level=3),
        ui.List(items=rows),
    ], gap=2)


async def _guests(ctx, connection_id: str = "", node: str = "", guest_type: str = "all", status: str = ""):
    try:
        args = {"connection_id": connection_id, "guest_type": guest_type}
        if node:
            args["node"] = node
        if status:
            args["status"] = status
        result = await ctx.extensions.call("list_proxmox_guests", args)
        items = result.get("items", []) if isinstance(result, dict) else []
        call_error = result.get("error") if isinstance(result, dict) else None
        if call_error:
            return ui.Alert(title="Guests failed", message=str(call_error), type="error")
    except Exception as exc:
        return ui.Alert(title="Guests failed", message=str(exc), type="error")

    rows = []
    for item in items:
        gid = item.get("id", "")
        title = item.get("title", gid or "guest")
        rows.append(ui.ListItem(id=gid or title, title=title, subtitle=gid))

    return ui.Stack([
        ui.Header("Guests", level=3,
                  subtitle=(connection_id or "first saved connection")),
        ui.Form(
            action="__panel__tools",
            submit_label="Refresh",
            defaults={"panel": "guests", "connection_id": connection_id},
            children=[
                ui.Input(param_name="node", value=node, placeholder="Node (optional)"),
                ui.Select(
                    param_name="guest_type",
                    value=guest_type,
                    options=[
                        {"value": "all", "label": "All"},
                        {"value": "qemu", "label": "QEMU VMs"},
                        {"value": "lxc", "label": "LXC containers"},
                    ],
                ),
                ui.Input(param_name="status", value=status, placeholder="Status filter (optional)"),
            ],
        ),
        ui.List(items=rows) if rows else ui.Empty(message="No guests matched", icon="Monitor"),
    ], gap=2)


async def _tasks(ctx, connection_id: str = ""):
    try:
        result = await ctx.extensions.call("list_proxmox_tasks", {"connection_id": connection_id})
        items = result.get("items", []) if isinstance(result, dict) else []
        call_error = result.get("error") if isinstance(result, dict) else None
        if call_error:
            return ui.Alert(title="Tasks failed", message=str(call_error), type="error")
    except Exception as exc:
        return ui.Alert(title="Tasks failed", message=str(exc), type="error")

    rows = [ui.ListItem(id=i.get("id", ""), title=i.get("title", "task"), subtitle=i.get("id", "")) for i in items]
    return ui.Stack([
        ui.Header("Recent tasks", level=3, subtitle=(connection_id or "first saved connection")),
        ui.List(items=rows) if rows else ui.Empty(message="No recent tasks", icon="ListTodo"),
    ], gap=2)


def _overview_page():
    return ui.Stack([
        ui.Header(text="Proxmox Connector", level=3,
                  subtitle="Manage your Proxmox VE cluster from Imperal with stricter forms, safer validation, and clearer results."),
        ui.Card(
            title="What you can do here",
            content=ui.Stats(children=[
                ui.Stat(label="Connect", value="API token", color="blue"),
                ui.Stat(label="Inventory", value="Nodes / storage / guests", color="green"),
                ui.Stat(label="Operations", value="Power / snapshots / clone / delete", color="yellow"),
                ui.Stat(label="Provisioning", value="Dedicated VM + LXC flows", color="purple"),
            ], columns=2),
        ),
        ui.Alert(
            title="Recommended flow",
            message="1) Connect a Proxmox host or cluster. 2) Check nodes, storage, and templates/ISOs. 3) Create a VM or LXC with the dedicated form. The connector validates node, storage, bridge, IDs, and required assets before it sends the create request.",
            type="info",
        ),
        ui.Card(
            title="Why there are separate VM and LXC forms",
            content=ui.Stack([
                ui.Text("QEMU VMs and LXC containers need different required inputs, so this connector keeps them separate on purpose."),
                ui.Text("That means fewer wrong combinations, clearer explanations, and more useful errors when something is missing."),
            ], gap=1),
        ),
        ui.Stack([
            ui.Button("Connect now", icon="Plug", variant="primary",
                      on_click=ui.Call("__panel__tools", panel="connect")),
            ui.Button("Open connections", icon="Server", variant="outline",
                      on_click=ui.Call("__panel__tools", panel="connections")),
            ui.Button("Browse guests", icon="Monitor", variant="outline",
                      on_click=ui.Call("__panel__tools", panel="guests")),
            ui.Button("Create VM", icon="PlusSquare", variant="outline",
                      on_click=ui.Call("__panel__tools", panel="create-vm")),
            ui.Button("Create LXC", icon="Package", variant="outline",
                      on_click=ui.Call("__panel__tools", panel="create-lxc")),
        ], direction="h", gap=2, wrap=True),
    ], gap=2)


def _connect_page():
    return ui.Stack([
        ui.Header(text="Connect Proxmox", level=3,
                  subtitle="API token only. Password login is disabled in this connector for safety."),
        ui.Alert(
            title="Use three separate values",
            message="Fill the API user, the token name, and the API key separately. Example: API user = imperal-ext-us@pam, Token name = imperal-ext, API key = the token secret value.",
            type="info",
        ),
        ui.Card(
            title="Expected Proxmox auth format",
            content=ui.Stack([
                ui.Text("Authorization header sent by the connector:"),
                ui.Text("PVEAPIToken=<api_user>@<realm>!<token_name>=<api_key>"),
                ui.Text("Example: PVEAPIToken=imperal-ext-us@pam!imperal-ext=********"),
            ], gap=1),
        ),
        ui.Form(
            action="connect_proxmox",
            submit_label="Save connection",
            defaults={"auth_mode": "api_token", "realm": "pam", "tls_verify": True},
            children=[
                ui.Input(param_name="label", placeholder="Connection label (optional)"),
                ui.Input(param_name="base_url", placeholder="https://node1-us.webhostmost.com:8006"),
                ui.Input(param_name="api_user", placeholder="API user, for example imperal-ext-us@pam"),
                ui.Input(param_name="token_name", placeholder="Token name, for example imperal-ext"),
                ui.Password(param_name="api_key", placeholder="API key / token secret"),
                ui.Input(param_name="realm", value="pam", placeholder="Realm, only used if API user has no @realm"),
                ui.Toggle(label="Verify TLS certificates", value=True, param_name="tls_verify"),
            ],
        ),
    ], gap=2)


def _power_page():
    return ui.Stack([
        ui.Header(text="Guest power actions", level=3),
        ui.Form(
            action="power_proxmox_guest",
            submit_label="Run power action",
            children=[
                ui.Input(param_name="connection_id", placeholder="Connection ID (optional)"),
                ui.Input(param_name="node", placeholder="Node name"),
                ui.Input(param_name="guest_id", placeholder="VMID / CTID"),
                ui.Select(
                    param_name="guest_type",
                    value="qemu",
                    options=[
                        {"value": "qemu", "label": "QEMU VM"},
                        {"value": "lxc", "label": "LXC container"},
                    ],
                ),
                ui.Select(
                    param_name="action",
                    value="start",
                    options=[
                        {"value": "start", "label": "Start"},
                        {"value": "stop", "label": "Stop"},
                        {"value": "shutdown", "label": "Shutdown"},
                        {"value": "reboot", "label": "Reboot"},
                        {"value": "resume", "label": "Resume"},
                        {"value": "suspend", "label": "Suspend"},
                    ],
                ),
            ],
        ),
    ], gap=2)


def _snapshots_page():
    return ui.Stack([
        ui.Header(text="Snapshots", level=3),
        ui.Card(
            title="Create snapshot",
            content=ui.Form(
                action="create_proxmox_snapshot",
                submit_label="Create snapshot",
                children=[
                    ui.Input(param_name="connection_id", placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", placeholder="Node name"),
                    ui.Input(param_name="guest_id", placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value="qemu",
                        options=[
                            {"value": "qemu", "label": "QEMU VM"},
                            {"value": "lxc", "label": "LXC container"},
                        ],
                    ),
                    ui.Input(param_name="snapshot", placeholder="Snapshot name"),
                    ui.Input(param_name="description", placeholder="Description (optional)"),
                    ui.Toggle(label="Include RAM", value=False, param_name="include_ram"),
                ],
            ),
        ),
        ui.Card(
            title="Delete snapshot",
            content=ui.Form(
                action="delete_proxmox_snapshot",
                submit_label="Delete snapshot",
                children=[
                    ui.Input(param_name="connection_id", placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", placeholder="Node name"),
                    ui.Input(param_name="guest_id", placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value="qemu",
                        options=[
                            {"value": "qemu", "label": "QEMU VM"},
                            {"value": "lxc", "label": "LXC container"},
                        ],
                    ),
                    ui.Input(param_name="snapshot", placeholder="Snapshot name"),
                ],
            ),
        ),
        ui.Card(
            title="List snapshots",
            content=ui.Form(
                action="list_proxmox_snapshots",
                submit_label="Show snapshots",
                children=[
                    ui.Input(param_name="connection_id", placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", placeholder="Node name"),
                    ui.Input(param_name="guest_id", placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value="qemu",
                        options=[
                            {"value": "qemu", "label": "QEMU VM"},
                            {"value": "lxc", "label": "LXC container"},
                        ],
                    ),
                ],
            ),
        ),
    ], gap=2)


def _create_vm_page():
    return ui.Stack([
        ui.Header(text="Create QEMU VM", level=3,
                  subtitle="For full virtual machines with their own kernel, virtual hardware, and optional ISO or cloud-init setup."),
        ui.Alert(
            title="What is validated before create",
            message="The connector checks the node, VMID, target storage, bridge, and optional ISO/cloud-init storage before it submits the VM create task.",
            type="info",
        ),
        ui.Card(
            title="Required for a minimal VM",
            content=ui.Stack([
                ui.Text("You need: node, VM name, CPU cores, memory, disk storage, and disk size."),
                ui.Text("If you add an ISO by filename only, also fill ISO storage. If you use any cloud-init field, cloud-init storage becomes required."),
            ], gap=1),
        ),
        ui.Form(
            action="create_proxmox_vm",
            submit_label="Create VM",
            children=[
                ui.Input(param_name="connection_id", placeholder="Connection ID (optional; empty = first saved connection)"),
                ui.Input(param_name="node", placeholder="Node name, for example pve-1"),
                ui.Input(param_name="guest_id", placeholder="VMID (optional; empty = next free ID)"),
                ui.Input(param_name="name", placeholder="VM name, for example web-01"),
                ui.Input(param_name="cores", placeholder="CPU cores, for example 2"),
                ui.Input(param_name="memory_mb", placeholder="Memory in MB, for example 4096"),
                ui.Input(param_name="sockets", value="1", placeholder="CPU sockets, usually 1"),
                ui.Input(param_name="qemu_scsi_storage", placeholder="Disk storage, for example local-lvm"),
                ui.Input(param_name="qemu_scsi_gb", placeholder="Disk size in GB, for example 32"),
                ui.Input(param_name="qemu_bridge", value="vmbr0", placeholder="Bridge, for example vmbr0"),
                ui.Input(param_name="qemu_model", value="virtio", placeholder="NIC model, for example virtio"),
                ui.Input(param_name="qemu_ostype", value="l26", placeholder="Guest OS type, for example l26"),
                ui.Input(param_name="qemu_iso_storage", placeholder="ISO storage (optional, needed when ISO file is just a filename)"),
                ui.Input(param_name="qemu_iso_file", placeholder="ISO file or full volid, for example debian.iso or local:iso/debian.iso"),
                ui.Input(param_name="qemu_ci_storage", placeholder="Cloud-init storage (optional, required if any cloud-init field below is used)"),
                ui.Input(param_name="qemu_ci_user", placeholder="Cloud-init user (optional)"),
                ui.Password(param_name="qemu_ci_password", placeholder="Cloud-init password (optional)"),
                ui.Input(param_name="qemu_ci_ssh_keys", placeholder="Cloud-init SSH public keys (optional)"),
                ui.Input(param_name="qemu_ci_ipconfig0", placeholder="Cloud-init ipconfig0 (optional), for example ip=dhcp"),
                ui.Input(param_name="description", placeholder="Description (optional)"),
                ui.Input(param_name="tags", placeholder="Tags, comma-separated (optional)"),
                ui.Toggle(label="Enable QEMU guest agent", value=False, param_name="qemu_agent"),
                ui.Toggle(label="Start VM after create", value=False, param_name="start_after_create"),
                ui.Toggle(label="Wait for Proxmox task completion", value=True, param_name="wait_for_completion"),
            ],
        ),
    ], gap=2)


def _create_lxc_page():
    return ui.Stack([
        ui.Header(text="Create LXC container", level=3,
                  subtitle="For lightweight system containers that share the host kernel and usually start faster with less overhead."),
        ui.Alert(
            title="What is validated before create",
            message="The connector checks the node, CTID, rootfs storage, bridge, and the exact container template before it submits the LXC create task.",
            type="info",
        ),
        ui.Card(
            title="Required for a minimal container",
            content=ui.Stack([
                ui.Text("You need: node, container name, CPU cores, memory, template volid, rootfs storage, and rootfs size."),
                ui.Text("Template must be a real Proxmox volume reference such as local:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst."),
            ], gap=1),
        ),
        ui.Form(
            action="create_proxmox_lxc",
            submit_label="Create LXC",
            children=[
                ui.Input(param_name="connection_id", placeholder="Connection ID (optional; empty = first saved connection)"),
                ui.Input(param_name="node", placeholder="Node name, for example pve-1"),
                ui.Input(param_name="guest_id", placeholder="CTID (optional; empty = next free ID)"),
                ui.Input(param_name="name", placeholder="Container name, for example app-01"),
                ui.Input(param_name="cores", placeholder="CPU cores, for example 2"),
                ui.Input(param_name="memory_mb", placeholder="Memory in MB, for example 2048"),
                ui.Input(param_name="swap_mb", value="512", placeholder="Swap in MB, for example 512"),
                ui.Input(param_name="lxc_ostemplate", placeholder="Template volid, for example local:vztmpl/debian-12.tar.zst"),
                ui.Input(param_name="lxc_rootfs_storage", placeholder="Rootfs storage, for example local-lvm"),
                ui.Input(param_name="lxc_rootfs_gb", placeholder="Rootfs size in GB, for example 8"),
                ui.Input(param_name="lxc_bridge", value="vmbr0", placeholder="Bridge, for example vmbr0"),
                ui.Input(param_name="lxc_ip_config", value="dhcp", placeholder="IP config, for example dhcp or 192.168.1.50/24"),
                ui.Input(param_name="lxc_hostname", placeholder="Hostname (optional; empty = uses container name)"),
                ui.Password(param_name="lxc_password", placeholder="Root password (optional)"),
                ui.Input(param_name="lxc_ssh_public_keys", placeholder="SSH public keys (optional)"),
                ui.Input(param_name="description", placeholder="Description (optional)"),
                ui.Input(param_name="tags", placeholder="Tags, comma-separated (optional)"),
                ui.Toggle(label="Create as unprivileged container", value=True, param_name="lxc_unprivileged"),
                ui.Toggle(label="Start container after create", value=False, param_name="start_after_create"),
                ui.Toggle(label="Wait for Proxmox task completion", value=True, param_name="wait_for_completion"),
            ],
        ),
    ], gap=2)


@ext.panel("sidebar", slot="left", title="Proxmox", icon="Server")
async def proxmox_sidebar(ctx, panel: str = "overview", _sidebar_panel: str = "", **kwargs):
    active_panel = _sidebar_panel or panel or "overview"
    nav = [_nav_item(active_panel, key, title, icon) for key, title, icon in NAV_ITEMS]
    root = ui.Stack([
        ui.Header(text="Proxmox", level=3),
        ui.Stack(nav, direction="v", gap=1),
    ], gap=2)
    root.props["auto_action"] = ui.Call("__panel__tools", panel=active_panel, _sidebar_panel=active_panel)
    return root


@ext.panel("tools", slot="center", title="Proxmox Connector", icon="Server", center_overlay=True)
async def proxmox_tools(ctx,
                        panel: str = "overview",
                        connection_id: str = "",
                        node: str = "",
                        guest_type: str = "all",
                        status: str = "",
                        **kwargs):
    if panel == "connect":
        return _connect_page()
    if panel == "connections":
        return await _connections(ctx)
    if panel == "guests":
        return await _guests(ctx, connection_id=connection_id, node=node, guest_type=guest_type, status=status)
    if panel == "power":
        return _power_page()
    if panel == "snapshots":
        return _snapshots_page()
    if panel == "create-vm":
        return _create_vm_page()
    if panel == "create-lxc":
        return _create_lxc_page()
    if panel == "tasks":
        return await _tasks(ctx, connection_id=connection_id)
    return _overview_page()
