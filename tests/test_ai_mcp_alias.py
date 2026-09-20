from __future__ import annotations

from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from england_works_watch.directory_server import directory_mcp


def _rpc(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _app() -> Starlette:
    ai_app = directory_mcp.streamable_http_app(
        host="testserver",
        json_response=True,
        stateless_http=True,
    )

    @asynccontextmanager
    async def lifespan(_app):
        async with directory_mcp.session_manager.run():
            yield

    return Starlette(routes=[Mount("/ai", app=ai_app)], lifespan=lifespan)


def test_ai_mcp_alias_is_read_only_directory_surface():
    with TestClient(_app()) as client:
        initialized = client.post(
            "/ai/mcp",
            json=_rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "ai-client", "version": "1"},
                },
            ),
        )
        listed = client.post("/ai/mcp", json=_rpc("tools/list", request_id=2))

    assert initialized.status_code == 200
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "sponsor_change_checker_info",
        "list_supported_change_events",
        "licensing_source_status",
        "assess_change_impact",
    ]
    assert all(tool.get("annotations", {}).get("readOnlyHint") is True for tool in tools)
    combined = " ".join((tool.get("description") or "") for tool in tools).lower()
    assert "x402" not in combined
    assert "stripe" not in combined
    assert "checkout" not in combined
