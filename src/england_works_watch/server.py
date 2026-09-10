from __future__ import annotations

import argparse
import os
import time
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse, PlainTextResponse, Response

from .analytics import record, summary
from .policy import RULES, assess_change_impact as decide
from .selection_metadata import SERVER_SELECTION_DESCRIPTION
from .source_runtime import ensure_runtime_seeded, production_source_status, start_background_source_monitor
from .x402_gate import MCP2X402Gate, PaidToolSpec, invoke, meta_to_dict

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
SERVICE_VERSION = "0.1.1"
PUBLIC_ORIGIN = os.getenv("EWW_PUBLIC_ORIGIN", "https://england-works-watch-production.up.railway.app").rstrip("/")
PUBLIC_MCP_URL = f"{PUBLIC_ORIGIN}/mcp"
PRICE_ASSESS = os.getenv("EWW_X402_PRICE_ASSESS", "$0.02")
PRICE_BATCH = os.getenv("EWW_X402_PRICE_BATCH", "$0.05")
PAYMENT_ENFORCED = os.getenv("EWW_PAYMENT_ENFORCED", "0").strip().lower() in {"1", "true", "yes", "on"}
PAY_TO = os.getenv("EWW_X402_PAY_TO", "").strip()
NETWORK = os.getenv("EWW_X402_NETWORK", "eip155:8453").strip()
FACILITATOR = os.getenv("EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network").strip()
SUPPORTED_EVENTS = [
    "worker_start_delay",
    "unauthorised_absence",
    "unpaid_or_reduced_pay_absence",
    "salary_change",
    "role_change",
    "work_location_change",
    "stop_sponsoring",
    "organisation_change",
    "tupe_transfer",
    "merger_takeover",
]

mcp = MCPServer(
    "England Works Watch",
    version=SERVICE_VERSION,
    instructions=(
        SERVER_SELECTION_DESCRIPTION + " "
        "V0.1 covers Skilled Worker sponsor duties only. "
        "Return only AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, or INSUFFICIENT_INPUT. "
        "Fail closed on missing inputs, official-source drift/staleness, conflicts, or unsupported routes. "
        "Evidence-first preflight, not legal advice."
    ),
)


def _meta(ctx: Context | None) -> dict[str, Any]:
    if ctx is None:
        return {}
    request_context = getattr(ctx, "request_context", None)
    return meta_to_dict(getattr(request_context, "meta", None))


def _measured(tool: str, fn, *, billable: bool, meta: dict[str, Any] | None = None):
    start = time.monotonic()
    try:
        result = fn()
        record(
            tool,
            "ok",
            billable=billable,
            payment_state="not_enforced" if billable and not PAYMENT_ENFORCED else None,
            meta=meta,
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )
        return result
    except Exception:
        record(
            tool,
            "error",
            billable=billable,
            meta=meta,
            latency_ms=round((time.monotonic() - start) * 1000, 2),
        )
        raise


def _payment_info() -> dict[str, Any]:
    result = {
        "protocol": "x402-v2",
        "scheme": "exact",
        "network": NETWORK,
        "asset": "USDC",
        "facilitator": FACILITATOR,
        "enforced": PAYMENT_ENFORCED,
        "prices": {
            "assess_change_impact": PRICE_ASSESS,
            "batch_assess_changes": PRICE_BATCH,
        },
        "buyer_security": "Never send private keys or seed phrases to this service; payment authorization is signed buyer-side.",
    }
    if PAY_TO:
        result["pay_to"] = PAY_TO
    return result


def _server_card() -> dict[str, Any]:
    return {
        "name": "England Works Watch",
        "version": SERVICE_VERSION,
        "description": SERVER_SELECTION_DESCRIPTION,
        "transport": "streamable-http",
        "endpoint": PUBLIC_MCP_URL,
        "scope": RULES["scope"],
        "decision_labels": ["AFFECTED", "NOT_AFFECTED", "REVIEW_REQUIRED", "INSUFFICIENT_INPUT"],
        "free_tools": ["england_works_watch_info", "licensing_source_status", "list_supported_change_events"],
        "paid_tools": ["assess_change_impact", "batch_assess_changes"],
        "decision_argument_shape": {
            "payload": {
                "event_type": "unauthorised_absence",
                "route": "skilled_worker",
                "consecutive_working_days": 11,
            }
        },
        "payment": _payment_info(),
        "evidence": "Official GOV.UK sponsor guidance with version, effective date, exact locator and runtime freshness gate.",
        "safety": "Evidence-first sponsor compliance/change-impact preflight; not legal advice or a Home Office decision.",
    }


