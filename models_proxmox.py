from __future__ import annotations

from typing import Any, Optional

from pydantic import Field, model_validator

from imperal_sdk import sdl


class ProxmoxConnectionRecord(sdl.Entity):
    connection_id: Optional[str] = None
    label: Optional[str] = None
    base_url: Optional[str] = None
    cluster_name: Optional[str] = None
    auth_mode: Optional[str] = None
    tls_verify: Optional[bool] = None
    username: Optional[str] = None
    token_id: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            data["id"] = data.get("connection_id") or data.get("id") or ""
            data.setdefault("title", data.get("label") or data.get("cluster_name") or data.get("base_url") or "Connection")
            data.setdefault("kind", "proxmox_connection")
        return data


class ProxmoxConnectionList(sdl.EntityList[ProxmoxConnectionRecord]):
    pass


class ProxmoxNodeRecord(sdl.Entity):
    connection_id: Optional[str] = None
    node: Optional[str] = None
    uptime: Optional[int] = None
    cpu: Optional[float] = None
    maxcpu: Optional[int] = None
    mem: Optional[int] = None
    maxmem: Optional[int] = None
    disk: Optional[int] = None
    maxdisk: Optional[int] = None
    level: Optional[str] = None
    ssl_fingerprint: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            node = data.get("node") or data.get("title") or "node"
            cid = data.get("connection_id") or "default"
            data["id"] = data.get("id") or f"{cid}:{node}"
            data.setdefault("title", node)
            data.setdefault("kind", "proxmox_node")
        return data


class ProxmoxNodeList(sdl.EntityList[ProxmoxNodeRecord]):
    pass


class ProxmoxStorageRecord(sdl.Entity):
    connection_id: Optional[str] = None
    node: Optional[str] = None
    storage: Optional[str] = None
    type: Optional[str] = None
    shared: Optional[int] = None
    enabled: Optional[int] = None
    active: Optional[int] = None
    avail: Optional[int] = None
    total: Optional[int] = None
    used: Optional[int] = None
    content: Optional[str] = None
    content_type: Optional[str] = None
    volid: Optional[str] = None
    size: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            cid = data.get("connection_id") or "default"
            node = data.get("node") or "node"
            storage = data.get("storage") or data.get("volid") or "storage"
            data["id"] = data.get("id") or f"{cid}:{node}:{storage}"
            data.setdefault("title", data.get("storage") or data.get("volid") or storage)
            data.setdefault("kind", "proxmox_storage")
        return data


class ProxmoxStorageList(sdl.EntityList[ProxmoxStorageRecord]):
    pass


class ProxmoxGuestRecord(sdl.Entity):
    connection_id: Optional[str] = None
    node: Optional[str] = None
    vmid: Optional[int] = None
    guest_type: Optional[str] = None
    name: Optional[str] = None
    cpu: Optional[float] = None
    cpus: Optional[int] = None
    mem: Optional[int] = None
    maxmem: Optional[int] = None
    disk: Optional[int] = None
    maxdisk: Optional[int] = None
    uptime: Optional[int] = None
    lock: Optional[str] = None
    template: Optional[int] = None
    tags: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            cid = data.get("connection_id") or "default"
            node = data.get("node") or "node"
            vmid = data.get("vmid") or data.get("guest_id") or "guest"
            data["id"] = data.get("id") or f"{cid}:{node}:{vmid}"
            data.setdefault("title", data.get("name") or f"{data.get('guest_type', 'guest').upper()} {vmid}")
            data.setdefault("kind", "proxmox_guest")
        return data


class ProxmoxGuestList(sdl.EntityList[ProxmoxGuestRecord]):
    pass


class ProxmoxSnapshotRecord(sdl.Entity):
    connection_id: Optional[str] = None
    node: Optional[str] = None
    vmid: Optional[int] = None
    guest_type: Optional[str] = None
    snapshot: Optional[str] = None
    snaptime: Optional[int] = None
    description: Optional[str] = None
    parent: Optional[str] = None
    vmstate: Optional[int] = None
    status: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            cid = data.get("connection_id") or "default"
            node = data.get("node") or "node"
            vmid = data.get("vmid") or "guest"
            snap = data.get("snapshot") or data.get("name") or "snapshot"
            data["id"] = data.get("id") or f"{cid}:{node}:{vmid}:{snap}"
            data.setdefault("title", snap)
            data.setdefault("kind", "proxmox_snapshot")
        return data


class ProxmoxSnapshotList(sdl.EntityList[ProxmoxSnapshotRecord]):
    pass


class ProxmoxTaskRecord(sdl.Entity):
    connection_id: Optional[str] = None
    node: Optional[str] = None
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    starttime: Optional[int] = None
    endtime: Optional[int] = None
    user: Optional[str] = None
    exitstatus: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            cid = data.get("connection_id") or "default"
            node = data.get("node") or "node"
            upid = data.get("task_id") or data.get("upid") or data.get("id") or "task"
            data["id"] = upid if isinstance(upid, str) and upid.startswith("UPID:") else f"{cid}:{node}:{upid}"
            data.setdefault("title", data.get("task_type") or data.get("status") or "task")
            data.setdefault("kind", "proxmox_task")
        return data


class ProxmoxTaskList(sdl.EntityList[ProxmoxTaskRecord]):
    pass


class ProxmoxStatusRecord(sdl.Entity):
    connection_id: Optional[str] = None
    base_url: Optional[str] = None
    cluster_name: Optional[str] = None
    nodes_online: Optional[int] = None
    nodes_total: Optional[int] = None
    guests_running: Optional[int] = None
    guests_total: Optional[int] = None
    qemu_total: Optional[int] = None
    lxc_total: Optional[int] = None
    storage_total: Optional[int] = None
    status: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _canon(cls, data: Any):
        if isinstance(data, dict):
            cid = data.get("connection_id") or data.get("id") or "default"
            data["id"] = cid
            data.setdefault("title", data.get("cluster_name") or data.get("base_url") or "Proxmox status")
            data.setdefault("kind", "proxmox_status")
        return data


class ConnectionParams(sdl.Schema):
    connection_id: str = Field(description="Saved Proxmox connection identifier")
