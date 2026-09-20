from __future__ import annotations

from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from england_works_watch import server
from england_works_watch.directory_server import openai_mcp


def _rpc(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


def _app() -> Starlette:
    openai_app = openai_mcp.streamable_http_app(
        host="testserver",
        json_response=True,
        stateless_http=True,
    )

    @asynccontextmanager
    async def lifespan(_app):
        async with openai_mcp.session_manager.run():
            yield

    return Starlette(routes=[Mount("/openai", app=openai_app)], lifespan=lifespan)


def test_openai_mcp_has_stable_read_only_tool_contract():
    with TestClient(_app()) as client:
        initialized = client.post(
            "/openai/mcp",
            json=_rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "openai-review", "version": "1"},
                },
            ),
        )
        listed = client.post("/openai/mcp", json=_rpc("tools/list", request_id=2))

    assert initialized.status_code == 200
    assert listed.status_code == 200
    tools = listed.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "sponsor_change_checker_info",
        "list_supported_change_events",
        "licensing_source_status",
        "assess_change_impact",
    ]
    for tool in tools:
        annotations = tool.get("annotations", {})
        assert annotations.get("readOnlyHint") is True
        assert annotations.get("openWorldHint") is False
        assert annotations.get("destructiveHint") is False


def test_openai_metadata_calls_do_not_use_directory_telemetry(monkeypatch):
    def telemetry_must_not_run(*_args, **_kwargs):
        raise AssertionError("OpenAI MCP must not write directory telemetry")

    monkeypatch.setattr(server, "_measured", telemetry_must_not_run)

    with TestClient(_app()) as client:
        info = client.post(
            "/openai/mcp",
            json=_rpc("tools/call", {"name": "sponsor_change_checker_info", "arguments": {}}, 3),
        )
        events = client.post(
            "/openai/mcp",
            json=_rpc("tools/call", {"name": "list_supported_change_events", "arguments": {}}, 4),
        )

    assert info.status_code == 200
    assert events.status_code == 200
    assert "UK Sponsor Change Checker" in info.text
    assert "salary_change" in events.text
