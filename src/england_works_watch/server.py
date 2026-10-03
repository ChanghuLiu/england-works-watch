from __future__ import annotations
from .purchase_ui import polish_page, browser_report_response

import argparse
import os
import secrets
import time
from typing import Any, Mapping
from urllib.parse import parse_qs, urlencode

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from .analytics import record, summary
from .attribution import OWNER_TEST_MARKERS, is_automated_user_agent
from .commercial import CommercialPlatformClient, CommercialPlatformError, CommercialSettings, PendingMonitoringCheckoutStore, commercial_source_channel
from .case_state import DurableCaseStore
from .entitlement_token import verify_entitlement_token
from .monitoring import changed_since, make_checkpoint
from .ops_contract import build_alerts, health_payload, status_payload, version_payload
from .policy import RULES, SOURCE_BY_ID, assess_change_impact as decide
from .public_surfaces import monitoring_page, policy_copy, render_policy_page, render_pricing_page
from .selection_metadata import (
    FREE_PAID_BOUNDARY,
    PAID_RESULT_PREVIEW,
    PAYMENT_GUIDANCE,
    SERVER_SELECTION_DESCRIPTION,
)
from .source_runtime import ensure_runtime_seeded, production_source_status, start_background_source_monitor
from .x402_gate import MCP2X402Gate, PaidToolSpec, invoke, meta_to_dict

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
SERVICE_VERSION = "0.1.2"
PUBLIC_ORIGIN = os.getenv("EWW_PUBLIC_ORIGIN", "https://works.regevidencehub.com").rstrip("/")
PUBLIC_MCP_URL = f"{PUBLIC_ORIGIN}/mcp"
PRICE_ASSESS = os.getenv("EWW_X402_PRICE_ASSESS", "$0.02")
PRICE_BATCH = os.getenv("EWW_X402_PRICE_BATCH", "$0.05")
PAYMENT_ENFORCED = os.getenv("EWW_PAYMENT_ENFORCED", "0").strip().lower() in {"1", "true", "yes", "on"}
PAY_TO = os.getenv("EWW_X402_PAY_TO", "").strip()
NETWORK = os.getenv("EWW_X402_NETWORK", "eip155:8453").strip()
FACILITATOR = os.getenv("EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network").strip()
COMMERCIAL_SETTINGS = CommercialSettings.from_env()
COMMERCIAL_CLIENT = CommercialPlatformClient(COMMERCIAL_SETTINGS)
CASE_RUNTIME_DIR = os.getenv("EWW_RUNTIME_DIR") or ("/data/england-works-watch" if os.getenv("RAILWAY_ENVIRONMENT") else "/tmp/england-works-watch")
PENDING_MONITORING_CHECKOUTS = PendingMonitoringCheckoutStore(
    COMMERCIAL_SETTINGS.pending_ttl_seconds,
    path=os.getenv("EWW_PENDING_STORE_PATH", "").strip() or os.path.join(CASE_RUNTIME_DIR, "pending-monitoring.json"),
)
DURABLE_CASES = DurableCaseStore(CASE_RUNTIME_DIR, ttl_seconds=int(os.getenv("EWW_CASE_TTL_SECONDS", "86400")))
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
        "recommended_paid_paths": {
            "batch_api": {
                "tool": "batch_assess_changes",
                "value": "Primary paid API path for repeated work: assess 1-25 structured sponsor changes in one call.",
            },
            "monitoring_report": {
                "url": f"{PUBLIC_ORIGIN}/monitoring-report",
                "price": "£49",
                "access": "30 days",
                "value": "Create a dated checkpoint across four core GOV.UK sponsor sources before a sponsor decision, then re-check the same evidence for 30 days through a private reusable link.",
            },
            "single_event_api": {
                "tool": "assess_change_impact",
                "positioning": "Metered programmatic compatibility path; a one-off interactive preflight is available on the public AI edition.",
            },
        },
        "buyer_security": "Never send private keys or seed phrases to this service; payment authorization is signed buyer-side.",
    }
    if PAY_TO:
        result["pay_to"] = PAY_TO
    return result


def _value_preview() -> dict[str, Any]:
    return {
        "free_paid_boundary": FREE_PAID_BOUNDARY,
        "example_paid_result": PAID_RESULT_PREVIEW,
        "payment_guidance": PAYMENT_GUIDANCE,
    }


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
        "commercial_value_paths": {
            "primary_api": "batch_assess_changes for 1-25 events",
            "continued_monitoring": f"{PUBLIC_ORIGIN}/monitoring-report for a 30-day Sponsor Decision Evidence Check",
            "single_event_api": "assess_change_impact retained for metered programmatic compatibility",
        },
        "decision_argument_shape": {
            "payload": {
                "event_type": "unauthorised_absence",
                "route": "skilled_worker",
                "consecutive_working_days": 11,
            }
        },
        "evidence": "Official GOV.UK sponsor guidance with persistent semantic fingerprints and fail-closed review state.",
        "payment": _payment_info(),
        "value_preview": _value_preview(),
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
            "value_preview": _value_preview(),
        },
        billable=False,
        meta=_meta(ctx),
    )


def _commercial_source_status_payload() -> dict[str, Any]:
    """Add a bounded commercial next step without changing source-health semantics."""
    status = dict(production_source_status())
    status["recommended_next_step"] = {
        "when": "If source status is usable and a sponsor decision needs a dated evidence checkpoint or repeated commercial assessment.",
        "single_event": {
            "tool": "assess_change_impact",
            "price": PRICE_ASSESS,
            "use_for": "One structured sponsor change requiring metered programmatic execution.",
        },
        "batch_or_repeated": {
            "tool": "batch_assess_changes",
            "price": PRICE_BATCH,
            "max_events": 25,
            "use_for": "Two to 25 sponsor changes, batch processing, or repeated automation.",
        },
        "continued_evidence_baseline": {
            "url": f"{PUBLIC_ORIGIN}/monitoring-report",
            "price": "£49",
            "access": "30 days",
            "use_for": (
                "Before salary, role, work-location, long-absence, delayed-start, stopping-sponsorship, "
                "TUPE, merger or takeover decisions when a dated record of the current four core GOV.UK "
                "sponsor sources is useful; re-check the same evidence for 30 days through a private link."
            ),
            "boundary": "No worker names or case facts are required; this does not decide sponsor cases or send alerts.",
        },
        "payment": {
            "protocol": "x402-v2",
            "network": NETWORK,
            "asset": "USDC",
            "instruction": "Call the paid tool to receive PaymentRequired, sign buyer-side, then retry the same tool.",
        },
    }
    return status


