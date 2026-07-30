"""Unit tests for the async ctx-touching helpers in providers.py:
connect_and_persist, list/save/update/delete_connections, resolve_connection,
build_client_from_connection. Uses FakeCtx (KV store + MockSecretStore) and
ProxmoxAPIMock (httpx.MockTransport) from conftest.py — no real network.
"""
from __future__ import annotations

import pytest

import providers as p


pytestmark = pytest.mark.asyncio


# ── list/save/update/delete connections (pure KV round-trip) ─────────

async def test_list_connections_empty_by_default(make_ctx):
    ctx = make_ctx()
    assert await p.list_connections(ctx) == []


async def test_save_and_list_connections_round_trips(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1", "label": "First"}])
    items = await p.list_connections(ctx)
    assert items == [{"connection_id": "c1", "label": "First"}]


async def test_update_connection_merges_fields(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1", "label": "Old", "tls_verify": True}])
    updated = await p.update_connection(ctx, "c1", {"label": "New"})
    assert updated["label"] == "New"
    assert updated["tls_verify"] is True
    items = await p.list_connections(ctx)
    assert items[0]["label"] == "New"


async def test_update_connection_missing_raises(make_ctx):
    ctx = make_ctx()
    with pytest.raises(p.ProxmoxError):
        await p.update_connection(ctx, "nope", {"label": "x"})


async def test_delete_connection_removes_it(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1", "label": "First", "secret_name": "proxmox_conn_c1"}])
    await ctx.secrets.set("proxmox_conn_c1", "shh")
    removed = await p.delete_connection(ctx, "c1")
    assert removed["connection_id"] == "c1"
    assert await p.list_connections(ctx) == []
    # secret is cleaned up too
    assert await ctx.secrets.get("proxmox_conn_c1") is None


async def test_delete_connection_missing_raises(make_ctx):
    ctx = make_ctx()
    with pytest.raises(p.ProxmoxError):
        await p.delete_connection(ctx, "nope")


# ── resolve_connection ────────────────────────────────────────────────

async def test_resolve_connection_no_saved_raises(make_ctx):
    ctx = make_ctx()
    with pytest.raises(p.ProxmoxError):
        await p.resolve_connection(ctx)


async def test_resolve_connection_defaults_to_first(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1"}, {"connection_id": "c2"}])
    conn = await p.resolve_connection(ctx)
    assert conn["connection_id"] == "c1"


async def test_resolve_connection_by_id(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1"}, {"connection_id": "c2"}])
    conn = await p.resolve_connection(ctx, "c2")
    assert conn["connection_id"] == "c2"


async def test_resolve_connection_unknown_id_raises(make_ctx):
    ctx = make_ctx()
    await p.save_connections(ctx, [{"connection_id": "c1"}])
    with pytest.raises(p.ProxmoxError):
        await p.resolve_connection(ctx, "ghost")


# ── build_client_from_connection ──────────────────────────────────────

async def test_build_client_from_connection_api_token(make_ctx):
    ctx = make_ctx()
    await ctx.secrets.set("proxmox_conn_c1", "the-secret")
    connection = {
        "connection_id": "c1", "auth_mode": "api_token", "tls_verify": True,
        "base_url": "https://pve.example.com:8006",
        "user_at_realm": "root@pam", "token_id": "imperal-ext",
        "secret_name": "proxmox_conn_c1",
    }
    client = await p.build_client_from_connection(ctx, connection)
    assert client.base_url == "https://pve.example.com:8006"
    assert client.headers["Authorization"] == "PVEAPIToken=root@pam!imperal-ext=the-secret"


async def test_build_client_from_connection_unsupported_auth_mode_raises(make_ctx):
    ctx = make_ctx()
    connection = {"connection_id": "c1", "auth_mode": "ldap_bind", "base_url": "https://x:8006"}
    with pytest.raises(p.ProxmoxError):
        await p.build_client_from_connection(ctx, connection)


# ── connect_and_persist (full flow through the httpx mock) ────────────

async def test_connect_and_persist_success_stores_record_and_secret(make_ctx, proxmox_api, monkeypatch):
    ctx = make_ctx()
    proxmox_api.on("GET", "/version", json_data={"data": {"version": "8.1"}})
    proxmox_api.on("GET", "/nodes", json_data={"data": [{"node": "pve1"}, {"node": "pve2"}]})
    proxmox_api.on("GET", "/cluster/status", json_data={"data": [{"type": "cluster", "name": "prod-cluster"}]})
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)

    record = await p.connect_and_persist(
        ctx, base_url="pve.example.com", auth_mode="api_token", realm="pam",
        username="root", token_id="imperal-ext", token_secret="s3cr3t", password="", tls_verify=True, label="",
    )
    assert record["base_url"] == "https://pve.example.com:8006"
    assert record["cluster_name"] == "prod-cluster"
    assert record["label"] == "prod-cluster"
    assert record["status"] == "connected"
    assert record["description"] == "Connected to 2 node(s)"

    saved = await p.list_connections(ctx)
    assert len(saved) == 1
    assert saved[0]["connection_id"] == record["connection_id"]
    stored_secret = await ctx.secrets.get(record["secret_name"])
    assert stored_secret == "s3cr3t"


async def test_connect_and_persist_auth_failure_raises_and_does_not_persist(make_ctx, proxmox_api, monkeypatch):
    ctx = make_ctx()
    proxmox_api.on("GET", "/version", status_code=401, text="unauthorized")
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)

    with pytest.raises(p.ProxmoxError):
        await p.connect_and_persist(
            ctx, base_url="pve.example.com", auth_mode="api_token", realm="pam",
            username="root", token_id="imperal-ext", token_secret="bad", password="", tls_verify=True, label="",
        )
    assert await p.list_connections(ctx) == []


async def test_connect_and_persist_tolerates_permission_denied_cluster_status(make_ctx, proxmox_api, monkeypatch):
    ctx = make_ctx()
    proxmox_api.on("GET", "/version", json_data={"data": {"version": "8.1"}})
    proxmox_api.on("GET", "/nodes", json_data={"data": [{"node": "pve1"}]})
    proxmox_api.on("GET", "/cluster/status", json_data={"errors": {"__all__": "Permission check failed"}})
    monkeypatch.setattr(p.httpx, "AsyncClient", proxmox_api.async_client_factory)

    record = await p.connect_and_persist(
        ctx, base_url="pve.example.com", auth_mode="api_token", realm="pam",
        username="root", token_id="imperal-ext", token_secret="s3cr3t", password="", tls_verify=True, label="My Cluster",
    )
    # cluster_status permission failure is tolerated (empty cluster_name), the
    # explicit label passed through untouched, connect still succeeds.
    assert record["cluster_name"] == ""
    assert record["label"] == "My Cluster"
