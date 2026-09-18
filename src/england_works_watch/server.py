from __future__ import annotations

import argparse
import os
import time
from typing import Any, Mapping
from urllib.parse import parse_qs

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from .analytics import record, summary
from .attribution import OWNER_TEST_MARKERS
from .commercial import CommercialPlatformClient, CommercialPlatformError, CommercialSettings, PendingMonitoringCheckoutStore, commercial_source_channel
from .monitoring import changed_since, make_checkpoint
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
SERVICE_VERSION = "0.1.1"
PUBLIC_ORIGIN = os.getenv("EWW_PUBLIC_ORIGIN", "https://england-works-watch-production.up.railway.app").rstrip("/")
PUBLIC_MCP_URL = f"{PUBLIC_ORIGIN}/mcp"
PRICE_ASSESS = os.getenv("EWW_X402_PRICE_ASSESS", "$0.02")
PRICE_BATCH = os.getenv("EWW_X402_PRICE_BATCH", "$0.05")
PAYMENT_ENFORCED = os.getenv("EWW_PAYMENT_ENFORCED", "0").strip().lower() in {"1", "true", "yes", "on"}
PAY_TO = os.getenv("EWW_X402_PAY_TO", "").strip()
NETWORK = os.getenv("EWW_X402_NETWORK", "eip155:8453").strip()
FACILITATOR = os.getenv("EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network").strip()
COMMERCIAL_SETTINGS = CommercialSettings.from_env()
COMMERCIAL_CLIENT = CommercialPlatformClient(COMMERCIAL_SETTINGS)
PENDING_MONITORING_CHECKOUTS = PendingMonitoringCheckoutStore(
    COMMERCIAL_SETTINGS.pending_ttl_seconds,
    path=os.getenv("EWW_PENDING_STORE_PATH", "").strip() or None,
)
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
            "Official-source-backed single Skilled Worker sponsor change-impact decision. Returns an evidence-linked rationale, required action/deadline fields, and explicit review or missing-input state. x402 Base mainnet USDC: sign buyer-side and retry this same tool with payment metadata.",
        ),
        _assess,
    )
    paid_batch = gate.build(
        PaidToolSpec(
            "batch_assess_changes",
            PRICE_BATCH,
            "Batch Skilled Worker sponsor change-impact decisions for up to 25 events, with evidence-linked per-event results and outcome counts. x402 Base mainnet USDC: sign buyer-side and retry this same tool with payment metadata.",
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
            "value_preview": _value_preview(),
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


@mcp.custom_route("/pricing", methods=["GET"])
async def pricing(_request):
    return PlainTextResponse(
        render_pricing_page(
            origin=PUBLIC_ORIGIN,
            prices={
                "assess_change_impact": f"{PRICE_ASSESS} USDC per x402 call",
                "batch_assess_changes": f"{PRICE_BATCH} USDC per x402 call",
                "human monitoring/report": "shared-commercial Test-mode offer; configured outside this product repo",
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
    return PlainTextResponse(monitoring_page(origin=PUBLIC_ORIGIN), media_type="text/html")


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
    return {key: items[-1] for key, items in values.items()}


def _monitoring_ids(payload: dict[str, Any]) -> list[str]:
    source_ids = payload.get("source_ids")
    if isinstance(source_ids, str):
        source_ids = [item.strip() for item in source_ids.split(",") if item.strip()]
    if not isinstance(source_ids, list) or not source_ids or len(source_ids) > 4 or any(not isinstance(item, str) or item not in SOURCE_BY_ID for item in source_ids):
        raise ValueError("source_ids must contain 1-4 known source IDs")
    return list(dict.fromkeys(source_ids))


def _monitoring_classification(request, payload: Mapping[str, Any]) -> tuple[str, bool]:
    """Read only an explicit operator marker; never infer ownership from facts."""
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
        row = PENDING_MONITORING_CHECKOUTS.create(
            checkpoint=checkpoint,
            source_channel=source_channel,
            classification=classification,
            owner_test=owner_test,
        )
        checkout = await COMMERCIAL_CLIENT.create_checkout(
            principal_ref=row.principal_ref,
            source_channel=row.source_channel,
            external_classification=row.classification,
            owner_test=row.owner_test,
            success_url=COMMERCIAL_SETTINGS.checkout_success_url(row.return_token),
            cancel_url=COMMERCIAL_SETTINGS.cancel_url,
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
            "return_token": row.return_token,
            "monitoring_scope": {
                "source_ids": source_ids,
                "stored": "opaque checkpoint only",
            },
        }

        # Browser form submission: continue directly to hosted Stripe Checkout.
        # JSON clients retain the existing machine-readable contract.
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" not in content_type:
            return RedirectResponse(checkout["checkout_url"], status_code=303)

        return JSONResponse(result)

    except ValueError as exc:
        return JSONResponse({"status": "INVALID_REQUEST", "detail": str(exc)}, status_code=400)
    except CommercialPlatformError as exc:
        return JSONResponse({"status": "COMMERCIAL_UNAVAILABLE", "detail": str(exc)}, status_code=503)



def _monitoring_paid_page(*, entitlement_code: str, report: dict[str, Any]) -> str:
    from html import escape

    status = escape(str(report.get("status") or "UNKNOWN"))
    checked_at = escape(str(report.get("checked_at") or ""))
    decision_usable = report.get("decision_usable") is True
    source_gate = report.get("source_gate") is True
    next_action = escape(str(report.get("next_action") or ""))
    disclaimer = escape(str(report.get("disclaimer") or ""))

    rows = []
    sources = report.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            source_id = escape(str(source.get("source_id") or ""))
            source_status = escape(str(source.get("status") or "UNKNOWN"))
            version = escape(str(source.get("current_source_version") or ""))
            observed = escape(str(source.get("current_observed_at") or ""))
            reason = escape(str(source.get("reason") or ""))
            rows.append(
                "<tr>"
                f"<td><strong>{source_id}</strong></td>"
                f"<td>{source_status}</td>"
                f"<td>{version}</td>"
                f"<td>{observed}</td>"
                f"<td>{reason}</td>"
                "</tr>"
            )

    rows_html = "".join(rows) or (
        '<tr><td colspan="5">No source rows were returned.</td></tr>'
    )

    usable_text = "Yes" if decision_usable else "No"
    gate_text = "Pass" if source_gate else "Review required"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paid sponsor monitoring report — England Works Watch</title>
<style>
:root {{
  --ink:#17202a;
  --muted:#5d6b78;
  --blue:#155eef;
  --green:#137a4b;
  --line:#dfe6ec;
  --panel:#f7f9fb;
  --blue-soft:#eef4ff;
}}
*{{box-sizing:border-box}}
body{{
  margin:0;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:var(--ink);
  line-height:1.55;
}}
main{{
  max-width:1080px;
  margin:0 auto;
  padding:54px 24px 72px;
}}
.eyebrow{{
  color:var(--blue);
  font-weight:750;
  font-size:.9rem;
  letter-spacing:.04em;
  text-transform:uppercase;
}}
h1{{
  margin:9px 0 18px;
  font-size:2.35rem;
  line-height:1.12;
}}
.lead{{color:var(--muted);max-width:800px}}
.summary{{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:12px;
  margin:28px 0;
}}
.metric{{
  border:1px solid var(--line);
  border-radius:12px;
  padding:16px 18px;
  background:#fff;
}}
.metric span{{
  display:block;
  color:var(--muted);
  font-size:.82rem;
  margin-bottom:4px;
}}
.metric strong{{font-size:1.05rem}}
.good{{color:var(--green)}}
.card{{
  border:1px solid var(--line);
  border-radius:14px;
  padding:24px;
  margin-top:22px;
  box-shadow:0 8px 28px rgba(23,32,42,.045);
}}
table{{
  width:100%;
  border-collapse:collapse;
  margin-top:14px;
  font-size:.92rem;
}}
th,td{{
  text-align:left;
  vertical-align:top;
  padding:11px 10px;
  border-bottom:1px solid var(--line);
}}
th{{background:var(--panel)}}
.notice{{
  margin-top:24px;
  background:var(--blue-soft);
  border-radius:10px;
  padding:17px 19px;
}}
.links{{
  margin-top:30px;
  padding-top:20px;
  border-top:1px solid var(--line);
}}
a{{color:var(--blue)}}
@media(max-width:760px){{
  .summary{{grid-template-columns:1fr 1fr}}
  .table-wrap{{overflow-x:auto}}
}}

.metric strong{{
  display:block;
  overflow-wrap:anywhere;
  word-break:break-word;
}}
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

  <section class="summary">
    <div class="metric">
      <span>Report status</span>
      <strong class="good">{status}</strong>
    </div>
    <div class="metric">
      <span>Entitlement</span>
      <strong>{escape(entitlement_code)}</strong>
    </div>
    <div class="metric">
      <span>Decision usable</span>
      <strong>{usable_text}</strong>
    </div>
    <div class="metric">
      <span>Source gate</span>
      <strong>{gate_text}</strong>
    </div>
  </section>

  <section class="card">
    <h2>Source monitoring results</h2>
    <p>Checked at: {checked_at}</p>
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

  <section class="notice">
    <strong>Next action</strong><br>
    {next_action or "Continue only with current verified evidence."}
  </section>

  <p>{disclaimer}</p>

  <p class="links">
    <a href="/monitoring-report">Run another monitoring report</a> ·
    <a href="/pricing">Pricing</a> ·
    <a href="/privacy">Privacy</a> ·
    <a href="/terms">Terms</a> ·
    <a href="/support">Support</a>
  </p>
</main>
</body>
</html>"""


@mcp.custom_route("/monitoring-report/checkout-success", methods=["GET"])
async def monitoring_report_success(request):
    token = request.query_params.get("return_token", "")
    row = PENDING_MONITORING_CHECKOUTS.get(token)
    if row is None:
        return JSONResponse({"status": "INVALID_RETURN_TOKEN"}, status_code=400)
    try:
        entitlement = await COMMERCIAL_CLIENT.verify_entitlement(principal_ref=row.principal_ref)
    except CommercialPlatformError as exc:
        return JSONResponse({"status": "ENTITLEMENT_UNAVAILABLE", "detail": str(exc)}, status_code=503)
    if entitlement.get("active") is not True or not isinstance(entitlement.get("token"), str) or not entitlement["token"]:
        return JSONResponse({"status": "ENTITLEMENT_REQUIRED", "detail": "A verified active shared-commercial entitlement is required."}, status_code=403)
    report = changed_since(row.checkpoint)
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
        "entitlement_code": entitlement.get("entitlement_code"),
        "report": report,
    }

    # Browsers receive a human-readable paid report.
    # Machine/API clients keep the existing JSON contract.
    accept = request.headers.get("accept", "").lower()
    if "text/html" in accept:
        return Response(
            _monitoring_paid_page(
                entitlement_code=str(entitlement.get("entitlement_code") or ""),
                report=report,
            ),
            media_type="text/html",
        )

    return JSONResponse(result)


@mcp.custom_route("/monitoring-report/checkout-cancelled", methods=["GET"])
async def monitoring_report_cancelled(request):
    token = request.query_params.get("return_token", "")
    return JSONResponse({"status": "CHECKOUT_CANCELLED", "return_token_present": bool(token), "next_action": "Return to /monitoring-report to start again."})


@mcp.custom_route("/llms.txt", methods=["GET"])
async def llms(_request):
    return PlainTextResponse(
        f"England Works Watch — UK sponsor compliance/change intelligence\n"
        f"MCP: {PUBLIC_MCP_URL}\n"
        "Scope: Skilled Worker sponsor duties only.\n"
        "Free MCP tools: england_works_watch_info, licensing_source_status, list_supported_change_events.\n"
        f"Paid: assess_change_impact {PRICE_ASSESS}; batch_assess_changes {PRICE_BATCH}.\n"
        "Use when an employer/HR/HRIS Agent needs deterministic evidence-backed sponsor change impact.\n"
        "Free vs paid: free tools provide scope, source status and supported-event vocabulary; paid tools return a deterministic decision with evidence-linked rationale, required action/deadline fields, and explicit review or missing-input state.\n"
        "Example paid result (synthetic shape only): unauthorised_absence, Skilled Worker, 11 consecutive working days -> a response containing status, decision_code, rationale, required_actions, deadline, missing_inputs, review_reasons, affected_rules and disclaimer.\n"
        f"Payment guidance: x402 PaymentRequired -> sign buyer-side Base mainnet USDC ({NETWORK}) -> retry the same paid tool with payment metadata. If payment or settlement is not verified, the paid decision is not executed.\n"
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
                "/pricing": {"get": {"summary": "x402 prices and human monitoring/report offer"}},
                "/privacy": {"get": {"summary": "Privacy and bounded-data policy"}},
                "/terms": {"get": {"summary": "Current product terms and limits"}},
                "/support": {"get": {"summary": "Integration and support guidance"}},
                "/monitoring-report": {"get": {"summary": "Human sponsor-compliance monitoring/report entry"}},
                "/monitoring-report/checkout": {"post": {"summary": "Start shared-commercial Test-mode monitoring/report checkout"}},
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