@mcp.tool(annotations=READ, structured_output=True)
def licensing_source_status(ctx: Context) -> dict[str, Any]:
    """Free official-source lifecycle, fingerprint, freshness and review status plus the next commercial decision path."""
    return _measured("licensing_source_status", _commercial_source_status_payload, billable=False, meta=_meta(ctx))


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
            "Metered programmatic single-event Skilled Worker sponsor change-impact decision. Use when an agent/runtime needs one-event API execution; for a one-off interactive check, the public AI edition is usually sufficient. Returns evidence-linked rationale, required action/deadline fields, and explicit review or missing-input state. For multiple events use batch_assess_changes. x402 Base mainnet USDC: sign buyer-side and retry this same tool with payment metadata.",
        ),
        _assess,
    )
    paid_batch = gate.build(
        PaidToolSpec(
            "batch_assess_changes",
            PRICE_BATCH,
            "Primary paid API for repeated sponsor-compliance work. Assess 1-25 structured Skilled Worker sponsor changes in one call, returning evidence-linked per-event results and outcome counts. Use for lists, batches, multiple employees or organisation changes, HR/HRIS workflows, and agent automation. x402 Base mainnet USDC: sign buyer-side and retry this same tool with payment metadata.",
        ),
        _batch,
    )

    @mcp.tool(annotations=READ)
    def assess_change_impact(payload: dict[str, Any], ctx: Context):
        """Metered paid API for one sponsor-change event. Use for programmatic one-event execution; use batch_assess_changes for multiple events. A one-off interactive preflight is available on the public AI edition. Requires x402 USDC payment."""
        return invoke(paid_assess, tool_name="assess_change_impact", arguments=dict(payload), ctx=ctx)

    @mcp.tool(annotations=READ)
    def batch_assess_changes(payload: dict[str, Any], ctx: Context):
        """Primary paid API for repeated work: assess 1..25 sponsor events in one call with per-event results and outcome counts. Use for batches, lists, multiple employees or organisation changes, and agent automation. Requires x402 USDC payment."""
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


@mcp.custom_route("/api/v1/continuation-case", methods=["POST"])
async def continuation_case(request):
    try:
        body = await request.json()
        action = str(body.get("action") or "sponsor_change_impact_preflight")
        if action != "sponsor_change_impact_preflight":
            return JSONResponse({"status": "invalid_request", "error_code": "unsupported_action"}, status_code=422)
        payload = body.get("payload") or {}
        if not isinstance(payload, dict) or not isinstance(payload.get("event_type"), str):
            return JSONResponse({"status": "invalid_request", "error_code": "invalid_payload"}, status_code=422)
        result = _assess(dict(payload))
        if result.get("status") == "INSUFFICIENT_INPUT":
            return JSONResponse({"status": "invalid_request", "error_code": "insufficient_input", "decision": result}, status_code=422)
        source_bucket = str(body.get("source_bucket") or "direct")
        classification = str(body.get("classification") or "unknown")
        owner_test = bool(body.get("owner_test") or False)
        if classification not in {"unknown", "confirmed_external", "owner_test", "synthetic"}:
            return JSONResponse({"status": "invalid_request", "error_code": "invalid_classification"}, status_code=422)
    except Exception:
        return JSONResponse({"status": "invalid_request"}, status_code=422)
    row = DURABLE_CASES.create(action=action, payload=payload, source_bucket=source_bucket, classification=classification, owner_test=owner_test)
    try:
        continuation = await COMMERCIAL_CLIENT.issue_continuation(case_ref=row.case_ref, state_ref=row.state_ref)
    except Exception:
        return JSONResponse({"status": "commercial_unavailable"}, status_code=503)
    return JSONResponse({
        "product_id": COMMERCIAL_SETTINGS.product_id,
        "case_ref": row.case_ref,
        "state_ref": row.state_ref,
        "continuation_token": continuation["continuation_token"],
        "expires_in_seconds": continuation.get("expires_in_seconds"),
    })

@mcp.custom_route("/api/v1/execute-restored-case", methods=["POST"])
async def execute_restored_case(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"status": "invalid_request"}, status_code=422)
    if body.get("contract_version") not in {None, "reh-execution-v1"}:
        return JSONResponse({"status":"invalid_request","error_code":"unsupported_contract_version"}, status_code=422)
    if body.get("product_id") not in {None, COMMERCIAL_SETTINGS.product_id}:
        return JSONResponse({"status":"invalid_request","error_code":"wrong_product"}, status_code=422)
    if body.get("action") not in {None, "sponsor_change_impact_preflight"}:
        return JSONResponse({"status":"invalid_request","error_code":"unsupported_action"}, status_code=422)
    try:
        claims = await verify_entitlement_token(
            str(body.get("entitlement_token") or ""),
            platform_url=COMMERCIAL_SETTINGS.platform_url,
            expected_product_id=COMMERCIAL_SETTINGS.product_id,
        )
    except ValueError:
        return JSONResponse({"status":"forbidden"}, status_code=403)
    row = DURABLE_CASES.get(str(body.get("state_ref") or ""))
    if row is None:
        return JSONResponse({"status":"case_unavailable","error_code":"state_not_found"}, status_code=404)
    if row.action != "sponsor_change_impact_preflight":
        return JSONResponse({"status":"invalid_request","error_code":"stored_action_mismatch"}, status_code=422)
    try:
        decision = _assess(dict(row.payload))
    except Exception:
        return JSONResponse({
            "contract_version":"reh-execution-v1","product_id":COMMERCIAL_SETTINGS.product_id,"status":"failed",
            "execution_id":f"eww_{secrets.token_hex(12)}","result":None,"error_code":"execution_unavailable"
        }, status_code=503)
    return JSONResponse({
        "contract_version":"reh-execution-v1",
        "product_id":COMMERCIAL_SETTINGS.product_id,
        "status":"executed",
        "execution_id":f"eww_{secrets.token_hex(12)}",
        "result":{"gateway_status":"OK","decision":decision,"entitlement_code":str(claims.get("entitlement_code") or "")},
        "error_code":None,
    })

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
            "value_preview": _value_preview(),
            "docs": f"{PUBLIC_ORIGIN}/llms.txt",
            "smithery": "https://smithery.ai/servers/liuchanghu2018/england-works-watch",
        }
    )


