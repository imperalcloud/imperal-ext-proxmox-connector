"""Handler-level tests for handlers_proxmox.py's @chat.function tools.

The SDK decorator returns the wrapped function unchanged (see
imperal_sdk.chat.extension._function_impl), so handlers can be invoked
directly with (ctx, params) — the same convention used by the
bing-webmaster-connector test suite. All Proxmox HTTP calls are routed
through ProxmoxAPIMock (httpx.MockTransport); no real network.
"""
from __future__ import annotations

import pytest

import handlers_proxmox as h
import providers as p


pytestmark = pytest.mark.asyncio


async def _seeded_ctx(make_ctx, proxmox_api, monkeypatch):
    """A ctx with one saved api_token connection ready for build_client_from_connection."""
    ctx = make_ctx()
    await ctx.secrets.set("proxmox_conn_c1", "s3cr3t")
    await p.save_connections(ctx, [{
        "connection_id": "c1",
        "label": "Prod",
        "base_url": "https://pve.example.com:8006",
        "auth_mode": "api_token",
        "tls_verify": True,
        "username": "root",
        "realm": "pam",
        "user_at_realm": "root@pam",
        "token_id": "imperal-ext",
        "secret_name": "proxmox_conn_c1",
        "status": "connected",
    }])
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)
    return ctx


# ── list_proxmox_connections / connect_proxmox ───────────────────────

async def test_list_proxmox_connections_empty(make_ctx):
    ctx = make_ctx()
    result = await h.list_proxmox_connections(ctx, h.EmptyParams())
    assert result.status == "success"
    assert result.data["items"] == []


async def test_connect_proxmox_success(make_ctx, proxmox_api, monkeypatch):
    ctx = make_ctx()
    proxmox_api.on("GET", "/version", json_data={"data": {"version": "8.1"}})
    proxmox_api.on("GET", "/nodes", json_data={"data": [{"node": "pve1"}]})
    proxmox_api.on("GET", "/cluster/status", json_data={"data": [{"type": "cluster", "name": "prod"}]})
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)

    params = h.ConnectProxmoxParams(
        base_url="pve.example.com", auth_mode="api_token", realm="pam",
        username="root", token_id="imperal-ext", token_secret="s3cr3t",
    )
    result = await h.connect_proxmox(ctx, params)
    assert result.status == "success"
    assert result.data["cluster_name"] == "prod"
    items = await p.list_connections(ctx)
    assert len(items) == 1


async def test_connect_proxmox_auth_failure_surfaces_error(make_ctx, proxmox_api, monkeypatch):
    ctx = make_ctx()
    proxmox_api.on("GET", "/version", status_code=401, text="auth error")
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)

    params = h.ConnectProxmoxParams(
        base_url="pve.example.com", auth_mode="api_token", realm="pam",
        username="root", token_id="imperal-ext", token_secret="wrong",
    )
    result = await h.connect_proxmox(ctx, params)
    assert result.status == "error"


# ── list_proxmox_guests / get_proxmox_guest ──────────────────────────

async def test_list_proxmox_guests_filters_by_type_and_node(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("GET", "/cluster/resources", json_data={"data": [
        {"type": "qemu", "vmid": 100, "node": "pve1", "status": "running"},
        {"type": "lxc", "vmid": 200, "node": "pve2", "status": "stopped"},
        {"type": "storage", "storage": "local"},
    ]})
    result = await h.list_proxmox_guests(ctx, h.ListGuestsParams(guest_type="qemu"))
    assert result.status == "success"
    assert len(result.data["items"]) == 1
    assert result.data["items"][0]["vmid"] == 100


async def test_list_proxmox_guests_no_connections_errors(make_ctx):
    ctx = make_ctx()
    result = await h.list_proxmox_guests(ctx, h.ListGuestsParams())
    assert result.status == "error"


async def test_get_proxmox_guest_success(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("GET", "/nodes/pve1/qemu/100/status/current", json_data={"data": {"status": "running", "vmid": 100}})
    proxmox_api.on("GET", "/nodes/pve1/qemu/100/config", json_data={"data": {"name": "web-1", "cores": 2}})
    result = await h.get_proxmox_guest(ctx, h.GuestParams(node="pve1", guest_id=100, guest_type="qemu"))
    assert result.status == "success"
    assert result.data["status"] == "running"
    assert result.data["name"] == "web-1"


# ── delete_proxmox_guest / power_proxmox_guest / clone_proxmox_guest ─

async def test_delete_proxmox_guest_success(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("GET", "/nodes", json_data={"data": [{"node": "pve1"}]})
    proxmox_api.on("GET", "/cluster/resources", json_data={"data": [
        {"type": "qemu", "vmid": 100, "node": "pve1", "status": "stopped"},
    ]})
    proxmox_api.on("DELETE", "/nodes/pve1/qemu/100", json_data={"data": "UPID:pve1:del"})
    result = await h.delete_proxmox_guest(ctx, h.DeleteGuestParams(node="pve1", guest_id=100, guest_type="qemu"))
    assert result.status == "success"
    assert result.data["task_id"] == "UPID:pve1:del"


async def test_delete_proxmox_guest_missing_raises_error(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("GET", "/nodes", json_data={"data": [{"node": "pve1"}]})
    proxmox_api.on("GET", "/cluster/resources", json_data={"data": []})
    result = await h.delete_proxmox_guest(ctx, h.DeleteGuestParams(node="pve1", guest_id=999, guest_type="qemu"))
    assert result.status == "error"


async def test_power_proxmox_guest_start(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("POST", "/nodes/pve1/qemu/100/status/start", json_data={"data": "UPID:pve1:start"})
    result = await h.power_proxmox_guest(ctx, h.GuestPowerParams(node="pve1", guest_id=100, guest_type="qemu", action="start"))
    assert result.status == "success"
    assert result.data["task_id"] == "UPID:pve1:start"


async def test_clone_proxmox_guest_queued_without_start(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("POST", "/nodes/pve1/qemu/100/clone", json_data={"data": "UPID:pve1:clone"})
    params = h.CloneGuestParams(node="pve1", guest_type="qemu", source_guest_id=100, new_guest_id=101)
    result = await h.clone_proxmox_guest(ctx, params)
    assert result.status == "success"
    assert result.data["task_id"] == "UPID:pve1:clone"


# ── get_proxmox_status (cluster summary) ─────────────────────────────

async def test_get_proxmox_status_summary(make_ctx, proxmox_api, monkeypatch):
    ctx = await _seeded_ctx(make_ctx, proxmox_api, monkeypatch)
    proxmox_api.on("GET", "/cluster/status", json_data={"data": [
        {"type": "node", "online": 1},
        {"type": "node", "online": 0},
    ]})
    proxmox_api.on("GET", "/cluster/resources", json_data={"data": [
        {"type": "qemu", "status": "running"},
        {"type": "lxc", "status": "stopped"},
        {"type": "storage"},
    ]})
    result = await h.get_proxmox_status(ctx, h.ConnectionIdParams())
    assert result.status == "success"
    assert result.data["nodes_total"] == 2
    assert result.data["nodes_online"] == 1
    assert result.data["guests_total"] == 2
    assert result.data["guests_running"] == 1
    assert result.data["status"] == "degraded"
