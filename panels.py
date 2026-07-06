from __future__ import annotations

from imperal_sdk import ui
from app import ext


def _nav_item(title: str, icon: str, active: str, panel: str):
    props = {
        "id": panel,
        "title": title,
        "icon": icon,
        "on_click": {
            "action": "call",
            "function": "__panel__tools",
            "params": {"panel": panel},
        },
    }
    if active == panel:
        props["selected"] = True
    return ui.base.UINode(type="ListItem", props=props)


@ext.panel("sidebar", slot="left", title="Proxmox", icon="Server")
async def proxmox_sidebar(ctx, panel: str = "overview", **kwargs):
    items = [
        _nav_item("Overview", "Info", panel, "overview"),
        _nav_item("Connect", "Plug", panel, "connect"),
        _nav_item("Tools", "Wrench", panel, "tools"),
    ]
    root = ui.List(items=items)
    root.props["auto_action"] = ui.Call("__panel__tools", panel=panel)
    return root


def _overview_page():
    return ui.Page(
        title="Proxmox Connector",
        children=[
            ui.Section(
                title="What this extension does",
                children=[
                    ui.Markdown(
                        content=(
                            "Connect your own Proxmox VE with either an API token or a username/password, "
                            "then manage nodes, storage, guests, snapshots, tasks, and safe create flows from Imperal."
                        )
                    )
                ],
            ),
            ui.Section(
                title="Recommended first step",
                children=[
                    ui.Markdown(content="Use chat or the tool runner with `connect_proxmox` to save your first endpoint.")
                ],
            ),
        ],
    )


def _connect_page():
    return ui.Page(
        title="Connect your Proxmox",
        children=[
            ui.Section(
                title="How to connect",
                children=[
                    ui.Markdown(
                        content=(
                            "Run `connect_proxmox` and provide:\n\n"
                            "- `base_url` — your Proxmox URL, for example `https://pve.example.com:8006`\n"
                            "- `auth_mode` — `api_token` or `password`\n"
                            "- `username` — Proxmox username like `root@pam` or service user\n"
                            "- token or password fields depending on auth mode\n"
                            "- optional `label` to name the connection"
                        )
                    )
                ],
            )
        ],
    )


def _tools_page():
    return ui.Page(
        title="Included tools",
        children=[
            ui.Section(
                title="Available functions",
                children=[
                    ui.Markdown(
                        content=(
                            "- `connect_proxmox`\n"
                            "- `list_proxmox_connections`\n"
                            "- `update_proxmox_connection`\n"
                            "- `disconnect_proxmox`\n"
                            "- `test_proxmox_connection`\n"
                            "- `get_proxmox_status`\n"
                            "- `list_proxmox_nodes`\n"
                            "- `list_proxmox_storage`\n"
                            "- `list_proxmox_storage_content`\n"
                            "- `list_proxmox_guests`\n"
                            "- `get_proxmox_guest`\n"
                            "- `create_proxmox_vm`\n"
                            "- `create_proxmox_lxc`\n"
                            "- `create_proxmox_guest`\n"
                            "- `delete_proxmox_guest`\n"
                            "- `clone_proxmox_guest`\n"
                            "- `power_proxmox_guest`\n"
                            "- `list_proxmox_snapshots`\n"
                            "- `create_proxmox_snapshot`\n"
                            "- `delete_proxmox_snapshot`\n"
                            "- `list_proxmox_tasks`\n"
                            "- `get_proxmox_task_status`"
                        )
                    )
                ],
            )
        ],
    )


@ext.panel("tools", slot="center", title="Proxmox Connector", icon="Server", center_overlay=True)
async def proxmox_tools(ctx, panel: str = "overview", **kwargs):
    if panel == "connect":
        return _connect_page()
    if panel == "tools":
        return _tools_page()
    return _overview_page()
