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
        "evidence": "Official GOV.UK sponsor guidance with persistent semantic fingerprints and fail-closed review state.",
        "payment": _payment_info(),
        "safety": "Evidence-first sponsor compliance preflight; not legal advice or a Home Office decision.",
    }


@mcp.tool(annotations=READ, structured_output=True)
def england_works_watch_info(ctx: Context) -> dict[str, Any]:
    """Free product scope, supported events, prices and payment/discovery metadata."""
    return _measured(
        "england_works_watch_info",
        lambda: {
            "service": "England Works Watch",
            "description": SERVER_SELECTION_DESCRIPTION,
            "scope": RULES["scope"],
            "supported_events": SUPPORTED_EVENTS,
            "decision_labels": ["AFFECTED", "NOT_AFFECTED", "REVIEW_REQUIRED", "INSUFFICIENT_INPUT"],
            "payment": _payment_info(),
            "evidence": "Official GOV.UK sponsor guidance with persistent runtime fingerprint/change monitoring.",
            "discovery": {
                "mcp": PUBLIC_MCP_URL,
                "server_card": f"{PUBLIC_ORIGIN}/.well-known/mcp/server-card.json",
                "x402": f"{PUBLIC_ORIGIN}/.well-known/x402",
                "llms": f"{PUBLIC_ORIGIN}/llms.txt",
                "openapi": f"{PUBLIC_ORIGIN}/openapi.json",
            },
            "not_legal_advice": True,
        },
        billable=False,
        meta=_meta(ctx),
    )


@mcp.tool(annotations=READ, structured_output=True)
def licensing_source_status(ctx: Context) -> dict[str, Any]:
    """Free official-source lifecycle, fingerprint, freshness and review status."""
    return _measured("licensing_source_status", production_source_status, billable=False, meta=_meta(ctx))


@mcp.tool(annotations=READ, structured_output=True)
def list_supported_change_events(ctx: Context) -> dict[str, Any]:
    """Free list of V0.1 sponsor change event types."""
    return _measured(
        "list_supported_change_events",
        lambda: {
            "events": SUPPORTED_EVENTS,
            "rule_pack_version": RULES["rule_pack_version"],
            "effective_date": RULES["effective_date"],
        },
        billable=False,
        meta=_meta(ctx),
    )


def _assess(args: dict[str, Any]) -> dict[str, Any]:
    status = production_source_status()
    if not status["coverage_complete"]:
        return {
            "status": "REVIEW_REQUIRED",
            "decision_code": "EW-SOURCE-LIFECYCLE-GATE",
            "event_type": str(args.get("event_type", "unknown")),
            "scope": RULES["scope"],
            "rule_pack_version": RULES["rule_pack_version"],
            "effective_date": RULES["effective_date"],
            "rationale": ["Required official-source evidence is changed pending review, stale, or otherwise blocked."],
            "required_actions": ["Review blocking official sources before relying on a deterministic decision."],
            "missing_inputs": [],
            "review_reasons": [f"blocking_source:{item}" for item in status["blocking_sources"]],
            "affected_rules": [],
            "source_runtime": {
                "blocking_sources": status["blocking_sources"],
                "review_required_sources": status["review_required_sources"],
                "stale_sources": status["stale_sources"],
            },
            "disclaimer": "Evidence-first sponsor compliance preflight. Not legal advice.",
        }
    return decide(args)


def _batch(args: dict[str, Any]) -> dict[str, Any]:
    changes = args.get("changes") or []
    if not isinstance(changes, list) or not 1 <= len(changes) <= 25:
        return {"status": "INSUFFICIENT_INPUT", "error": "changes must contain 1..25 structured change events"}
    results = [_assess(item if isinstance(item, dict) else {}) for item in changes]
    return {
        "scope": RULES["scope"],
        "rule_pack_version": RULES["rule_pack_version"],
        "total": len(results),
        "counts": {
            state: sum(1 for result in results if result.get("status") == state)
            for state in ["AFFECTED", "NOT_AFFECTED", "REVIEW_REQUIRED", "INSUFFICIENT_INPUT"]
        },
        "results": results,
    }