def england_works_watch_info() -> dict[str, Any]:
    return _server_card()


def licensing_source_status() -> dict[str, Any]:
    return production_source_status()


def list_supported_change_events() -> dict[str, Any]:
    return {
        "scope": RULES["scope"],
        "supported_events": SUPPORTED_EVENTS,
        "decision_labels": ["AFFECTED", "NOT_AFFECTED", "REVIEW_REQUIRED", "INSUFFICIENT_INPUT"],
        "rule_pack_version": RULES["version"],
    }


def assess_change_impact(payload: dict[str, Any]) -> dict[str, Any]:
    return decide(payload)


def batch_assess_changes(items: list[dict[str, Any]]) -> dict[str, Any]:
    if len(items) > 25:
        raise ValueError("batch_assess_changes accepts at most 25 events")
    rows = [decide(item) for item in items]
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {"count": len(rows), "counts": counts, "results": rows}


@mcp.tool(
    name="england_works_watch_info",
    description=(
        "FREE product-info tool. Use for questions about England Works Watch itself: product scope, pricing, MCP endpoint, "
        "x402/Base USDC payment details, supported decision labels, or whether this is legal advice. Do not use for source-freshness "
        "checks or to decide a sponsor event."
    ),
    annotations=READ,
)
def _tool_info() -> dict[str, Any]:
    return _measured("england_works_watch_info", england_works_watch_info, billable=False)


@mcp.tool(
    name="licensing_source_status",
    description=(
        "FREE official-source freshness/evidence-lifecycle tool. Use before relying on decisions, or when asked whether GOV.UK sponsor "
        "guidance is current, stale, changed, conflicting, blocking, or fully baselined. This does not list supported event types and "
        "does not assess a worker/employer change."
    ),
    annotations=READ,
)
def _tool_source_status() -> dict[str, Any]:
    return _measured("licensing_source_status", licensing_source_status, billable=False)


@mcp.tool(
    name="list_supported_change_events",
    description=(
        "FREE supported-event list. Use when an agent needs to know which Skilled Worker sponsor event categories England Works Watch can "
        "handle, such as salary, role/occupation code, work location/home working, absence, delayed start, stop sponsorship, TUPE, merger "
        "or sponsor organisation changes. Do not use for source freshness or to assess a specific event."
    ),
    annotations=READ,
)
def _tool_events() -> dict[str, Any]:
    return _measured("list_supported_change_events", list_supported_change_events, billable=False)


@mcp.tool(
    name="assess_change_impact",
    description=(
        "PAID single-event decision tool ($0.02). Use for exactly one Skilled Worker sponsor change/event when you need an evidence-linked "
        "AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, or INSUFFICIENT_INPUT decision plus next action. Examples: one salary reduction, one "
        "11-working-day unauthorised absence, one role/SOC change, one home-working/location change, one TUPE event. Do not use to merely "
        "list supported event types or for multiple events."
    ),
)
def _tool_assess(payload: dict[str, Any], ctx: Context | None = None) -> Any:
    meta = _meta(ctx)
    return invoke(
        PaidToolSpec(
            name="assess_change_impact",
            price=PRICE_ASSESS,
            description="Official-source-backed Skilled Worker sponsor change-impact preflight.",
            tags=["uk", "skilled-worker", "sponsor", "compliance", "change-impact"],
            example={"payload": {"event_type": "unauthorised_absence", "route": "skilled_worker", "consecutive_working_days": 11}},
        ),
        lambda: _measured("assess_change_impact", lambda: assess_change_impact(payload), billable=True, meta=meta),
        meta=meta,
    )


