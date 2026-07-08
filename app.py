from __future__ import annotations

from imperal_sdk import Extension
from imperal_sdk.chat import ChatExtension

ext = Extension(
    "proxmox-connector",
    version="0.4.0",
    display_name="Proxmox Connector",
    description=(
        "Connect any Proxmox VE server or cluster with a URL plus an API token, "
        "then inspect nodes, virtual machines, containers, storage, snapshots and tasks from Imperal."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["store:read", "store:write", "secrets:read", "secrets:write"],
)

chat = ChatExtension(
    ext=ext,
    tool_name="tool_proxmox_connector_chat",
    description=(
        "Proxmox Connector — connect one or more Proxmox VE endpoints per user and manage them safely. "
        "Use connect_proxmox first, then inspect nodes, storage, guests, snapshots, tasks, and base create/clone flows."
    ),
)


@ext.health_check
async def health(ctx) -> dict:
    return {"status": "ok", "version": ext.version}


@ext.on_install
async def on_install(ctx):
    return None
