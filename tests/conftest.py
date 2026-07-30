"""Test harness for imperal-ext-proxmox-connector.

The extension talks to Proxmox VE exclusively via httpx (ProxmoxClient in
providers.py), and persists connection records via a single-key KV surface
(ctx.store.get(key)/set(key, value) — NOT the collection-based StoreProtocol
used by most other extensions) plus ctx.secrets for the API token secret.
No real network, no third-party mocking library (matches the coding-remote
httpx.MockTransport precedent — the validation host's worker venv has
httpx+pytest but NOT respx).
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable

import httpx
import pytest

# Captured BEFORE any test monkeypatches providers.httpx.AsyncClient, so the
# mock factory below can always reach the real implementation.
_REAL_ASYNC_CLIENT = httpx.AsyncClient

# Make the ext modules importable (they use bare `import app`, `from app import …`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from imperal_sdk.testing.mock_secrets import MockSecretStore  # noqa: E402


class FakeKVStore:
    """In-memory single-key KV mirroring the subset providers.py uses:
    ``get(key) -> value | None`` and ``set(key, value) -> None``."""

    def __init__(self):
        self._data: dict[str, Any] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value: Any):
        self._data[key] = value


class FakeUser:
    def __init__(self, imperal_id: str = "imp_u_TEST"):
        self.imperal_id = imperal_id


class FakeCtx:
    """Minimal ctx stand-in: ctx.store (KV), ctx.secrets (MockSecretStore),
    ctx.user.imperal_id — the only surface providers.py/handlers_proxmox.py
    touch."""

    def __init__(self, imperal_id: str = "imp_u_TEST"):
        self.store = FakeKVStore()
        self.secrets = MockSecretStore()
        self.user = FakeUser(imperal_id)


@pytest.fixture
def make_ctx():
    def _make(imperal_id: str = "imp_u_TEST") -> FakeCtx:
        return FakeCtx(imperal_id)
    return _make


class ProxmoxAPIMock:
    """Routes (method, path) -> canned httpx.Response (or an Exception to
    raise) through an httpx.MockTransport, and monkeypatches
    providers.httpx.AsyncClient so every ProxmoxClient.request(...) call in
    the test goes through this fake instead of real network.

    Usage::
        api = ProxmoxAPIMock()
        api.on("GET", "/version", json_data={"data": {"version": "8.1"}})
        api.on("GET", "/nodes", json_data={"data": [...]})
        monkeypatch.setattr(providers.httpx, "AsyncClient", api.async_client_factory)
    """

    def __init__(self):
        self.routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]] = {}
        self.calls: list[httpx.Request] = []

    def on(self, method: str, path: str, *, json_data: Any = None, status_code: int = 200, text: str = ""):
        def _responder(request: httpx.Request) -> httpx.Response:
            if json_data is not None:
                return httpx.Response(status_code, json=json_data)
            return httpx.Response(status_code, text=text)
        self.routes[(method.upper(), path)] = _responder

    def on_raise(self, method: str, path: str, exc: Exception):
        def _responder(request: httpx.Request) -> httpx.Response:
            raise exc
        self.routes[(method.upper(), path)] = _responder

    def _handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        # Strip the /api2/json prefix ProxmoxClient always adds.
        path = request.url.path
        if path.startswith("/api2/json"):
            path = path[len("/api2/json"):]
        key = (request.method.upper(), path)
        if key in self.routes:
            return self.routes[key](request)
        return httpx.Response(404, json={"data": None, "errors": {"__all__": f"no route for {key}"}})

    def async_client_factory(self, *args, **kwargs):
        # Capture the REAL httpx.AsyncClient at module level (before any
        # monkeypatch), never at call time -- providers.py does
        # `import httpx` then `httpx.AsyncClient(...)`, so once a test
        # monkeypatches providers.httpx.AsyncClient to this very factory,
        # re-reading httpx.AsyncClient here would recurse into itself.
        kwargs["transport"] = httpx.MockTransport(self._handler)
        return _REAL_ASYNC_CLIENT(**kwargs)


@pytest.fixture
def proxmox_api():
    return ProxmoxAPIMock()