def _ops_snapshot():
    source = production_source_status()
    analytics = summary()
    window = ((analytics.get("windows") or {}).get("24h") or {}) if isinstance(analytics, dict) else {}
    payment_errors = int(window.get("payment_errors") or 0) if isinstance(window, dict) else 0
    source_issue_count = (
        len(source.get("blocking_sources") or [])
        + len(source.get("review_required_sources") or [])
        + len(source.get("stale_sources") or [])
    )
    if not source.get("coverage_complete"):
        source_state = "degraded"
    elif source_issue_count:
        source_state = "review_required"
    else:
        source_state = "ready"
    payment_state = "degraded" if payment_errors else ("ready" if PAYMENT_ENFORCED else "disabled")
    service_degraded = False
    return source, analytics, source_state, payment_state, source_issue_count, payment_errors, service_degraded


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    source, _analytics, source_state, payment_state, _source_issue_count, _payment_errors, service_degraded = _ops_snapshot()
    payload = health_payload(
        service="England Works Watch",
        version=SERVICE_VERSION,
        commit=os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV") or "unknown",
        source_state=source_state,
        payment_state=payment_state,
        service_degraded=service_degraded,
    )
    payload.update({
        "scope": RULES["scope"],
        "rule_pack_version": RULES["rule_pack_version"],
        "source_baselines": f"{source['sources_with_fingerprint_baseline']}/{source['total_sources']}",
        "payment_enforced": PAYMENT_ENFORCED,
        "production_ready": source.get("coverage_complete") is True,
    })
    return JSONResponse(payload, status_code=200, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/status", methods=["GET"])
async def status(_request):
    source, analytics, source_state, payment_state, source_issue_count, payment_errors, service_degraded = _ops_snapshot()
    alerts = build_alerts(
        source_state=source_state,
        source_issue_count=source_issue_count,
        payment_errors=payment_errors,
        service_degraded=service_degraded,
    )
    payload = status_payload(
        service="England Works Watch",
        version=SERVICE_VERSION,
        commit=os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV") or "unknown",
        source_state=source_state,
        payment_state=payment_state,
        alerts=alerts,
        service_degraded=service_degraded,
    )
    payload.update({
        "payment": _payment_info(),
        "sources": source,
        "analytics_24h": ((analytics.get("windows") or {}).get("24h") or {}) if isinstance(analytics, dict) else {},
    })
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


@mcp.custom_route("/version", methods=["GET"])
async def version(_request):
    payload = version_payload(
        service="England Works Watch",
        version=SERVICE_VERSION,
        commit=os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV") or "unknown",
        public_origin=PUBLIC_ORIGIN,
    )
    payload.update({
        "rule_pack_version": RULES["rule_pack_version"],
        "effective_date": RULES["effective_date"],
    })
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


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


@mcp.custom_route("/pricing", methods=["GET"])
async def pricing(_request):
    return PlainTextResponse(
        render_pricing_page(
            origin=PUBLIC_ORIGIN,
            prices={
                "Single-event commercial API (assess_change_impact)": f"{PRICE_ASSESS} USDC per x402 call; programmatic compatibility path",
                "Primary paid batch API (batch_assess_changes)": f"{PRICE_BATCH} USDC per x402 call; 1-25 events",
                "30-day Sponsor Decision Evidence Check": "£49 via shared commercial Stripe checkout",
            },
        ),
        media_type="text/html",
    )


@mcp.custom_route("/privacy", methods=["GET"])
async def privacy(_request):
    return PlainTextResponse(render_policy_page("privacy", origin=PUBLIC_ORIGIN), media_type="text/html")


@mcp.custom_route("/terms", methods=["GET"])
async def terms(_request):
    return PlainTextResponse(render_policy_page("terms", origin=PUBLIC_ORIGIN), media_type="text/html")


@mcp.custom_route("/support", methods=["GET"])
async def support(_request):
    return PlainTextResponse(render_policy_page("support", origin=PUBLIC_ORIGIN), media_type="text/html")


@mcp.custom_route("/monitoring-report", methods=["GET"])
async def monitoring_report_entry(request):
    source_channel = commercial_source_channel(
        str(request.query_params.get("src") or "direct")
    )
    classification, owner_test = _monitoring_classification(request, {})
    await _safe_commercial_event(
        "discovery_observed",
        source_channel=source_channel,
        classification=classification,
        owner_test=owner_test,
    )
    return PlainTextResponse(
        monitoring_page(
            origin=PUBLIC_ORIGIN,
            source_channel=source_channel,
            owner_test=owner_test,
        ),
        media_type="text/html",
    )


async def _read_monitoring_request(request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:
            raise ValueError("Expected a JSON object body.") from exc
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object body.")
        return payload
    raw = (await request.body()).decode("utf-8", "replace")
    values = parse_qs(raw, keep_blank_values=True)
    return {key: (items if key == "source_ids" and len(items) > 1 else items[-1]) for key, items in values.items()}


def _monitoring_ids(payload: dict[str, Any]) -> list[str]:
    source_ids = payload.get("source_ids")
    if isinstance(source_ids, str):
        source_ids = [item.strip() for item in source_ids.split(",") if item.strip()]
    if not isinstance(source_ids, list) or not source_ids or len(source_ids) > 4 or any(not isinstance(item, str) or item not in SOURCE_BY_ID for item in source_ids):
        raise ValueError("source_ids must contain 1-4 known source IDs")
    return list(dict.fromkeys(source_ids))


def _monitoring_classification(request, payload: Mapping[str, Any]) -> tuple[str, bool]:
    """Use explicit attribution evidence only; never infer customer identity from PII or case facts."""
    headers = getattr(request, "headers", {})
    query = getattr(request, "query_params", {})
    raw = (
        headers.get("x-eww-human-run-class")
        or headers.get("x-eww-owner-test-marker")
        or payload.get("run_class")
        or payload.get("owner_test_marker")
        or query.get("run")
        or query.get("owner_test_marker")
        or ""
    )
    value = str(raw).strip().lower()
    if value in OWNER_TEST_MARKERS or value in {"owner", "owner_test", "test", "smoke", "ci"}:
        return "owner_test", True
    if value in {"synthetic", "fixture"}:
        return "synthetic", False

    # Automated traffic can never promote itself into customer evidence.
    user_agent = str(headers.get("user-agent") or "")
    if is_automated_user_agent(user_agent):
        return "automated_external", False

    confirmation = payload.get("independent_customer_confirmation")
    confirmed = confirmation is True or str(confirmation or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "independent",
        "confirmed_external",
    }
    if confirmed:
        return "confirmed_external", False
    return "unknown", False


async def _safe_commercial_event(
    event_type: str,
    *,
    source_channel: str,
    classification: str,
    owner_test: bool,
) -> None:
    """Commercial telemetry is optional and never gates a monitoring result."""
    try:
        await COMMERCIAL_CLIENT.record_event(
            event_type=event_type,
            source_channel=source_channel,
            commercial_intent="monitoring",
            external_classification=classification,
            owner_test=owner_test,
        )
    except Exception:
        return


@mcp.custom_route("/monitoring-report/checkout", methods=["POST"])
async def monitoring_report_checkout(request):
    try:
        payload = await _read_monitoring_request(request)
        source_ids = _monitoring_ids(payload)
        checkpoint = payload.get("checkpoint")
        if checkpoint is None:
            checkpoint = make_checkpoint(source_ids)
        if not isinstance(checkpoint, dict):
            raise ValueError("checkpoint must be an object when supplied")
        source_channel = commercial_source_channel(str(payload.get("source_channel") or request.query_params.get("src") or "direct"))
        classification, owner_test = _monitoring_classification(request, payload)
        await _safe_commercial_event(
            "paid_intent",
            source_channel=source_channel,
            classification=classification,
            owner_test=owner_test,
        )
        row = PENDING_MONITORING_CHECKOUTS.create(
            checkpoint=checkpoint,
            source_channel=source_channel,
            classification=classification,
            owner_test=owner_test,
        )
        contact_email = str(payload.get("contact_email") or "").strip()
        if not contact_email or len(contact_email) > 254 or contact_email.count("@") != 1 or any(ch.isspace() for ch in contact_email):
            return browser_report_response(request, {"status":"INVALID_REQUEST","detail":"A valid recovery email is required."}, status_code=422)
        checkout = await COMMERCIAL_CLIENT.create_report_checkout(
            contact_email=contact_email,
            source_channel=row.source_channel,
            external_classification=row.classification,
            owner_test=row.owner_test,
            success_url=COMMERCIAL_SETTINGS.checkout_success_url(row.return_token),
            cancel_url=str(COMMERCIAL_SETTINGS.cancel_url),
        )
        PENDING_MONITORING_CHECKOUTS.attach_checkout(row.return_token, checkout["checkout_id"])
        await _safe_commercial_event(
            "checkout_started",
            source_channel=row.source_channel,
            classification=row.classification,
            owner_test=row.owner_test,
        )
        result = {
            "status": "CHECKOUT_REQUIRED",
            "checkout_url": checkout["checkout_url"],
            "checkout_id": checkout["checkout_id"],
            "monitoring_scope": {
                "source_ids": source_ids,
                "stored": "opaque checkpoint only",
            },
        }

        # Browser form submission: continue directly to hosted Stripe Checkout.
        # JSON clients retain the existing machine-readable contract.
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            response = RedirectResponse(checkout["checkout_url"], status_code=303)
            response.set_cookie(key=f"report_claim_{checkout['checkout_id']}", value=checkout["report_claim_token"], max_age=1800,
                                httponly=True, secure=COMMERCIAL_SETTINGS.success_url.startswith("https://"), samesite="lax",
                                path="/monitoring-report/checkout-success")
            return response

        result["report_claim_token"] = checkout["report_claim_token"]

        return browser_report_response(request, result)

    except ValueError as exc:
        return browser_report_response(request, {"status": "INVALID_REQUEST", "detail": str(exc)}, status_code=400)
    except CommercialPlatformError as exc:
        return browser_report_response(request, {"status": "COMMERCIAL_UNAVAILABLE", "detail": str(exc)}, status_code=503)



def _monitoring_paid_page(*, entitlement_code: str, report: dict[str, Any], checkout_id: str) -> str:
    import json
    from datetime import datetime, timezone
    from html import escape
    from urllib.parse import urlencode

    def display_time(value: Any) -> str:
        raw = str(value or "")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return escape(parsed.astimezone(timezone.utc).strftime("%d %b %Y · %H:%M:%S UTC"))
        except ValueError:
            pass
        return escape(raw or "Not recorded")

    raw_status = str(report.get("status") or "UNKNOWN")
    status = escape(raw_status)
    status_class = "good" if raw_status == "UNCHANGED" else "review"
    checked_at = display_time(report.get("checked_at"))
    report_json = escape(json.dumps(report, indent=2, ensure_ascii=False))
    decision_usable = report.get("decision_usable") is True
    source_gate = report.get("source_gate") is True
    next_action = escape(str(report.get("next_action") or ""))
    disclaimer = escape(str(report.get("disclaimer") or ""))
    access_link = "/monitoring-report/checkout-success"
    recovery_link = escape("/monitoring-report/recover?" + urlencode({"checkout_id": checkout_id}), quote=True)

    rows = []
    sources = report.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            raw_source_id = str(source.get("source_id") or "")
            source_id = escape(raw_source_id)
            official = SOURCE_BY_ID.get(raw_source_id) or {}
            official_url = str(official.get("url") or "")
            source_label = (
                f'<a href="{escape(official_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'{escape(str(official.get("title") or raw_source_id))}</a>'
                if official_url.startswith("https://www.gov.uk/") else source_id
            )
            raw_source_status = str(source.get("status") or "UNKNOWN")
            source_status = escape(raw_source_status)
            source_class = "good" if raw_source_status == "UNCHANGED" else "review"
            version = escape(str(source.get("current_source_version") or "Not recorded"))
            observed = display_time(source.get("current_observed_at"))
            reason = escape(str(source.get("reason") or ""))
            rows.append(
                "<tr>"
                f'<td data-label="Source" class="source-name"><strong>{source_label}</strong></td>'
                f'<td data-label="Status"><span class="badge {source_class}">{source_status}</span></td>'
                f'<td data-label="Version">{version}</td>'
                f'<td data-label="Observed" class="source-time">{observed}</td>'
                f'<td data-label="Reason" class="source-reason">{reason}</td>'
                "</tr>"
            )

    rows_html = "".join(rows) or (
        '<tr><td colspan="5">No source rows were returned.</td></tr>'
    )

    usable_text = "Yes" if decision_usable else "No"
    gate_text = "Pass" if source_gate else "Review required"
    usable_class = "good" if decision_usable else "review"
    gate_class = "good" if source_gate else "review"
    source_count = sum(isinstance(source, dict) for source in sources) if isinstance(sources, list) else 0

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paid sponsor monitoring report — England Works Watch</title>
<style>
:root{{--ink:#172b43;--muted:#586a80;--blue:#155eef;--green:#14532d;--line:#dce4ef;--panel:#f5f8fc;--blue-soft:#edf3ff}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);line-height:1.65;background:#f3f6fb}}
main{{max-width:1140px;margin:0 auto;padding:48px 28px 64px}}
.eyebrow{{color:var(--blue);font-weight:750;font-size:.78rem;letter-spacing:.09em;text-transform:uppercase}}
h1{{margin:12px 0 18px;font-size:clamp(1.9rem,4vw,2.8rem);letter-spacing:-.035em;line-height:1.15}}
h2{{margin:0 0 16px;font-size:1.3rem;letter-spacing:-.02em}}
p{{margin:12px 0}}
.lead,.muted{{color:var(--muted)}}
.lead{{max-width:760px;font-size:1.05rem}}
.card{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:30px;margin-top:24px;box-shadow:0 8px 30px #172b4308}}
.report-header{{border-top:4px solid var(--blue)}}
.summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:26px 0}}
.metric{{border:1px solid var(--line);border-radius:12px;padding:18px 20px;background:var(--panel);min-width:0}}
.metric span{{display:block;color:var(--muted);font-size:.8rem;font-weight:600;margin-bottom:8px}}
.metric strong{{display:block;font-size:1.05rem;overflow-wrap:anywhere}}
.good{{color:var(--green)}}
.review{{color:#92400e}}
.badge{{display:inline-block;font-size:.72rem;font-weight:750;padding:5px 9px;border-radius:6px;letter-spacing:.02em;white-space:nowrap;overflow-wrap:normal}}
.badge.good{{background:#ecfdf3;border:1px solid #b5e6c4}}
.badge.review{{background:#fffbeb;border:1px solid #f3d798}}
.order-reference{{display:grid;gap:8px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 20px;margin-top:22px}}
.order-reference span{{font-size:.8rem;font-weight:650;color:var(--muted)}}
code{{font-size:.92rem;overflow-wrap:anywhere}}
.actions{{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin-top:24px}}
.button{{display:inline-block;padding:12px 20px;background:var(--blue);color:#fff;border-radius:8px;text-decoration:none;font-weight:700}}
.button:hover{{background:#124ac0}}
.button.secondary{{background:#fff;color:var(--blue);border:1px solid #b6c9f2}}
a{{color:var(--blue);text-underline-offset:3px}}
:focus-visible{{outline:3px solid #94b9ff;outline-offset:3px}}
.checked-at{{color:var(--muted);font-size:.88rem;margin:0 0 18px}}
.explanation{{padding:16px 20px;background:var(--panel);border-radius:10px;font-size:.9rem;color:var(--muted);margin-bottom:22px}}
table{{width:100%;border-collapse:collapse;font-size:.85rem;line-height:1.6}}
th,td{{text-align:left;vertical-align:top;padding:16px 12px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}}
th{{background:var(--panel);font-size:.78rem;color:var(--muted);font-weight:700;white-space:nowrap}}
.source-name{{width:28%}}.source-time{{min-width:125px;font-size:.8rem;color:var(--muted)}}.source-reason{{width:24%;color:var(--muted)}}
td[data-label="Status"]{{min-width:108px}}td[data-label="Version"]{{min-width:66px;white-space:nowrap}}
tbody tr:last-child td{{border-bottom:0}}
.notice{{border-left:4px solid var(--blue);background:var(--blue-soft)}}
.notice strong{{display:block;margin-bottom:6px}}
.recovery-card{{scroll-margin-top:24px}}.recovery-card .eyebrow{{margin:0 0 12px}}
details.card{{padding:22px 30px}}summary{{font-weight:700;cursor:pointer}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--panel);padding:20px;border-radius:10px;font-size:.78rem;margin:20px 0 0}}
.footer{{margin-top:28px;font-size:.85rem;color:var(--muted)}}.footer nav{{display:flex;flex-wrap:wrap;gap:20px;margin-top:20px;padding-top:20px;border-top:1px solid var(--line)}}
@media(max-width:760px){{
  main{{padding:24px 16px 40px}}.card{{padding:22px 18px}}.summary{{grid-template-columns:1fr 1fr;gap:12px}}.metric{{padding:14px}}
  table,tbody{{display:block}}thead{{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}}
  tbody tr{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px 0;border-top:1px solid var(--line)}}
  td{{display:block;padding:0;border:0;min-width:0}}td::before{{content:attr(data-label);display:block;font-size:.72rem;color:var(--muted);font-weight:700;margin-bottom:6px}}
  .source-name,.source-reason,td[colspan]{{grid-column:1/-1;width:auto}}.source-time{{min-width:0}}details.card{{padding:20px 18px}}
}}
@media(max-width:420px){{.summary{{grid-template-columns:1fr}}.actions{{align-items:stretch}}.button{{width:100%;text-align:center}}}}
@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}}}
@media print{{body{{background:#fff}}main{{padding:0}}.card{{box-shadow:none;break-inside:avoid}}.actions,.recovery-card,.footer nav{{display:none}}}}
</style>
</head>
<body>
<main>
  <div class="eyebrow">England Works Watch</div>
  <h1>Paid sponsor monitoring report</h1>

  <p class="lead">
    Verified monitoring result for the selected official GOV.UK sponsor
    guidance sources.
  </p>

  <section class="card report-header" aria-label="Report summary">
    <div class="summary">
      <div class="metric"><span>Report status</span><strong class="{status_class}">{status}</strong></div>
      <div class="metric"><span>Decision usable</span><strong class="{usable_class}">{usable_text}</strong></div>
      <div class="metric"><span>Source gate</span><strong class="{gate_class}">{gate_text}</strong></div>
      <div class="metric"><span>Selected sources</span><strong>{source_count}</strong></div>
    </div>
    <div class="order-reference"><span>Order reference</span><code>{escape(entitlement_code)}</code></div>
    <div class="actions">
      <a class="button" href="{access_link}">Check these sources again</a>
      <a href="#report-access">Save access for later</a>
    </div>
  </section>

  <section class="card">
    <h2>Source monitoring results</h2>
    <p class="checked-at">Last report check: <strong>{checked_at}</strong></p>
    <p class="explanation">The comparison starts with a source snapshot saved before checkout. UNCHANGED means no detected change since that snapshot; it does not describe earlier updates. Open each official source to review its current guidance.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Status</th>
            <th>Version</th>
            <th>Observed</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </section>

  <section class="card notice">
    <strong>Next action</strong>
    {next_action or "Continue only with current verified evidence."}
  </section>

  <details class="card">
    <summary>Complete monitoring result · JSON</summary>
    <pre>{report_json}</pre>
  </details>

  <section class="card recovery-card" id="report-access" aria-labelledby="access-heading">
    <p class="eyebrow">Report access</p>
    <h2 id="access-heading">Keep access to this report</h2>
    <p class="muted">Save your order reference. Use it with your checkout email to recover access when you return.</p>
    <div class="order-reference"><span>Order reference</span><code>{escape(checkout_id)}</code></div>
    <div class="actions"><a class="button secondary" href="{recovery_link}">Recover access by verified email</a></div>
  </section>

  <footer class="footer">
    <p>{disclaimer}</p>
    <nav aria-label="Service information">
      <a href="/pricing">Pricing</a><a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a><a href="/support">Support</a>
    </nav>
  </footer>
</main>
</body>
</html>"""


def _recovery_bootstrap_response():
    # The recovery credentials arrive in the URL fragment, which browsers do
    # not send to the server. Always keep a browser-side path available when
    # an old report-session cookie fails verification.
    return Response(polish_page("""<!doctype html><html><meta charset=utf-8><meta name=referrer content=no-referrer><title>Recover sponsor report</title><main><h1>Opening your recovered report…</h1><p id=status>Verifying access</p></main><script>(()=>{const p=new URLSearchParams(location.hash.slice(1));history.replaceState(null,'',location.pathname);const checkout_id=p.get('checkout_id'),report_session=p.get('report_session');if(!checkout_id||!report_session){document.getElementById('status').textContent='Recovery link is missing or expired.';return;}fetch('/api/v1/report-access/redeem',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({checkout_id,report_session})}).then(r=>{if(!r.ok)throw Error();location.replace('/monitoring-report/checkout-success?checkout_id='+encodeURIComponent(checkout_id));}).catch(()=>{document.getElementById('status').textContent='Payment may still be processing, or this recovery link is invalid, expired, or already used.';});})();</script></html>"""), media_type="text/html", headers={"Cache-Control":"no-store", "Referrer-Policy":"no-referrer", "Content-Security-Policy":"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"})


@mcp.custom_route("/monitoring-report/checkout-success", methods=["GET"])
async def monitoring_report_success(request):
    checkout_id = getattr(request, "query_params", {}).get("checkout_id", "") or next((key.removeprefix("report_session_") for key in request.cookies if key.startswith("report_session_")), "")
    if not checkout_id:
        checkout_id = next((key.removeprefix("report_claim_") for key in request.cookies if key.startswith("report_claim_")), "")
    if not checkout_id:
        return _recovery_bootstrap_response()
    row = PENDING_MONITORING_CHECKOUTS.get_by_checkout_id(checkout_id)
    if row is None:
        if "text/html" in request.headers.get("accept", "").lower():
            return _recovery_bootstrap_response()
        return browser_report_response(request, {"status": "REPORT_UNAVAILABLE"}, status_code=403)
    report_session = request.cookies.get(f"report_session_{checkout_id}")
    if not report_session:
        claim = request.cookies.get(f"report_claim_{checkout_id}")
        if not claim:
            return browser_report_response(request, {"status": "REPORT_UNAVAILABLE"}, status_code=403)
        try:
            claimed = await COMMERCIAL_CLIENT.claim_report_access(checkout_id=checkout_id, report_claim_token=claim)
            report_session = str(claimed["report_session"])
        except CommercialPlatformError as exc:
            return browser_report_response(request, {"status": "PAYMENT_PENDING_OR_REPORT_UNAVAILABLE", "detail": str(exc)}, status_code=403)
    try:
        verified = await COMMERCIAL_CLIENT.verify_report_access(checkout_id=checkout_id, report_session=report_session)
    except CommercialPlatformError as exc:
        return browser_report_response(request, {"status": "REPORT_ACCESS_UNAVAILABLE", "detail": str(exc)}, status_code=503)
    if not verified:
        # The browser may carry an expired report-session cookie while opening
        # a fresh recovery URL. Give the browser shell a chance to redeem the
        # new fragment token and replace that stale cookie.
        if "text/html" in request.headers.get("accept", "").lower() and request.cookies.get(f"report_session_{checkout_id}"):
            return _recovery_bootstrap_response()
        return browser_report_response(request, {"status": "REPORT_ACCESS_UNAVAILABLE"}, status_code=403)
    # Verified entitlements remain the authority on every visit. The opaque
    # return link is extended only once, so repeat views cannot extend access.
    first_paid_view = PENDING_MONITORING_CHECKOUTS.activate_paid_access(row.return_token)
    report = changed_since(row.checkpoint)
    if first_paid_view:
        await _safe_commercial_event(
            "payment_succeeded",
            source_channel=row.source_channel,
            classification=row.classification,
            owner_test=row.owner_test,
        )
        await _safe_commercial_event(
            "entitlement_activated",
            source_channel=row.source_channel,
            classification=row.classification,
            owner_test=row.owner_test,
        )
    await _safe_commercial_event(
        "premium_fulfilled",
        source_channel=row.source_channel,
        classification=row.classification,
        owner_test=row.owner_test,
    )

    result = {
        "status": "READY",
        "entitlement_code": checkout_id,
        "report": report,
    }

    # Browsers receive a human-readable paid report.
    # Machine/API clients keep the existing JSON contract.
    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept:
        response = Response(
            _monitoring_paid_page(
                entitlement_code=checkout_id,
                report=report,
                checkout_id=checkout_id,
            ),
            media_type="text/html",
            headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"},
        )
        response.set_cookie(key=f"report_session_{checkout_id}", value=report_session, max_age=86400, httponly=True,
                            secure=COMMERCIAL_SETTINGS.success_url.startswith("https://"), samesite="lax",
                            path="/monitoring-report/checkout-success")
        response.delete_cookie(key=f"report_claim_{checkout_id}", path="/monitoring-report/checkout-success")
        return response

    return browser_report_response(request, result, headers={"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})


@mcp.custom_route("/monitoring-report/checkout-cancelled", methods=["GET"])
async def monitoring_report_cancelled(request):
    return browser_report_response(request, {"status": "CHECKOUT_CANCELLED", "next_action": "Return to /monitoring-report to start again."})


@mcp.custom_route("/api/v1/report-access/redeem", methods=["POST"])
async def redeem_recovered_report(request):
    try:
        body = await request.json()
        checkout_id = str(body.get("checkout_id") or "")
        report_session = str(body.get("report_session") or "")
    except Exception:
        return JSONResponse({"status":"invalid_request"}, status_code=422)
    row = PENDING_MONITORING_CHECKOUTS.get_by_checkout_id(checkout_id)
    try:
        verified = bool(row is not None and await COMMERCIAL_CLIENT.verify_report_access(checkout_id=checkout_id, report_session=report_session))
    except Exception:
        verified = False
    if not verified:
        return JSONResponse({"status":"report_access_unavailable"}, status_code=403)
    response = Response(status_code=204, headers={"Cache-Control":"no-store", "Referrer-Policy":"no-referrer"})
    response.set_cookie(key=f"report_session_{checkout_id}", value=report_session, max_age=86400, httponly=True,
                        secure=COMMERCIAL_SETTINGS.success_url.startswith("https://"), samesite="lax",
                        path="/monitoring-report/checkout-success")
    return response


@mcp.custom_route("/api/v1/report-access/recovery", methods=["POST"])
async def start_report_recovery(request):
    try:
        body = await request.json()
        checkout_id = str(body.get("checkout_id") or "")
        contact_email = str(body.get("contact_email") or "").strip()
    except Exception:
        return JSONResponse({"status":"invalid_request"}, status_code=422)
    if not 32 <= len(checkout_id) <= 64 or not 5 <= len(contact_email) <= 254 or contact_email.count("@") != 1 or any(ch.isspace() for ch in contact_email):
        return JSONResponse({"status":"invalid_request"}, status_code=422, headers={"Cache-Control":"no-store"})
    try:
        available = await COMMERCIAL_CLIENT.start_report_recovery(checkout_id=checkout_id, contact_email=contact_email)
    except Exception:
        available = False
    if not available:
        return JSONResponse({"status":"Recovery is temporarily unavailable. Try again shortly."}, status_code=503, headers={"Cache-Control":"no-store"})
    return JSONResponse({"status":"If a paid report matches those details, a recovery link will be sent."}, headers={"Cache-Control":"no-store"})


@mcp.custom_route("/monitoring-report/recover", methods=["GET"])
async def monitoring_report_recover(request):
    from .report_recovery import RECOVERY_HEADERS, render_report_recovery

    checkout_id = request.query_params.get("checkout_id", "")
    return Response(render_report_recovery(checkout_id), media_type="text/html", headers=RECOVERY_HEADERS)


@mcp.custom_route("/llms.txt", methods=["GET"])
async def llms(_request):
    return PlainTextResponse(
        f"England Works Watch — UK sponsor compliance/change intelligence\n"
        f"Commercial MCP: {PUBLIC_MCP_URL}\n"
        f"Public AI MCP: {PUBLIC_ORIGIN}/ai/mcp\n"
        "Scope: Skilled Worker sponsor duties only.\n"
        "Public AI/directory edition: one interactive single-event sponsor-change preflight is available without x402, alongside source-status and supported-event discovery.\n"
        "Commercial MCP free discovery tools: england_works_watch_info, licensing_source_status, list_supported_change_events.\n"
        f"Primary paid API: batch_assess_changes {PRICE_BATCH}; assess 1-25 structured sponsor changes in one x402 call with per-event results and outcome counts.\n"
        f"Single-event commercial API: assess_change_impact {PRICE_ASSESS}; retained for metered programmatic integrations that need one-event execution.\n"
        f"30-day Sponsor Decision Evidence Check: £49 via Stripe at {PUBLIC_ORIGIN}/monitoring-report; creates a dated checkpoint across four core GOV.UK sponsor sources before a sponsor decision, then re-checks the same evidence for 30 days through a private reusable link.\n"
        "Use paid access for automation, repeated business use, batch processing, or continued evidence monitoring rather than to unlock the basic one-off answer.\n"
        "Example decision shape: status, decision_code, rationale, required_actions, deadline, missing_inputs, review_reasons, affected_rules and disclaimer.\n"
        f"x402 payment guidance: PaymentRequired -> sign buyer-side Base mainnet USDC ({NETWORK}) -> retry the same paid tool with payment metadata. If payment or settlement is not verified, the paid API decision is not executed.\n"
        "Decision arguments use a top-level payload object containing structured change facts.\n"
        "Official GOV.UK evidence is fingerprinted continuously; changed/stale evidence fails closed.\n"
        "Never treat REVIEW_REQUIRED or INSUFFICIENT_INPUT as clearance. Not legal advice.\n"
    )


@mcp.custom_route("/robots.txt", methods=["GET"])
async def robots(_request):
    return PlainTextResponse(f"User-agent: *\nAllow: /\nSitemap: {PUBLIC_ORIGIN}/sitemap.xml\n")


@mcp.custom_route("/sitemap.xml", methods=["GET"])
async def sitemap(_request):
    urls = [
        "/", "/pricing", "/privacy", "/terms", "/support", "/monitoring-report",
        "/llms.txt", "/openapi.json", "/.well-known/mcp.json", "/.well-known/agent-card.json", "/.well-known/x402",
    ]
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{PUBLIC_ORIGIN}{path}</loc></url>" for path in urls
    ) + "</urlset>"
    return Response(body, media_type="application/xml")


@mcp.custom_route("/.well-known/x402", methods=["GET"])
async def x402_info(_request):
    payment = _payment_info()
    result = {
        "x402Version": 2,
        "scheme": "exact",
        "network": NETWORK,
        "asset": "USDC",
        "payment_enforced": PAYMENT_ENFORCED,
        "tools": {
            "assess_change_impact": {
                "price": PRICE_ASSESS,
                "role": "metered programmatic single-event compatibility path",
            },
            "batch_assess_changes": {
                "price": PRICE_BATCH,
                "role": "primary paid API path for repeated work",
                "max_events": 25,
            },
        },
        "recommended_paid_paths": payment["recommended_paid_paths"],
        "public_ai_alternative": {
            "url": f"{PUBLIC_ORIGIN}/ai/mcp",
            "value": "One interactive single-event sponsor-change preflight is available without x402.",
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
            "description": "UK Skilled Worker sponsor-change preflight with a public interactive single-event path, paid batch automation, and a 30-day Sponsor Decision Evidence Check.",
            "url": PUBLIC_ORIGIN,
            "mcp": PUBLIC_MCP_URL,
            "public_ai_mcp": f"{PUBLIC_ORIGIN}/ai/mcp",
            "monitoring_report": f"{PUBLIC_ORIGIN}/monitoring-report",
            "capabilities": {
                "change_impact": SUPPORTED_EVENTS,
                "source_freshness": True,
                "batch": True,
                "monitoring": True,
                "x402": True,
            },
            "commercial_value": {
                "primary_paid_api": "batch_assess_changes for 1-25 sponsor changes",
                "continued_monitoring": "30-day Sponsor Decision Evidence Check for dated GOV.UK evidence before and between sponsor decisions",
                "single_event_api": "assess_change_impact for metered programmatic one-event execution",
            },
            "instructions": "Use the public AI edition for a one-off interactive sponsor-change preflight. Use the commercial batch API for multiple events or repeated automation. Use the £49 Sponsor Decision Evidence Check when a buyer needs a dated GOV.UK evidence checkpoint before a sponsor decision and a private link to re-check that evidence for 30 days. On commercial execution, read source status first and escalate REVIEW_REQUIRED or INSUFFICIENT_INPUT.",
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
            "$schema": "https://glama.ai/mcp/schemas/connector.json",
            "claim": "glama_claim_w9AF-xs40XYIYfk0LmecMd2kKI5eY-Lt",
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
                "/pricing": {"get": {"summary": "x402 prices and human monitoring/report offer"}},
                "/privacy": {"get": {"summary": "Privacy and bounded-data policy"}},
                "/terms": {"get": {"summary": "Current product terms and limits"}},
                "/support": {"get": {"summary": "Integration and support guidance"}},
                "/monitoring-report": {"get": {"summary": "Human sponsor-compliance monitoring/report entry"}},
                "/monitoring-report/checkout": {"post": {"summary": "Start shared-commercial monitoring/report checkout"}},
                "/monitoring-report/checkout-success": {"get": {"summary": "Verify entitlement and return monitoring report"}},
                "/monitoring-report/checkout-cancelled": {"get": {"summary": "Checkout cancellation return"}},
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
