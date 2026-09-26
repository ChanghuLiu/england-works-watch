from __future__ import annotations

import re
from typing import Any

from .analytics import record
from .attribution import is_automated_user_agent, normalize_source_bucket
from .http_x402 import ASSESS_PATH, BATCH_PATH


_PROTECTED = {
    ASSESS_PATH: "assess_change_impact",
    BATCH_PATH: "batch_assess_changes",
}
_PAYMENT_HEADER_NAMES = {
    b"payment-signature",
    b"x-payment",
    b"x-payment-signature",
    b"payment",
}
_OWNER_ACTOR_VALUES = {"owned", "owned_ci", "owner", "test", "smoke"}

_NAMED_MACHINE_SOURCES = (
    ("x402-list-monitor", "x402_list"),
    ("x402-observer", "x402_trust"),
    ("x402lens-indexer", "x402lens"),
    ("x402watch", "x402_watch"),
    ("x402-probe", "x402_probe"),
    ("agent402", "agent402"),
    ("402explorer", "402explorer"),
    ("mcpbeat", "mcpbeat"),
    ("golemreach", "golemreach"),
    ("proofbench", "proofbench"),
    ("sentinel", "sentineloracle"),
)


def _safe_token(value: str | None, max_length: int = 80) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    candidate = re.sub(r"[^A-Za-z0-9._:/+@-]", "_", candidate)[:max_length]
    return candidate or None


def _source_context(headers: dict[bytes, bytes]) -> str:
    explicit = normalize_source_bucket(
        headers.get(b"x-eww-source-context", b"").decode("utf-8", errors="ignore")
    )
    if explicit != "unknown":
        return explicit

    ua = headers.get(b"user-agent", b"").decode("utf-8", errors="ignore").strip().lower()
    for token, bucket in _NAMED_MACHINE_SOURCES:
        if token in ua:
            return normalize_source_bucket(bucket)
    if is_automated_user_agent(ua):
        return "unknown_machine"
    return "unknown"


def _bounded_meta(headers: dict[bytes, bytes]) -> dict[str, Any]:
    meta: dict[str, Any] = {"source_context": _source_context(headers)}

    actor = headers.get(b"x-mcp-commercial-actor", b"").decode("utf-8", errors="ignore").strip().lower()
    if actor in _OWNER_ACTOR_VALUES:
        meta["englandworkswatch/actor"] = "owned_ci"

    request_id = _safe_token(
        headers.get(b"x-commercial-request-id", b"").decode("utf-8", errors="ignore"),
        96,
    )
    if request_id:
        meta["commercial/request_id"] = request_id

    declared = _safe_token(
        headers.get(b"x-eww-client", b"").decode("utf-8", errors="ignore"),
        80,
    )
    if declared:
        meta["io.modelcontextprotocol/clientInfo"] = {"name": declared}

    return meta


class HttpX402TelemetryASGI:
    """Privacy-minimal telemetry for the paid HTTP x402 compatibility routes.

    The wrapper observes only protected route, response status, whether one of
    the standard payment-proof headers is present, and bounded attribution
    labels. It never stores request bodies, payment proofs/signatures, wallet
    addresses, IP addresses, cookies, or raw user-agent strings.
    """

    def __init__(self, app: Any):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") not in _PROTECTED
        ):
            await self.app(scope, receive, send)
            return

        path = str(scope["path"])
        tool = _PROTECTED[path]
        headers = {bytes(k).lower(): bytes(v) for k, v in scope.get("headers", [])}
        proof_present = any(name in headers for name in _PAYMENT_HEADER_NAMES)
        meta = _bounded_meta(headers)
        status_code: int | None = None

        async def observed_send(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 0))
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        except Exception:
            if proof_present:
                record(
                    tool,
                    "payment_error",
                    billable=True,
                    payment_state="payment_error",
                    event_type="payment_error",
                    meta=meta,
                )
            raise

        if status_code == 402:
            record(
                tool,
                "challenge",
                billable=True,
                payment_state="challenge",
                event_type="paid_challenge",
                meta=meta,
            )
        elif status_code is not None and 200 <= status_code < 300 and proof_present:
            # Record the canonical business-tool name here. The endpoint's
            # existing *_http measurement remains operational telemetry and is
            # intentionally outside BUSINESS_TOOLS, so this event is the one
            # that advances the commercial funnel.
            record(
                tool,
                "paid_executed",
                billable=True,
                payment_state="paid_executed",
                event_type="paid_executed",
                meta=meta,
            )
        elif proof_present:
            record(
                tool,
                "payment_error",
                billable=True,
                payment_state="payment_error",
                event_type="payment_error",
                meta=meta,
            )
