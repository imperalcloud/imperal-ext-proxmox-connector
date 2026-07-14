from __future__ import annotations

from typing import Any

from imperal_sdk import ui
from app import ext


NAV_ITEMS = [
    ("overview", "Overview", "LayoutDashboard"),
    ("connect", "Connect", "Plug"),
    ("connections", "Connections", "Server"),
    ("nodes", "Nodes", "Cpu"),
    ("storage", "Storage", "HardDrive"),
    ("guests", "Guests", "Monitor"),
    ("power", "Power", "Power"),
    ("snapshots", "Snapshots", "Camera"),
    ("clone", "Clone", "Copy"),
    ("delete", "Delete", "Trash2"),
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


def _safe_text(value: Any, fallback: str = "—") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _result_payload(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _extract_error_message(error: Any) -> str:
    if not error:
        return ""
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        return str(error.get("message") or error.get("detail") or error.get("error") or error)
    message = getattr(error, "message", None)
    if message:
        return str(message)
    detail = getattr(error, "detail", None)
    if detail:
        return str(detail)
    return str(error)


def _result_error(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, dict):
        error = _extract_error_message(result.get("error"))
        if error:
            return error
        summary = result.get("summary")
        if result.get("ok") is False and summary:
            return str(summary)
        return ""
    error = _extract_error_message(getattr(result, "error", None))
    if error:
        return error
    summary = getattr(result, "summary", None)
    ok_value = getattr(result, "ok", None)
    if ok_value is False and summary:
        return str(summary)
    return ""


async def _call_panel_action(ctx, action: str, **kwargs):
    try:
        result = await ctx.extensions.call("proxmox-connector", action, **kwargs)
    except Exception as exc:
        return None, str(exc)
    error = _result_error(result)
    if error:
        return result, error
    return result, ""


def _panel_connect_action() -> str:
    connect_fn = getattr(ext, "tool", None)
    if callable(connect_fn):
        try:
            connect_tool = connect_fn("connect_proxmox")
            action_name = getattr(connect_tool, "name", None)
            if action_name:
                return str(action_name)
        except Exception:
            pass
    return "connect_proxmox"


async def _connections(ctx):
    result, error = await _call_panel_action(ctx, "list_proxmox_connections")
    if error:
        return ui.Alert(title="Connections failed", message=error, type="error")

    items = _result_payload(result).get("items", [])
    if not items:
        return ui.Stack([
            ui.Empty(message="No Proxmox connections yet", icon="Server"),
            ui.Button(
                "Open connect form",
                icon="Plug",
                variant="primary",
                on_click=ui.Call("__panel__tools", panel="connect", _sidebar_panel="connect"),
            ),
        ], gap=2)

    rows = []
    for item in items:
        cid = _safe_text(item.get("connection_id") or item.get("id"), "")
        title = _safe_text(item.get("label") or item.get("title"), cid or "connection")
        subtitle = _safe_text(item.get("base_url") or cid)
        rows.append(ui.ListItem(
            id=cid or title,
            title=title,
            subtitle=subtitle,
            expandable=True,
            expanded_content=[
                ui.Stack([
                    ui.Text(_safe_text(item.get("description"), "No extra details")),
                    ui.Stack([
                        ui.Button(
                            "Test",
                            icon="Activity",
                            variant="secondary",
                            on_click=ui.Call("test_proxmox_connection", connection_id=cid),
                        ),
                        ui.Button(
                            "Load guests",
                            icon="Monitor",
                            variant="outline",
                            on_click=ui.Call("__panel__tools", panel="guests", connection_id=cid, _sidebar_panel="guests"),
                        ),
                        ui.Button(
                            "Load tasks",
                            icon="ListTodo",
                            variant="outline",
                            on_click=ui.Call("__panel__tools", panel="tasks", connection_id=cid, _sidebar_panel="tasks"),
                        ),
                        ui.Button(
                            "Delete",
                            icon="Trash2",
                            variant="danger",
                            on_click=ui.Call("disconnect_proxmox", connection_id=cid),
                        ),
                    ], direction="h", gap=2, wrap=True),
                ], gap=2),
            ],
        ))

    return ui.Stack([
        ui.Header(text="Saved connections", level=3),
        ui.List(items=rows),
    ], gap=2)


async def _guests(ctx, connection_id: str = "", node: str = "", guest_type: str = "all", status: str = ""):
    args = {"connection_id": connection_id, "guest_type": guest_type}
    if node:
        args["node"] = node
    if status:
        args["status"] = status

    result, error = await _call_panel_action(ctx, "list_proxmox_guests", **args)
    if error:
        return ui.Alert(title="Guests failed", message=error, type="error")

    items = _result_payload(result).get("items", [])
    rows = []
    for item in items:
        gid = _safe_text(item.get("id"), "")
        name = _safe_text(item.get("name") or item.get("title"), gid or "guest")
        subtitle = f"{_safe_text(item.get('guest_type'), 'guest')} · VMID {_safe_text(item.get('vmid'))} · {_safe_text(item.get('node'))} · {_safe_text(item.get('status'))}"
        item_node = _safe_text(item.get("node"), "")
        item_vmid = _safe_text(item.get("vmid"), "")
        item_gtype = _safe_text(item.get("guest_type"), "qemu")
        if item_gtype not in ("qemu", "lxc"):
            item_gtype = "qemu"
        rows.append(ui.ListItem(
            id=gid or name,
            title=name,
            subtitle=subtitle,
            expandable=True,
            expanded_content=[
                ui.Stack([
                    ui.Text(_safe_text(item.get("description"), "No extra details")),
                    ui.Stack([
                        ui.Button(
                            "Power",
                            icon="Power",
                            variant="outline",
                            on_click=ui.Call("__panel__tools", panel="power", connection_id=connection_id, node=item_node, guest_id=item_vmid, guest_type=item_gtype, _sidebar_panel="power"),
                        ),
                        ui.Button(
                            "Snapshots",
                            icon="Camera",
                            variant="outline",
                            on_click=ui.Call("__panel__tools", panel="snapshots", connection_id=connection_id, node=item_node, guest_id=item_vmid, guest_type=item_gtype, _sidebar_panel="snapshots"),
                        ),
                        ui.Button(
                            "Clone",
                            icon="Copy",
                            variant="outline",
                            on_click=ui.Call("__panel__tools", panel="clone", connection_id=connection_id, node=item_node, guest_id=item_vmid, guest_type=item_gtype, _sidebar_panel="clone"),
                        ),
                        ui.Button(
                            "Delete",
                            icon="Trash2",
                            variant="danger",
                            on_click=ui.Call("__panel__tools", panel="delete", connection_id=connection_id, node=item_node, guest_id=item_vmid, guest_type=item_gtype, _sidebar_panel="delete"),
                        ),
                    ], direction="h", gap=2, wrap=True),
                ], gap=2),
            ],
        ))

    return ui.Stack([
        ui.Header(text="Guests", level=3, subtitle=(connection_id or "first saved connection")),
        ui.Form(
            action="__panel__tools",
            submit_label="Refresh",
            defaults={"panel": "guests", "connection_id": connection_id, "_sidebar_panel": "guests"},
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
    result, error = await _call_panel_action(ctx, "list_proxmox_tasks", connection_id=connection_id)
    if error:
        return ui.Alert(title="Tasks failed", message=error, type="error")

    items = _result_payload(result).get("items", [])
    rows = []
    for item in items:
        task_id = _safe_text(item.get("task_id") or item.get("upid") or item.get("id"), "")
        title = _safe_text(item.get("task_type") or item.get("title"), "task")
        subtitle = f"{_safe_text(item.get('node'))} · {_safe_text(item.get('status'))} · {_safe_text(item.get('exitstatus'))}"
        rows.append(ui.ListItem(
            id=task_id or title,
            title=title,
            subtitle=subtitle,
            expandable=True,
            expanded_content=[ui.Text(_safe_text(item.get("description"), "No extra details"))],
        ))

    return ui.Stack([
        ui.Header(text="Recent tasks", level=3, subtitle=(connection_id or "first saved connection")),
        ui.List(items=rows) if rows else ui.Empty(message="No recent tasks", icon="ListTodo"),
    ], gap=2)


async def _nodes(ctx, connection_id: str = ""):
    result, error = await _call_panel_action(ctx, "list_proxmox_nodes", connection_id=connection_id)
    if error:
        return ui.Alert(title="Nodes failed", message=error, type="error")

    items = _result_payload(result).get("items", [])
    rows = []
    for item in items:
        node_name = _safe_text(item.get("node"), "node")
        cpu = item.get("cpu")
        maxcpu = item.get("maxcpu")
        mem = item.get("mem")
        maxmem = item.get("maxmem")
        cpu_text = f"{round(float(cpu) * 100, 1)}%" if isinstance(cpu, (int, float)) else "—"
        mem_text = (
            f"{round(mem / (1024**3), 1)}G / {round(maxmem / (1024**3), 1)}G"
            if isinstance(mem, (int, float)) and isinstance(maxmem, (int, float)) and maxmem
            else "—"
        )
        subtitle = f"{_safe_text(item.get('status'))} · CPU {cpu_text} of {_safe_text(maxcpu)} · RAM {mem_text}"
        rows.append(ui.ListItem(
            id=node_name,
            title=node_name,
            subtitle=subtitle,
            expandable=True,
            expanded_content=[
                ui.Stack([
                    ui.Button(
                        "View storage",
                        icon="HardDrive",
                        variant="outline",
                        on_click=ui.Call("__panel__tools", panel="storage", connection_id=connection_id, node=node_name, _sidebar_panel="storage"),
                    ),
                    ui.Button(
                        "View guests",
                        icon="Monitor",
                        variant="outline",
                        on_click=ui.Call("__panel__tools", panel="guests", connection_id=connection_id, node=node_name, _sidebar_panel="guests"),
                    ),
                ], direction="h", gap=2, wrap=True),
            ],
        ))

    return ui.Stack([
        ui.Header(text="Cluster nodes", level=3, subtitle=(connection_id or "first saved connection")),
        ui.Form(
            action="__panel__tools",
            submit_label="Refresh",
            defaults={"panel": "nodes", "connection_id": connection_id, "_sidebar_panel": "nodes"},
            children=[
                ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
            ],
        ),
        ui.List(items=rows) if rows else ui.Empty(message="No nodes found", icon="Cpu"),
    ], gap=2)


async def _storage(ctx, connection_id: str = "", node: str = ""):
    args = {"connection_id": connection_id}
    if node:
        args["node"] = node

    result, error = await _call_panel_action(ctx, "list_proxmox_storage", **args)
    if error:
        return ui.Alert(title="Storage failed", message=error, type="error")

    items = _result_payload(result).get("items", [])
    rows = []
    for item in items:
        storage_id = _safe_text(item.get("storage"), "storage")
        used = item.get("used")
        total = item.get("total")
        used_text = (
            f"{round(used / (1024**3), 1)}G / {round(total / (1024**3), 1)}G"
            if isinstance(used, (int, float)) and isinstance(total, (int, float)) and total
            else "—"
        )
        subtitle = f"{_safe_text(item.get('node'))} · {_safe_text(item.get('type'))} · {used_text} · content: {_safe_text(item.get('content'))}"
        rows.append(ui.ListItem(
            id=f"{_safe_text(item.get('node'))}:{storage_id}",
            title=storage_id,
            subtitle=subtitle,
            expandable=True,
            expanded_content=[ui.Text(_safe_text(item.get("description"), "No extra details"))],
        ))

    return ui.Stack([
        ui.Header(text="Storage", level=3, subtitle=(connection_id or "first saved connection")),
        ui.Form(
            action="__panel__tools",
            submit_label="Refresh",
            defaults={"panel": "storage", "connection_id": connection_id, "_sidebar_panel": "storage"},
            children=[
                ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                ui.Input(param_name="node", value=node, placeholder="Node filter (optional)"),
            ],
        ),
        ui.List(items=rows) if rows else ui.Empty(message="No storage found", icon="HardDrive"),
    ], gap=2)


async def _overview_page(ctx):
    live_card = None
    connections_result, connections_error = await _call_panel_action(ctx, "list_proxmox_connections")
    connections = _result_payload(connections_result).get("items", []) if not connections_error else []

    if connections:
        status_result, status_error = await _call_panel_action(ctx, "get_proxmox_status")
        if status_error:
            live_card = ui.Alert(title="Cluster status unavailable", message=status_error, type="warning")
        else:
            s = _result_payload(status_result)
            live_card = ui.Card(
                title=_safe_text(s.get("cluster_name"), "Connected cluster"),
                content=ui.Stats(children=[
                    ui.Stat(label="Nodes online", value=f"{_safe_text(s.get('nodes_online'), '0')}/{_safe_text(s.get('nodes_total'), '0')}", color=("green" if s.get("status") == "ok" else "yellow")),
                    ui.Stat(label="Guests running", value=f"{_safe_text(s.get('guests_running'), '0')}/{_safe_text(s.get('guests_total'), '0')}", color="blue"),
                    ui.Stat(label="QEMU VMs", value=_safe_text(s.get("qemu_total"), "0"), color="purple"),
                    ui.Stat(label="LXC containers", value=_safe_text(s.get("lxc_total"), "0"), color="purple"),
                    ui.Stat(label="Storage entries", value=_safe_text(s.get("storage_total"), "0"), color="gray"),
                    ui.Stat(label="Status", value=_safe_text(s.get("status"), "unknown"), color=("green" if s.get("status") == "ok" else "yellow")),
                ], columns=2),
            )
    else:
        live_card = ui.Alert(
            title="No Proxmox connection yet",
            message="Connect a Proxmox host or cluster below to see live nodes, guests, and storage status here.",
            type="info",
        )

    return ui.Stack([
        ui.Header(
            text="Proxmox Connector",
            level=3,
            subtitle="Manage your Proxmox VE cluster from Imperal with stricter forms, safer validation, and clearer results.",
        ),
        live_card,
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
            ui.Button("Connect now", icon="Plug", variant="primary", on_click=ui.Call("__panel__tools", panel="connect", _sidebar_panel="connect")),
            ui.Button("Open connections", icon="Server", variant="outline", on_click=ui.Call("__panel__tools", panel="connections", _sidebar_panel="connections")),
            ui.Button("View nodes", icon="Cpu", variant="outline", on_click=ui.Call("__panel__tools", panel="nodes", _sidebar_panel="nodes")),
            ui.Button("View storage", icon="HardDrive", variant="outline", on_click=ui.Call("__panel__tools", panel="storage", _sidebar_panel="storage")),
            ui.Button("Browse guests", icon="Monitor", variant="outline", on_click=ui.Call("__panel__tools", panel="guests", _sidebar_panel="guests")),
            ui.Button("Create VM", icon="PlusSquare", variant="outline", on_click=ui.Call("__panel__tools", panel="create-vm", _sidebar_panel="create-vm")),
            ui.Button("Create LXC", icon="Package", variant="outline", on_click=ui.Call("__panel__tools", panel="create-lxc", _sidebar_panel="create-lxc")),
        ], direction="h", gap=2, wrap=True),
    ], gap=2)


def _connect_page():
    return ui.Stack([
        ui.Header(text="Connect Proxmox", level=3, subtitle="API token only. Password login is disabled in this connector for safety."),
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
            action=_panel_connect_action(),
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


def _power_page(connection_id: str = "", node: str = "", guest_id: str = "", guest_type: str = "qemu"):
    return ui.Stack([
        ui.Header(text="Guest power actions", level=3),
        ui.Form(
            action="power_proxmox_guest",
            submit_label="Run power action",
            defaults={"connection_id": connection_id, "node": node, "guest_id": guest_id},
            children=[
                ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                ui.Input(param_name="node", value=node, placeholder="Node name"),
                ui.Input(param_name="guest_id", value=guest_id, placeholder="VMID / CTID"),
                ui.Select(
                    param_name="guest_type",
                    value=guest_type or "qemu",
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


def _snapshots_page(connection_id: str = "", node: str = "", guest_id: str = "", guest_type: str = "qemu"):
    gtype = guest_type or "qemu"
    return ui.Stack([
        ui.Header(text="Snapshots", level=3),
        ui.Card(
            title="Create snapshot",
            content=ui.Form(
                action="create_proxmox_snapshot",
                submit_label="Create snapshot",
                defaults={"connection_id": connection_id, "node": node, "guest_id": guest_id},
                children=[
                    ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", value=node, placeholder="Node name"),
                    ui.Input(param_name="guest_id", value=guest_id, placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value=gtype,
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
                defaults={"connection_id": connection_id, "node": node, "guest_id": guest_id},
                children=[
                    ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", value=node, placeholder="Node name"),
                    ui.Input(param_name="guest_id", value=guest_id, placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value=gtype,
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
                defaults={"connection_id": connection_id, "node": node, "guest_id": guest_id},
                children=[
                    ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                    ui.Input(param_name="node", value=node, placeholder="Node name"),
                    ui.Input(param_name="guest_id", value=guest_id, placeholder="VMID / CTID"),
                    ui.Select(
                        param_name="guest_type",
                        value=gtype,
                        options=[
                            {"value": "qemu", "label": "QEMU VM"},
                            {"value": "lxc", "label": "LXC container"},
                        ],
                    ),
                ],
            ),
        ),
    ], gap=2)


def _clone_page(connection_id: str = "", node: str = "", guest_id: str = "", guest_type: str = "qemu"):
    return ui.Stack([
        ui.Header(text="Clone guest", level=3, subtitle="Duplicate an existing VM or container to a new VMID/CTID."),
        ui.Alert(
            title="Full vs linked clone",
            message="Full clone copies all disk data and can move to a different storage/node. Linked clone (full=false) is faster but stays dependent on the source, and only works where the storage supports it.",
            type="info",
        ),
        ui.Form(
            action="clone_proxmox_guest",
            submit_label="Clone guest",
            defaults={"full": True, "start_after_clone": False, "connection_id": connection_id, "node": node, "source_guest_id": guest_id},
            children=[
                ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                ui.Input(param_name="node", value=node, placeholder="Source node"),
                ui.Select(
                    param_name="guest_type",
                    value=guest_type or "qemu",
                    options=[
                        {"value": "qemu", "label": "QEMU VM"},
                        {"value": "lxc", "label": "LXC container"},
                    ],
                ),
                ui.Input(param_name="source_guest_id", value=guest_id, placeholder="Source VMID / CTID"),
                ui.Input(param_name="new_guest_id", placeholder="New VMID / CTID"),
                ui.Input(param_name="name", placeholder="New guest name (optional)"),
                ui.Input(param_name="target_node", placeholder="Target node (optional; empty = same node)"),
                ui.Input(param_name="target_storage", placeholder="Target storage (optional)"),
                ui.Input(param_name="snapshot", placeholder="Clone from snapshot (optional)"),
                ui.Toggle(label="Full clone", value=True, param_name="full"),
                ui.Toggle(label="Start after clone", value=False, param_name="start_after_clone"),
            ],
        ),
    ], gap=2)


def _delete_page(connection_id: str = "", node: str = "", guest_id: str = "", guest_type: str = "qemu"):
    return ui.Stack([
        ui.Header(text="Delete guest", level=3, subtitle="Permanently remove a VM or container. This cannot be undone."),
        ui.Alert(
            title="Destructive action",
            message="This stops and deletes the guest. By default owned storage volumes are destroyed with it. Double-check node, guest type, and ID before submitting.",
            type="warning",
        ),
        ui.Form(
            action="delete_proxmox_guest",
            submit_label="Delete guest",
            defaults={"destroy_owned_volumes": True, "purge_unreferenced_disks": False, "connection_id": connection_id, "node": node, "guest_id": guest_id},
            children=[
                ui.Input(param_name="connection_id", value=connection_id, placeholder="Connection ID (optional)"),
                ui.Input(param_name="node", value=node, placeholder="Node name"),
                ui.Select(
                    param_name="guest_type",
                    value=guest_type or "qemu",
                    options=[
                        {"value": "qemu", "label": "QEMU VM"},
                        {"value": "lxc", "label": "LXC container"},
                    ],
                ),
                ui.Input(param_name="guest_id", value=guest_id, placeholder="VMID / CTID"),
                ui.Toggle(label="Destroy owned storage volumes", value=True, param_name="destroy_owned_volumes"),
                ui.Toggle(label="Purge unreferenced disks", value=False, param_name="purge_unreferenced_disks"),
            ],
        ),
    ], gap=2)


def _create_vm_page():
    return ui.Stack([
        ui.Header(text="Create QEMU VM", level=3, subtitle="For full virtual machines with their own kernel, virtual hardware, and optional ISO or cloud-init setup."),
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
        ui.Header(text="Create LXC container", level=3, subtitle="For lightweight system containers that share the host kernel and usually start faster with less overhead."),
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
    if panel == "nodes":
        return await _nodes(ctx, connection_id=connection_id)
    if panel == "storage":
        return await _storage(ctx, connection_id=connection_id, node=node)
    if panel == "guests":
        return await _guests(ctx, connection_id=connection_id, node=node, guest_type=guest_type, status=status)
    if panel == "power":
        return _power_page(connection_id=connection_id, node=node, guest_id=kwargs.get("guest_id", ""), guest_type=(guest_type if guest_type in ("qemu", "lxc") else "qemu"))
    if panel == "snapshots":
        return _snapshots_page(connection_id=connection_id, node=node, guest_id=kwargs.get("guest_id", ""), guest_type=(guest_type if guest_type in ("qemu", "lxc") else "qemu"))
    if panel == "clone":
        return _clone_page(connection_id=connection_id, node=node, guest_id=kwargs.get("guest_id", ""), guest_type=(guest_type if guest_type in ("qemu", "lxc") else "qemu"))
    if panel == "delete":
        return _delete_page(connection_id=connection_id, node=node, guest_id=kwargs.get("guest_id", ""), guest_type=(guest_type if guest_type in ("qemu", "lxc") else "qemu"))
    if panel == "create-vm":
        return _create_vm_page()
    if panel == "create-lxc":
        return _create_lxc_page()
    if panel == "tasks":
        return await _tasks(ctx, connection_id=connection_id)
    return await _overview_page(ctx)