@mcp.tool(
    name="batch_assess_changes",
    description=(
        "PAID multi-event decision tool ($0.05). Use when a caller has multiple Skilled Worker sponsor changes and wants one batch result "
        "with outcome counts and an evidence-linked decision for each event. Accepts up to 25 events. Use assess_change_impact for exactly "
        "one event."
    ),
)
def _tool_batch(items: list[dict[str, Any]], ctx: Context | None = None) -> Any:
    meta = _meta(ctx)
    return invoke(
        PaidToolSpec(
            name="batch_assess_changes",
            price=PRICE_BATCH,
            description="Batch sponsor change-impact preflight for up to 25 Skilled Worker events.",
            tags=["uk", "skilled-worker", "sponsor", "batch", "compliance"],
            example={"items": [{"event_type": "salary_change", "route": "skilled_worker"}]},
        ),
        lambda: _measured("batch_assess_changes", lambda: batch_assess_changes(items), billable=True, meta=meta),
        meta=meta,
    )


async def _health(_request) -> JSONResponse:
    source = production_source_status()
    return JSONResponse(
        {
            "status": "ok",
            "service": "England Works Watch",
            "version": SERVICE_VERSION,
            "production_ready": source.get("coverage_complete", False),
            "payment_enforced": PAYMENT_ENFORCED,
            "scope": RULES["scope"],
            "rule_pack_version": RULES["version"],
            "source_gate": source.get("coverage_complete", False),
            "source_baselines": f"{source.get('baseline_count', 0)}/{source.get('source_count', 0)}",
            "blocking_sources": source.get("blocking_sources", []),
        }
    )


async def _status(_request) -> JSONResponse:
    return JSONResponse({"service": _server_card(), "source_status": production_source_status()})


async def _version(_request) -> JSONResponse:
    return JSONResponse({"service": "England Works Watch", "version": SERVICE_VERSION, "rule_pack_version": RULES["version"]})


async def _analytics(_request) -> JSONResponse:
    return JSONResponse(summary())


async def _robots(_request) -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nAllow: /\nSitemap: " + PUBLIC_ORIGIN + "/sitemap.xml\n")


async def _sitemap(_request) -> Response:
    urls = ["/", "/health", "/status", "/version", "/openapi.json", "/llms.txt", "/.well-known/x402", "/.well-known/mcp.json"]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(
        f"  <url><loc>{PUBLIC_ORIGIN}{path}</loc></url>" for path in urls
    ) + "\n</urlset>\n"
    return Response(body, media_type="application/xml")


async def _llms(_request) -> PlainTextResponse:
    return PlainTextResponse(
        "# England Works Watch\n\n"
        "UK Skilled Worker sponsor compliance/change intelligence MCP for employer HR/People Ops and agent workflows.\n"
        f"MCP endpoint: {PUBLIC_MCP_URL}\n"
        "Free discovery/status tools: england_works_watch_info, licensing_source_status, list_supported_change_events.\n"
        f"Paid decision tools: assess_change_impact ({PRICE_ASSESS}), batch_assess_changes ({PRICE_BATCH}).\n"
        "Outcomes: AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, INSUFFICIENT_INPUT.\n"
        "Official GOV.UK evidence; deterministic rules; fail closed on missing/stale/conflicting evidence.\n"
        "Not legal advice.\n"
    )


async def _openapi(_request) -> JSONResponse:
    return JSONResponse(
        {
            "openapi": "3.1.0",
            "info": {"title": "England Works Watch", "version": SERVICE_VERSION, "description": SERVER_SELECTION_DESCRIPTION},
            "servers": [{"url": PUBLIC_ORIGIN}],
            "paths": {
                "/health": {"get": {"summary": "Health and source gate"}},
                "/status": {"get": {"summary": "Service/payment/source status"}},
                "/analytics/summary": {"get": {"summary": "Privacy-minimal aggregate analytics"}},
                "/mcp": {"post": {"summary": "MCP Streamable HTTP endpoint"}},
            },
            "x-mcp": {"endpoint": PUBLIC_MCP_URL, "transport": "streamable-http"},
            "x-payment": _payment_info(),
        }
    )


async def _x402(_request) -> JSONResponse:
    return JSONResponse(
        {
            "x402Version": 2,
            "service": "England Works Watch",
            "payment_enforced": PAYMENT_ENFORCED,
            "network": NETWORK,
            "asset": "USDC",
            "pay_to": PAY_TO or None,
            "facilitator": FACILITATOR,
            "paid_tools": {
                "assess_change_impact": {"price": PRICE_ASSESS, "resource": "mcp://tool/assess_change_impact"},
                "batch_assess_changes": {"price": PRICE_BATCH, "resource": "mcp://tool/batch_assess_changes"},
            },
        }
    )


