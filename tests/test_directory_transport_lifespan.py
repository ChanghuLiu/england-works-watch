"""Exercise production child-transport setup without importing regulatory data.

The real transport construction and lifespan AST are loaded from the production
entrypoint. Real MCP session managers and HTTP handshakes expose a missing
child lifespan; domain loaders, payment adapters and source monitors are outside
this transport-only regression.
"""
import ast
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace

from mcp.server.mcpserver import MCPServer
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient


ENTRYPOINT = "src/england_works_watch/entrypoint.py"


async def _idle():
    await asyncio.Event().wait()


def _transport_app():
    source = Path(__file__).resolve().parents[1] / ENTRYPOINT
    tree = ast.parse(source.read_text())
    transport_names = {"directory_app", "ai_app", "openai_app"}
    assignments = sorted(
        [node for node in ast.walk(tree)
         if isinstance(node, ast.Assign)
         and any(isinstance(target, ast.Name) and target.id in transport_names
                 for target in node.targets)],
        key=lambda node: node.lineno,
    )
    lifespan = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.AsyncFunctionDef) and node.name == "lifespan")
    main = MCPServer("commercial-fixture")
    main.streamable_http_app(host="127.0.0.1", json_response=True, stateless_http=True)
    directory = MCPServer("directory-fixture")
    @directory.tool()
    def directory_probe() -> str:
        return "fixture"
    namespace = {
        "host": "127.0.0.1", "directory_mcp": directory,
        "openai_mcp": MCPServer("openai-fixture"),
        "server": SimpleNamespace(mcp=main, session_manager=main.session_manager),
        "asyncio": asyncio, "AsyncExitStack": AsyncExitStack,
        "asynccontextmanager": asynccontextmanager, "suppress": suppress,
        "runtime": SimpleNamespace(_runtime_source_probe_loop=_idle),
        "_commercial_summary_loop": _idle,
    }
    exec(compile(ast.Module(body=assignments + [lifespan], type_ignores=[]),
                 str(source), "exec"), namespace)
    return Starlette(routes=[
        Mount("/mcp-directory", app=namespace["directory_app"]),
        Mount("/ai", app=namespace["ai_app"]),
    ], lifespan=namespace["lifespan"])


def test_both_production_directory_transports_start_and_list_tools():
    with TestClient(_transport_app(), base_url="http://127.0.0.1:8000") as client:
        for path in ("/mcp-directory/", "/ai/mcp"):
            headers = {"Accept": "application/json, text/event-stream"}
            initialized = client.post(path, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                           "clientInfo": {"name": "transport-regression", "version": "1"}},
            })
            assert initialized.status_code == 200, initialized.text
            headers["MCP-Protocol-Version"] = initialized.json()["result"]["protocolVersion"]
            notification = client.post(path, headers=headers, json={
                "jsonrpc": "2.0", "method": "notifications/initialized",
            })
            assert notification.status_code in (200, 202)
            listed = client.post(path, headers=headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
            })
            assert listed.status_code == 200, listed.text
            assert [tool["name"] for tool in listed.json()["result"]["tools"]] == ["directory_probe"]