# Public MCP contract deliberately uses an ordinary JSON payload object, matching
# the proven UK Taxi MCP 2.x production bridge. Deterministic validation happens
# inside the policy layer so ambiguous/missing facts produce explicit fail-closed
# decisions rather than transport-specific schema surprises.
if PAYMENT_ENFORCED:
    gate = MCP2X402Gate()
    paid_assess = gate.build(
        PaidToolSpec(
            "assess_change_impact",
            PRICE_ASSESS,
            "Official-source-backed Skilled Worker sponsor change-impact preflight.",
        ),
        _assess,
    )
    paid_batch = gate.build(
        PaidToolSpec(
            "batch_assess_changes",
            PRICE_BATCH,
            "Batch Skilled Worker sponsor change-impact preflight for up to 25 events.",
        ),
        _batch,
    )

    @mcp.tool(annotations=READ)
    def assess_change_impact(payload: dict[str, Any], ctx: Context):
        """Paid deterministic Skilled Worker sponsor change-impact preflight. Requires x402 USDC payment."""
        return invoke(paid_assess, tool_name="assess_change_impact", arguments=dict(payload), ctx=ctx)

    @mcp.tool(annotations=READ)
    def batch_assess_changes(payload: dict[str, Any], ctx: Context):
        """Paid batch change-impact preflight for 1..25 sponsor events. Requires x402 USDC payment."""
        return invoke(paid_batch, tool_name="batch_assess_changes", arguments=dict(payload), ctx=ctx)
else:

    @mcp.tool(annotations=READ, structured_output=True)
    def assess_change_impact(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
        """Deterministic Skilled Worker sponsor change-impact preflight; x402 disabled in this environment."""
        return _measured(
            "assess_change_impact",
            lambda: _assess(dict(payload)),
            billable=True,
            meta=_meta(ctx),
        )

    @mcp.tool(annotations=READ, structured_output=True)
    def batch_assess_changes(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
        """Batch deterministic sponsor change-impact preflight; x402 disabled in this environment."""
        return _measured(
            "batch_assess_changes",
            lambda: _batch(dict(payload)),
            billable=True,
            meta=_meta(ctx),
        )


@mcp.custom_route("/", methods=["GET"])
async def product_page(_request):
    source = production_source_status()
    return JSONResponse(
        {
            "service": "England Works Watch",
            "version": SERVICE_VERSION,
            "description": SERVER_SELECTION_DESCRIPTION,
            "scope": RULES["scope"],
            "mcp": PUBLIC_MCP_URL,
            "source_gate": source["coverage_complete"],
            "payment": _payment_info(),
            "docs": f"{PUBLIC_ORIGIN}/llms.txt",
        }
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    source = production_source_status()
    ready = source["coverage_complete"]
    return JSONResponse(
        {
            "status": "ok" if ready else "review_required",
            "service": "England Works Watch",
            "version": SERVICE_VERSION,
            "production_ready": ready,
            "payment_enforced": PAYMENT_ENFORCED,
            "scope": RULES["scope"],
            "rule_pack_version": RULES["rule_pack_version"],
            "source_gate": ready,
            "source_baselines": f"{source['sources_with_fingerprint_baseline']}/{source['total_sources']}",
            "blocking_sources": source["blocking_sources"],
        },
        status_code=200 if ready else 503,
    )


@mcp.custom_route("/status", methods=["GET"])
async def status(_request):
    return JSONResponse(
        {
            "service": "England Works Watch",
            "version": SERVICE_VERSION,
            "payment": _payment_info(),
            "sources": production_source_status(),
            "analytics": summary(),
        }
    )


@mcp.custom_route("/version", methods=["GET"])
async def version(_request):
    return JSONResponse(
        {
            "service": "England Works Watch",
            "version": SERVICE_VERSION,
            "rule_pack_version": RULES["rule_pack_version"],
            "effective_date": RULES["effective_date"],
            "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV"),
        }
    )


@mcp.custom_route("/metrics", methods=["GET"])
async def metrics(_request):
    source = production_source_status()
    return JSONResponse(
        {
            "usage": summary(),
            "source": {
                "total_sources": source["total_sources"],
                "fingerprint_baselines": source["sources_with_fingerprint_baseline"],
                "blocking_sources": len(source["blocking_sources"]),
                "review_required_sources": len(source["review_required_sources"]),
                "stale_sources": len(source["stale_sources"]),
                "fetch_status_counts": source["fetch_status_counts"],
            },
        }
    )


@mcp.custom_route("/analytics/summary", methods=["GET"])
async def analytics_summary(_request):
    return JSONResponse(summary())


@mcp.custom_route("/llms.txt", methods=["GET"])
async def llms(_request):
    return PlainTextResponse(
        f"England Works Watch — UK sponsor compliance/change intelligence\n"
        f"MCP: {PUBLIC_MCP_URL}\n"
        "Scope: Skilled Worker sponsor duties only.\n"
        "Free MCP tools: england_works_watch_info, licensing_source_status, list_supported_change_events.\n"
        f"Paid: assess_change_impact {PRICE_ASSESS}; batch_assess_changes {PRICE_BATCH}.\n"
        "Use when an employer/HR/HRIS Agent needs deterministic evidence-backed sponsor change impact.\n"
        "Decision arguments use a top-level payload object containing structured change facts.\n"
        "Official GOV.UK evidence is fingerprinted continuously; changed/stale evidence fails closed.\n"
        "Never treat REVIEW_REQUIRED or INSUFFICIENT_INPUT as clearance. Not legal advice.\n"
    )


@mcp.custom_route("/robots.txt", methods=["GET"])
async def robots(_request):
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_ORIGIN}/sitemap.xml\n")


@mcp.custom_route("/sitemap.xml", methods=["GET"])
async def sitemap(_request):
    urls = ["/", "/llms.txt", "/openapi.json", "/.well-known/mcp.json", "/.well-known/agent-card.json", "/.well-known/x402"]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{PUBLIC_ORIGIN}{path}</loc></url>" for path in urls
    ) + "</urlset>"
    return Response(body, media_type="application/xml")


