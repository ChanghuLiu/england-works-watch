"""Production entrypoint with machine-discovery catalog routes and telemetry.

The deterministic decision server remains in ``server.py``. This module adds
catalog surfaces, benchmark-driven MCP selection metadata, and privacy-minimal
HTTP discovery observability. It does not change regulatory rules, prices,
payment semantics, or tool execution.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
import sys

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

from . import server
from .discovery_ecosystem import DiscoveryEcosystemASGI
from .selection_metadata import apply_selection_metadata

# The server module has already registered every tool by import time. Override
# only advertised discovery metadata/schemas; deterministic execution stays in
# server.py and policy.py.
apply_selection_metadata(server.mcp)


@server.mcp.custom_route("/.well-known/ai-catalog.json", methods=["GET"])
async def ai_catalog(_request):
    """Machine-readable catalog advertising both MCP and OpenAPI interfaces."""
    return JSONResponse(
        {
            "name": "England Works Watch",
            "version": server.SERVICE_VERSION,
            "description": server.SERVER_SELECTION_DESCRIPTION,
            "interfaces": [
                {"type": "mcp", "transport": "streamable-http", "url": server.PUBLIC_MCP_URL},
                {"type": "openapi", "url": f"{server.PUBLIC_ORIGIN}/openapi.json"},
            ],
            "discovery": {
                "mcp_manifest": f"{server.PUBLIC_ORIGIN}/.well-known/mcp.json",
                "mcp_server_card": f"{server.PUBLIC_ORIGIN}/.well-known/mcp/server-card.json",
                "agent_card": f"{server.PUBLIC_ORIGIN}/.well-known/agent-card.json",
                "llms": f"{server.PUBLIC_ORIGIN}/llms.txt",
                "x402": f"{server.PUBLIC_ORIGIN}/.well-known/x402",
            },
            "scope": "Skilled Worker sponsor duties only",
            "payment": server._payment_info(),
            "evidence_policy": "Official GOV.UK sources are fingerprint-monitored; changed or stale evidence fails closed.",
        }
    )


@server.mcp.custom_route("/.well-known/api-catalog", methods=["GET"])
async def api_catalog(_request):
    """RFC-style linkset for crawlers that discover machine APIs by relation."""
    payload = {
        "linkset": [
            {
                "anchor": server.PUBLIC_ORIGIN,
                "service-desc": [
                    {"href": f"{server.PUBLIC_ORIGIN}/openapi.json", "type": "application/openapi+json"},
                    {"href": f"{server.PUBLIC_ORIGIN}/.well-known/mcp.json", "type": "application/json"},
                    {"href": server.PUBLIC_MCP_URL, "type": "application/json"},
                ],
                "describedby": [
                    {"href": f"{server.PUBLIC_ORIGIN}/llms.txt", "type": "text/plain"},
                    {"href": f"{server.PUBLIC_ORIGIN}/.well-known/x402", "type": "application/json"},
                ],
            }
        ]
    }
    return JSONResponse(payload, media_type="application/linkset+json")


def _run_http() -> None:
    server.ensure_runtime_seeded()
    server.start_background_source_monitor()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    mcp_app = server.mcp.streamable_http_app(host=host, json_response=True, stateless_http=True)

    @asynccontextmanager
    async def lifespan(_app):
        async with server.mcp.session_manager.run():
            yield

    app = Starlette(routes=[Mount("/", app=mcp_app)], lifespan=lifespan)
    app = DiscoveryEcosystemASGI(app)
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    # Preserve the existing CLI contract used by Railway and release smokes.
    if "--http" in sys.argv[1:]:
        _run_http()
    else:
        server.main()


if __name__ == "__main__":
    main()