async def _mcp_manifest(_request) -> JSONResponse:
    return JSONResponse(
        {
            "name": "io.github.ChanghuLiu/england-works-watch",
            "description": SERVER_SELECTION_DESCRIPTION,
            "version": SERVICE_VERSION,
            "remotes": [{"type": "streamable-http", "url": PUBLIC_MCP_URL}],
        }
    )


async def _server_card_route(_request) -> JSONResponse:
    return JSONResponse(_server_card())


async def _agent_card(_request) -> JSONResponse:
    return JSONResponse(
        {
            "name": "England Works Watch",
            "description": SERVER_SELECTION_DESCRIPTION,
            "url": PUBLIC_MCP_URL,
            "version": SERVICE_VERSION,
            "skills": [
                {"id": "sponsor-source-status", "name": "Official source freshness", "tags": ["ukvi", "sponsor", "evidence"]},
                {"id": "sponsor-event-list", "name": "Supported sponsor change events", "tags": ["skilled-worker", "hris"]},
                {"id": "sponsor-change-impact", "name": "Single sponsor change-impact preflight", "tags": ["x402", "compliance"]},
                {"id": "sponsor-change-batch", "name": "Batch sponsor change-impact preflight", "tags": ["x402", "batch"]},
            ],
        }
    )


async def _glama(_request) -> JSONResponse:
    return JSONResponse(
        {
            "$schema": "https://glama.ai/mcp/schemas/server.json",
            "maintainers": ["github:ChanghuLiu"],
            "name": "England Works Watch",
            "description": SERVER_SELECTION_DESCRIPTION,
            "server": {"type": "remote", "url": PUBLIC_MCP_URL, "transport": "streamable-http"},
        }
    )


async def _home(_request) -> PlainTextResponse:
    return PlainTextResponse(
        "England Works Watch — UK Skilled Worker sponsor compliance/change intelligence for AI agents.\n"
        f"MCP: {PUBLIC_MCP_URL}\n"
        "Decision labels: AFFECTED | NOT_AFFECTED | REVIEW_REQUIRED | INSUFFICIENT_INPUT\n"
    )


def build_app():
    ensure_runtime_seeded()
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route

    mcp_http = mcp.streamable_http_app(stateless_http=True, json_response=True)
    routes = [
        Route("/", _home, methods=["GET"]),
        Route("/health", _health, methods=["GET"]),
        Route("/status", _status, methods=["GET"]),
        Route("/version", _version, methods=["GET"]),
        Route("/analytics/summary", _analytics, methods=["GET"]),
        Route("/metrics", _analytics, methods=["GET"]),
        Route("/robots.txt", _robots, methods=["GET"]),
        Route("/sitemap.xml", _sitemap, methods=["GET"]),
        Route("/llms.txt", _llms, methods=["GET"]),
        Route("/openapi.json", _openapi, methods=["GET"]),
        Route("/.well-known/x402", _x402, methods=["GET"]),
        Route("/.well-known/mcp.json", _mcp_manifest, methods=["GET"]),
        Route("/.well-known/mcp/server-card.json", _server_card_route, methods=["GET"]),
        Route("/.well-known/agent-card.json", _agent_card, methods=["GET"]),
        Route("/.well-known/agent.json", _agent_card, methods=["GET"]),
        Route("/.well-known/glama.json", _glama, methods=["GET"]),
        Mount("/mcp", app=mcp_http),
    ]
    app = Starlette(routes=routes)
    app = MCP2X402Gate(
        app,
        payment_enforced=PAYMENT_ENFORCED,
        pay_to=PAY_TO,
        network=NETWORK,
        facilitator_url=FACILITATOR,
    )
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="England Works Watch")
    parser.add_argument("--http", action="store_true", help="run Streamable HTTP server")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()

    if args.http:
        import uvicorn

        start_background_source_monitor()
        uvicorn.run(build_app(), host=args.host, port=args.port, log_level="info")
    else:
        raise SystemExit("Use --http for production Streamable HTTP")


if __name__ == "__main__":
    main()