@mcp.custom_route("/.well-known/x402", methods=["GET"])
async def x402_info(_request):
    result = {
        "x402Version": 2,
        "scheme": "exact",
        "network": NETWORK,
        "asset": "USDC",
        "payment_enforced": PAYMENT_ENFORCED,
        "tools": {
            "assess_change_impact": {"price": PRICE_ASSESS},
            "batch_assess_changes": {"price": PRICE_BATCH},
        },
        "facilitator": FACILITATOR,
        "payment_flow": [
            "Call a paid MCP tool to receive the x402 PaymentRequired challenge.",
            "Sign accepted Base-USDC authorization buyer-side.",
            "Retry the same MCP tool call with payment metadata.",
            "Payment is verified before deterministic decision execution; stale or changed evidence still fails closed.",
        ],
        "buyer_security": "Never send private keys or seed phrases to this service. Authorization is signed buyer-side.",
    }
    if PAY_TO:
        result["pay_to"] = PAY_TO
    return JSONResponse(result)


@mcp.custom_route("/.well-known/mcp.json", methods=["GET"])
async def mcp_json(_request):
    return JSONResponse(
        {
            "name": "io.github.ChanghuLiu/england-works-watch",
            "version": SERVICE_VERSION,
            "description": SERVER_SELECTION_DESCRIPTION,
            "remotes": [{"type": "streamable-http", "url": PUBLIC_MCP_URL}],
        }
    )


@mcp.custom_route("/.well-known/mcp/server-card.json", methods=["GET"])
async def server_card(_request):
    return JSONResponse(_server_card())


@mcp.custom_route("/.well-known/agent-card.json", methods=["GET"])
async def agent_card(_request):
    return JSONResponse(
        {
            "name": "England Works Watch",
            "description": "Deterministic official-source-backed sponsor change-impact tool for employer agents.",
            "url": PUBLIC_ORIGIN,
            "mcp": PUBLIC_MCP_URL,
            "capabilities": {
                "change_impact": SUPPORTED_EVENTS,
                "source_freshness": True,
                "batch": True,
                "x402": True,
            },
            "instructions": "Read free source status before a paid decision. Escalate REVIEW_REQUIRED or INSUFFICIENT_INPUT.",
        }
    )


@mcp.custom_route("/.well-known/agent.json", methods=["GET"])
async def agent_json(_request):
    return JSONResponse(
        {
            "name": "England Works Watch",
            "url": PUBLIC_ORIGIN,
            "mcp_endpoint": PUBLIC_MCP_URL,
            "purpose": "UK Skilled Worker sponsor compliance/change intelligence",
            "payment": _payment_info(),
        }
    )


@mcp.custom_route("/.well-known/glama.json", methods=["GET"])
async def glama_json(_request):
    return JSONResponse(
        {
            "name": "England Works Watch",
            "description": "UK Skilled Worker sponsor compliance/change intelligence via remote MCP.",
            "serverUrl": PUBLIC_MCP_URL,
            "transport": "streamable-http",
            "repository": "https://github.com/ChanghuLiu/england-works-watch",
        }
    )


@mcp.custom_route("/openapi.json", methods=["GET"])
async def openapi(_request):
    return JSONResponse(
        {
            "openapi": "3.1.0",
            "info": {
                "title": "England Works Watch",
                "version": SERVICE_VERSION,
                "description": SERVER_SELECTION_DESCRIPTION,
            },
            "paths": {
                "/health": {"get": {"summary": "Serving/source readiness gate"}},
                "/status": {"get": {"summary": "Runtime source/payment/analytics status"}},
                "/version": {"get": {"summary": "Release and rule-pack identity"}},
                "/metrics": {"get": {"summary": "Aggregate-only usage and source counters"}},
                "/mcp": {"post": {"summary": "MCP Streamable HTTP endpoint"}},
                "/.well-known/x402": {"get": {"summary": "x402 payment discovery"}},
            },
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    ensure_runtime_seeded()
    start_background_source_monitor()
    if args.http:
        mcp.run(
            transport="streamable-http",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            json_response=True,
            stateless_http=True,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
