from __future__ import annotations

from imperal_sdk import ui

from app import ext


@ext.panel("proxmox")
async def panel_proxmox(ctx):
    return ui.Page(
        title="Proxmox Connector",
        children=[
            ui.Section(
                title="What this extension does",
                children=[
                    ui.Markdown(
                        content=(
                            "Connect your own Proxmox VE with either an API token or a username/password, "
                            "then manage nodes, storage, guests, snapshots, tasks, and safe base create flows from Imperal.\n\n"
                            "Recommended first step in chat: `connect_proxmox`."
                        )
                    )
                ],
            ),
            ui.Section(
                title="Included tools",
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
                            "- `create_proxmox_guest`\n"
                            "- `clone_proxmox_guest`\n"
                            "- `power_proxmox_guest`\n"
                            "- `list_proxmox_snapshots`\n"
                            "- `create_proxmox_snapshot`\n"
                            "- `delete_proxmox_snapshot`\n"
                            "- `list_proxmox_tasks`\n"
                            "- `get_proxmox_task_status`\n"
                        )
                    )
                ],
            ),
        ],
    )
