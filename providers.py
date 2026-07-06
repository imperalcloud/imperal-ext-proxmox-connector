from __future__ import annotations

import json
import os
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

CONNECTIONS_KEY = "proxmox_connections"
SECRET_PREFIX = "proxmox_conn_"


class ProxmoxError(Exception):
    pass


class ProxmoxClient:
    def __init__(self, base_url: str, headers: dict[str, str], tls_verify: bool = True, ticket: str = "", csrf_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.headers = headers.copy()
        self.tls_verify = tls_verify
        self.ticket = ticket
        self.csrf_token = csrf_token

    async def request(self, method: str, path: str, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> Any:
        headers = self.headers.copy()
        if self.ticket:
            cookie = f"PVEAuthCookie={self.ticket}"
            if headers.get("Cookie"):
                headers["Cookie"] = headers["Cookie"] + "; " + cookie
            else:
                headers["Cookie"] = cookie
        if self.csrf_token and method.upper() not in ("GET", "HEAD"):
            headers["CSRFPreventionToken"] = self.csrf_token
        url = f"{self.base_url}/api2/json{path}"
        async with httpx.AsyncClient(verify=self.tls_verify, timeout=20.0) as client:
            resp = await client.request(method.upper(), url, headers=headers, params=params, data=data)
        if resp.status_code >= 400:
            body = (resp.text or "").strip()
            raise ProxmoxError(f"HTTP {resp.status_code}: {body[:300] or '(empty body)'}")
        try:
            payload = resp.json()
        except Exception as e:
            raise ProxmoxError(f"Non-JSON response from Proxmox: {e}") from e
        if isinstance(payload, dict) and "errors" in payload:
            raise ProxmoxError(json.dumps(payload["errors"], ensure_ascii=False))
        return payload.get("data") if isinstance(payload, dict) and "data" in payload else payload


def _normalize_username_and_realm(username: str, realm: str) -> tuple[str, str, str]:
    raw_username = (username or "").strip()
    raw_realm = (realm or "pam").strip()
    if not raw_username:
        raise ProxmoxError("username is required")
    if "!" in raw_username:
        raise ProxmoxError("username must not include token id. Put only the Proxmox user into username, for example 'root@pam', and put the token name into token_id separately.")
    if "@" in raw_username:
        name, realm_from_username = raw_username.rsplit("@", 1)
        if not name.strip() or not realm_from_username.strip():
            raise ProxmoxError("username must be a valid Proxmox user like 'root@pam'")
        return raw_username, raw_username, realm_from_username.strip()
    if not raw_realm:
        raise ProxmoxError("realm is required when username has no @realm")
    user_at_realm = f"{raw_username}@{raw_realm}"
    return raw_username, user_at_realm, raw_realm


def _normalize_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip()
    if not base_url:
        raise ProxmoxError("base_url is required")
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    parsed = urlparse(base_url)
    if not parsed.netloc:
        raise ProxmoxError("Invalid Proxmox URL")
    netloc = parsed.netloc
    if ":" not in netloc:
        netloc = f"{netloc}:8006"
    return f"{parsed.scheme}://{netloc}"


async def _store_get(ctx, key: str, default: Any):
    if hasattr(ctx, "store") and hasattr(ctx.store, "get"):
        try:
            val = await ctx.store.get(key)
            return default if val in (None, "") else val
        except Exception:
            return default
    return default


async def _store_set(ctx, key: str, value: Any):
    if hasattr(ctx, "store") and hasattr(ctx.store, "set"):
        await ctx.store.set(key, value)
        return
    raise ProxmoxError("ctx.store.set is unavailable in this runtime")


async def _secret_set(ctx, name: str, value: str):
    if hasattr(ctx, "secrets") and hasattr(ctx.secrets, "set"):
        await ctx.secrets.set(name, value)
        return
    raise ProxmoxError("ctx.secrets.set is unavailable in this runtime")


async def _secret_get(ctx, name: str) -> str:
    if hasattr(ctx, "secrets") and hasattr(ctx.secrets, "get"):
        val = await ctx.secrets.get(name)
        return val or ""
    raise ProxmoxError("ctx.secrets.get is unavailable in this runtime")


async def _secret_delete(ctx, name: str):
    if hasattr(ctx, "secrets") and hasattr(ctx.secrets, "delete"):
        await ctx.secrets.delete(name)
        return
    # tolerate runtimes without delete


async def list_connections(ctx) -> list[dict[str, Any]]:
    data = await _store_get(ctx, CONNECTIONS_KEY, [])
    return data if isinstance(data, list) else []


async def save_connections(ctx, items: list[dict[str, Any]]):
    await _store_set(ctx, CONNECTIONS_KEY, items)


async def update_connection(ctx, connection_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    items = await list_connections(ctx)
    for idx, item in enumerate(items):
        if item.get("connection_id") == connection_id:
            merged = {**item, **updates}
            items[idx] = merged
            await save_connections(ctx, items)
            return merged
    raise ProxmoxError(f"Connection '{connection_id}' not found")


async def delete_connection(ctx, connection_id: str) -> dict[str, Any]:
    items = await list_connections(ctx)
    for idx, item in enumerate(items):
        if item.get("connection_id") == connection_id:
            removed = items.pop(idx)
            await save_connections(ctx, items)
            secret_name = removed.get("secret_name")
            if secret_name:
                await _secret_delete(ctx, secret_name)
            return removed
    raise ProxmoxError(f"Connection '{connection_id}' not found")


async def resolve_connection(ctx, connection_id: str = "") -> dict[str, Any]:
    items = await list_connections(ctx)
    if not items:
        raise ProxmoxError("No saved Proxmox connections. Use connect_proxmox first.")
    if connection_id:
        for item in items:
            if item.get("connection_id") == connection_id:
                return item
        raise ProxmoxError(f"Connection '{connection_id}' not found")
    return items[0]


async def build_client_from_connection(ctx, connection: dict[str, Any]) -> ProxmoxClient:
    auth_mode = connection.get("auth_mode")
    tls_verify = bool(connection.get("tls_verify", True))
    headers: dict[str, str] = {}
    ticket = ""
    csrf = ""
    if auth_mode == "api_token":
        token_secret = await _secret_get(ctx, connection["secret_name"])
        user_at_realm = connection.get("user_at_realm") or ""
        token_id = connection.get("token_id") or ""
        headers["Authorization"] = f"PVEAPIToken={user_at_realm}!{token_id}={token_secret}"
    elif auth_mode == "password":
        password = await _secret_get(ctx, connection["secret_name"])
        payload = {
            "username": connection.get("user_at_realm") or "",
            "password": password,
        }
        async with httpx.AsyncClient(verify=tls_verify, timeout=20.0) as client:
            resp = await client.post(f"{connection['base_url']}/api2/json/access/ticket", data=payload)
        if resp.status_code >= 400:
            raise ProxmoxError(f"Login failed: HTTP {resp.status_code}: {(resp.text or '')[:300]}")
        data = resp.json().get("data") or {}
        ticket = data.get("ticket") or ""
        csrf = data.get("CSRFPreventionToken") or ""
        if not ticket:
            raise ProxmoxError("Login failed: no auth ticket returned")
    else:
        raise ProxmoxError(f"Unsupported auth_mode '{auth_mode}'")
    return ProxmoxClient(connection["base_url"], headers=headers, tls_verify=tls_verify, ticket=ticket, csrf_token=csrf)


async def connect_and_persist(
    ctx,
    *,
    base_url: str,
    auth_mode: str,
    realm: str,
    username: str,
    password: str,
    token_id: str,
    token_secret: str,
    tls_verify: bool,
    label: str,
) -> dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    auth_mode = (auth_mode or "").strip().lower()
    username = (username or "").strip()
    token_id = (token_id or "").strip()
    label = (label or "").strip()

    if auth_mode not in {"api_token", "password"}:
        raise ProxmoxError("auth_mode must be 'api_token' or 'password'")
    raw_username, user_at_realm, normalized_realm = _normalize_username_and_realm(username, realm)
    if auth_mode == "password" and not password:
        raise ProxmoxError("password is required when auth_mode=password")
    if auth_mode == "api_token" and (not token_id or not token_secret):
        raise ProxmoxError("token_id and token_secret are required when auth_mode=api_token")

    headers: dict[str, str] = {}
    ticket = ""
    csrf = ""
    if auth_mode == "api_token":
        headers["Authorization"] = f"PVEAPIToken={user_at_realm}!{token_id}={token_secret}"
    else:
        async with httpx.AsyncClient(verify=tls_verify, timeout=20.0) as client:
            resp = await client.post(f"{base_url}/api2/json/access/ticket", data={"username": user_at_realm, "password": password})
        if resp.status_code >= 400:
            raise ProxmoxError(f"Login failed: HTTP {resp.status_code}: {(resp.text or '')[:300]}")
        data = resp.json().get("data") or {}
        ticket = data.get("ticket") or ""
        csrf = data.get("CSRFPreventionToken") or ""
        if not ticket:
            raise ProxmoxError("Login failed: no auth ticket returned")

    client = ProxmoxClient(base_url, headers=headers, tls_verify=tls_verify, ticket=ticket, csrf_token=csrf)
    version = await client.request("GET", "/version")
    nodes = await client.request("GET", "/nodes")

    cluster_name = ""
    try:
        cluster_status = await client.request("GET", "/cluster/status")
    except ProxmoxError:
        cluster_status = []
    if isinstance(cluster_status, list):
        for item in cluster_status:
            if item.get("type") == "cluster":
                cluster_name = item.get("name") or ""
                break
    if not label:
        label = cluster_name or urlparse(base_url).hostname or "Proxmox"

    connection_id = uuid.uuid4().hex[:16]
    secret_name = SECRET_PREFIX + connection_id
    secret_value = token_secret if auth_mode == "api_token" else password
    await _secret_set(ctx, secret_name, secret_value)

    record = {
        "connection_id": connection_id,
        "label": label,
        "base_url": base_url,
        "cluster_name": cluster_name,
        "auth_mode": auth_mode,
        "tls_verify": tls_verify,
        "username": raw_username,
        "realm": normalized_realm,
        "user_at_realm": user_at_realm,
        "token_id": token_id if auth_mode == "api_token" else "",
        "secret_name": secret_name,
        "status": "connected",
        "description": f"Connected to {len(nodes) if isinstance(nodes, list) else 0} node(s)",
    }
    items = await list_connections(ctx)
    items.append(record)
    await save_connections(ctx, items)
    return record


async def wait_for_task(client: ProxmoxClient, node: str, upid: Any, timeout_seconds: int = 900, poll_seconds: float = 2.0) -> dict[str, Any]:
    if not upid:
        raise ProxmoxError("Missing Proxmox task id (UPID)")
    import asyncio
    import time

    deadline = time.monotonic() + max(5, timeout_seconds)
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = await client.request("GET", f"/nodes/{node}/tasks/{upid}/status") or {}
        status = (last.get("status") or "").lower()
        exitstatus = (last.get("exitstatus") or "").upper()
        if status == "stopped":
            if exitstatus in {"", "OK"}:
                return last
            raise ProxmoxError(f"Task {upid} failed: {exitstatus}")
        await asyncio.sleep(poll_seconds)
    raise ProxmoxError(f"Timed out waiting for task {upid} on node {node}")


async def next_guest_id(client: ProxmoxClient) -> int:
    vmid = await client.request("GET", "/cluster/nextid")
    try:
        return int(vmid)
    except Exception as e:
        raise ProxmoxError(f"Invalid next VMID returned by Proxmox: {vmid}") from e


async def ensure_node_exists(client: ProxmoxClient, node: str) -> dict[str, Any]:
    items = await client.request("GET", "/nodes")
    for item in items or []:
        if item.get("node") == node:
            return item
    raise ProxmoxError(f"Node '{node}' not found")


async def ensure_storage_exists(client: ProxmoxClient, node: str, storage: str, *, require_enabled: bool = True) -> dict[str, Any]:
    if not (storage or "").strip():
        raise ProxmoxError("storage is required")
    items = await client.request("GET", f"/nodes/{node}/storage")
    for item in items or []:
        if item.get("storage") != storage:
            continue
        if require_enabled and not item.get("enabled", 1):
            raise ProxmoxError(f"Storage '{storage}' exists on node '{node}' but is disabled")
        if require_enabled and item.get("active") in {0, False}:
            raise ProxmoxError(f"Storage '{storage}' exists on node '{node}' but is not active")
        return item
    raise ProxmoxError(f"Storage '{storage}' not found on node '{node}'")


async def ensure_bridge_exists(client: ProxmoxClient, node: str, bridge: str) -> dict[str, Any]:
    name = (bridge or "").strip()
    if not name:
        raise ProxmoxError("bridge is required")
    items = await client.request("GET", f"/nodes/{node}/network")
    for item in items or []:
        if item.get("iface") != name:
            continue
        item_type = (item.get("type") or "").strip().lower()
        if item_type and item_type != "bridge":
            raise ProxmoxError(f"Interface '{name}' exists on node '{node}' but is type '{item_type}', not bridge")
        if item.get("active") in {0, False}:
            raise ProxmoxError(f"Bridge '{name}' exists on node '{node}' but is not active")
        return item
    raise ProxmoxError(f"Bridge '{name}' not found on node '{node}'")


async def ensure_guest_id_free(client: ProxmoxClient, guest_id: int) -> None:
    items = await client.request("GET", "/cluster/resources", params={"type": "vm"})
    for item in items or []:
        if int(item.get("vmid") or -1) == int(guest_id):
            raise ProxmoxError(f"Guest ID {guest_id} is already in use")


async def ensure_guest_exists(client: ProxmoxClient, guest_type: str, node: str, guest_id: int) -> dict[str, Any]:
    items = await client.request("GET", "/cluster/resources", params={"type": "vm"})
    wanted_type = (guest_type or "").strip().lower()
    for item in items or []:
        item_vmid = item.get("vmid")
        if int(item_vmid or -1) != int(guest_id):
            continue
        item_type = (item.get("type") or "").strip().lower()
        item_node = (item.get("node") or "").strip()
        if item_type != wanted_type:
            raise ProxmoxError(f"Guest ID {guest_id} exists but is type '{item_type}', not '{wanted_type}'")
        if item_node != node:
            raise ProxmoxError(f"Guest ID {guest_id} exists on node '{item_node}', not '{node}'")
        return item
    raise ProxmoxError(f"Guest ID {guest_id} not found on node '{node}'")


async def ensure_storage_content_exists(client: ProxmoxClient, node: str, storage: str, *, volid: str = "", content_type: str = "", file_name: str = "") -> dict[str, Any]:
    await ensure_storage_exists(client, node, storage)
    query = {"content": content_type} if content_type else None
    items = await client.request("GET", f"/nodes/{node}/storage/{storage}/content", params=query)
    target_volid = (volid or "").strip()
    target_name = (file_name or "").strip()
    for item in items or []:
        item_volid = (item.get("volid") or "").strip()
        if target_volid and item_volid == target_volid:
            return item
        if target_name and (item_volid.endswith("/" + target_name) or item_volid == f"{storage}:{target_name}"):
            return item
    wanted = target_volid or target_name or "requested content"
    raise ProxmoxError(f"Storage content '{wanted}' not found on storage '{storage}' at node '{node}'")


def normalize_tag_string(tags: str) -> str:
    raw = (tags or "").strip()
    if not raw:
        return ""
    items: list[str] = []
    seen: set[str] = set()
    for part in raw.replace("\n", ",").split(","):
        tag = "".join(ch for ch in part.strip() if ch.isalnum() or ch in {"-", "_", "."})
        if not tag or tag in seen:
            continue
        seen.add(tag)
        items.append(tag)
    return ";".join(items)


def ensure_positive_int(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if int(value) <= 0:
        raise ProxmoxError(f"{field_name} must be greater than 0")
    return int(value)


def guest_path(guest_type: str, node: str, vmid: int | str) -> str:
    guest_type = (guest_type or "").lower().strip()
    if guest_type not in {"qemu", "lxc"}:
        raise ProxmoxError("guest_type must be 'qemu' or 'lxc'")
    return f"/nodes/{node}/{guest_type}/{vmid}"


def node_storage_path(node: str, storage: str = "") -> str:
    return f"/nodes/{node}/storage/{storage}" if storage else f"/nodes/{node}/storage"


def ensure_guest_type_for_create(guest_type: str) -> str:
    guest_type = (guest_type or "").lower().strip()
    if guest_type not in {"qemu", "lxc"}:
        raise ProxmoxError("guest_type must be 'qemu' or 'lxc'")
    return guest_type


def bool_to_proxmox_flag(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def build_qemu_net0(model: str, bridge: str, vlan_tag: int | None = None) -> str:
    nic_model = (model or "virtio").strip()
    nic_bridge = (bridge or "vmbr0").strip()
    net = f"{nic_model},bridge={nic_bridge}"
    if vlan_tag is not None:
        if int(vlan_tag) <= 0:
            raise ProxmoxError("qemu_vlan_tag must be greater than 0 when provided")
        net += f",tag={int(vlan_tag)}"
    return net


def build_lxc_net0(bridge: str, ip_config: str = "dhcp", name: str = "eth0", vlan_tag: int | None = None) -> str:
    nic_bridge = (bridge or "vmbr0").strip()
    nic_name = (name or "eth0").strip()
    ip_value = (ip_config or "dhcp").strip()
    net = f"name={nic_name},bridge={nic_bridge},ip={ip_value}"
    if vlan_tag is not None:
        if int(vlan_tag) <= 0:
            raise ProxmoxError("lxc_vlan_tag must be greater than 0 when provided")
        net += f",tag={int(vlan_tag)}"
    return net


def parse_volume_reference(value: str, *, field_name: str, default_kind: str = "") -> str:
    raw = (value or "").strip()
    if not raw:
        raise ProxmoxError(f"{field_name} is required")
    if ":" not in raw:
        raise ProxmoxError(f"{field_name} must be a Proxmox volume reference like 'local-lvm:32' or 'local:vztmpl/debian.tar.zst'")
    storage, rest = raw.split(":", 1)
    if not storage.strip() or not rest.strip():
        raise ProxmoxError(f"{field_name} must be a valid Proxmox volume reference")
    if default_kind and "/" not in rest and not rest.isdigit():
        return f"{storage}:{default_kind}/{rest}"
    return raw


def build_scsi_disk_value(storage: str, size_gb: int, disk_format: str = "") -> str:
    storage_name = (storage or "").strip()
    if not storage_name:
        raise ProxmoxError("qemu_scsi_storage is required")
    if int(size_gb) <= 0:
        raise ProxmoxError("qemu_scsi_gb must be greater than 0")
    value = f"{storage_name}:{int(size_gb)}"
    if disk_format:
        value += f",format={disk_format.strip()}"
    return value


def build_rootfs_value(storage: str, size_gb: int) -> str:
    storage_name = (storage or "").strip()
    if not storage_name:
        raise ProxmoxError("lxc_rootfs_storage is required")
    if int(size_gb) <= 0:
        raise ProxmoxError("lxc_rootfs_gb must be greater than 0")
    return f"{storage_name}:{int(size_gb)}"
