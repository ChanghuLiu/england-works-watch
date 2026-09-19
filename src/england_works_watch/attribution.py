"""Shared V24 aggregate attribution contract for England Works Watch."""
from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any, Mapping
from urllib.parse import parse_qs
from uuid import uuid4

EVENT_SCHEMA_VERSION = "commercial-attribution-v1"
SOURCE_BUCKETS = frozenset({
    "linkedin", "organic", "directory",
    "official_registry", "glama", "docker", "tensorblock", "mcpso",
    "mcpservers_org", "mcpmux", "punkpeye_remote", "mcpindex", "direct", "unknown",
    "mcpbeat", "agent402", "402explorer", "wellknown", "mcpmetrics", "smithery",
    "mcp_directory", "safemcp", "unyly", "truespar", "agentshare",
    "sentineloracle", "proofbench", "mcpcheckup", "golemreach", "mcpscan", "agentstatus",
    "openai", "claude", "grok",
})
EXPLICIT_SOURCE_ALIASES = {
    "chatgpt": "openai",
    "chatgpt_app": "openai",
    "openai_chatgpt": "openai",
    "claude_connector": "claude",
    "claude_connectors": "claude",
    "grok_connector": "grok",
    "xai_grok": "grok",
    "linkedin.com": "linkedin",
    "linkedin_post": "linkedin",
    "linkedin_dm": "linkedin",
    "google": "organic",
    "bing": "organic",
    "search": "organic",
    "seo": "organic",
    "organic_search": "organic",
}
OWNER_TEST_MARKERS = frozenset({"portfolio_owner_probe_v21", "portfolio_ci_probe_v21"})
OWNER_TEST_ACTORS = frozenset({"owned", "owned_ci", "owner", "test", "smoke"})
OWNER_TEST_MODES = frozenset({"test", "staging", "acceptance", "owner_probe"})
PAYMENT_STATUSES = frozenset({"not_applicable", "challenged", "paid", "payment_error", "unknown"})

AUTOMATED_USER_AGENT_MARKERS = (
    "bot", "crawler", "spider", "indexer", "headless",
    "curl/", "wget/", "python-requests", "httpx/", "aiohttp/", "tinyfish",
)


def is_automated_user_agent(value: Any) -> bool:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return False
    if candidate in {"node", "node.js"}:
        return True
    return any(marker in candidate for marker in AUTOMATED_USER_AGENT_MARKERS)



class SourceContext(str):
    request_id: str | None
    declared_client: str | None
    declared_client_version: str | None

    def __new__(
        cls,
        value: str,
        request_id: str | None = None,
        declared_client: str | None = None,
        declared_client_version: str | None = None,
    ):
        obj = str.__new__(cls, value)
        obj.request_id = request_id
        obj.declared_client = declared_client
        obj.declared_client_version = declared_client_version
        return obj


def _safe_token(value: Any, max_length: int = 96) -> str | None:
    if not isinstance(value, str): return None
    candidate = value.strip()
    if not candidate: return None
    return re.sub(r"[^A-Za-z0-9._:/+@-]", "_", candidate)[:max_length] or None


def normalize_source_bucket(value: Any) -> str:
    if not isinstance(value, str): return "unknown"
    value = value.strip().lower()
    value = EXPLICIT_SOURCE_ALIASES.get(value, value)
    return value if value in SOURCE_BUCKETS else "unknown"


def source_bucket_from_query(query: Any) -> str:
    if not isinstance(query, str): return "unknown"
    parsed = parse_qs(query, keep_blank_values=True)
    for key in ("src", "source", "ref", "utm_source", "campaign_source"):
        values = parsed.get(key, [])
        if values:
            return normalize_source_bucket(values[0])
    return "unknown"


def request_id_from_meta(meta: Mapping[str, Any] | None, *, fallback: Any = None) -> str:
    meta = meta or {}
    for key in ("commercial/request_id", "request_id", "requestId", "x-request-id"):
        value = _safe_token(meta.get(key))
        if value: return value
    return _safe_token(fallback) or uuid4().hex


def _declared_client_from_meta(meta: Mapping[str, Any]) -> tuple[str | None, str | None]:
    client = meta.get("io.modelcontextprotocol/clientInfo")
    if not isinstance(client, Mapping): return None, None
    return _safe_token(client.get("name"), 80), _safe_token(client.get("version"), 32)


def source_context_from_meta(meta: Mapping[str, Any] | None) -> SourceContext:
    meta = meta or {}
    explicit_request_id = None
    for key in ("commercial/request_id", "request_id", "requestId", "x-request-id"):
        explicit_request_id = _safe_token(meta.get(key))
        if explicit_request_id: break
    client, client_version = _declared_client_from_meta(meta)
    source = "unknown"
    for key in ("source_context", "source", "ref", "utm_source", "campaign_source"):
        if key in meta:
            source = normalize_source_bucket(meta.get(key))
            break
    return SourceContext(source, explicit_request_id, client, client_version)


def payment_status_for_event(event_type: Any, *, outcome: Any = None) -> str:
    normalized_outcome = str(outcome or "").strip().upper()
    if normalized_outcome == "CHALLENGE": return "challenged"
    if normalized_outcome == "PAID_EXECUTED": return "paid"
    if normalized_outcome == "PAYMENT_ERROR": return "payment_error"
    normalized_type = str(event_type or "").strip().lower()
    if normalized_type == "paid_challenge": return "challenged"
    if normalized_type == "paid_executed": return "paid"
    if normalized_type in {"payment_error", "paid_error"}: return "payment_error"
    if normalized_type in {"discovery_observed", "mcp_initialize", "tools_list", "free_business_call", "tool_call", "business_tool_call"}: return "not_applicable"
    return "unknown"


def normalize_payment_status(value: Any, *, event_type: Any = None, outcome: Any = None) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in PAYMENT_STATUSES: return candidate
    return payment_status_for_event(event_type, outcome=outcome)


def owner_test_from_meta(meta: Mapping[str, Any] | None, *, deployment_mode: Any = "production") -> bool:
    meta = meta or {}
    marker = meta.get("owner_test_marker") or meta.get("englandworkswatch/owner_test_marker")
    actor = str(meta.get("englandworkswatch/actor") or meta.get("mcp-commercial-actor") or "").strip().lower()
    mode = deployment_mode.strip().lower() if isinstance(deployment_mode, str) else "production"
    return marker in OWNER_TEST_MARKERS or actor in OWNER_TEST_ACTORS or mode in OWNER_TEST_MODES


def external_classification(meta: Mapping[str, Any] | None, *, actor: str | None = None) -> tuple[str, bool]:
    owner_test = owner_test_from_meta(meta)
    if owner_test: return "owner_test", True
    effective_actor = actor or str((meta or {}).get("englandworkswatch/actor") or "").strip().lower()
    if effective_actor == "declared_external": return "confirmed_external", False
    return "unknown", False


def make_event(
    *, product_id: str, event_type: str, deployment_revision: str,
    source_context: Any = None, external: str = "unknown", owner_test: bool = False,
    timestamp: Any = None, request_id: Any = None, payment_status: Any = None,
    outcome: Any = None, tool_name: Any = None, declared_client: Any = None,
    declared_client_name: Any = None, declared_client_version: Any = None,
) -> dict[str, Any]:
    """Build the additive cross-product attribution envelope."""
    if owner_test: external = "owner_test"
    if external not in {"confirmed_external", "automated_external", "owner_test", "synthetic", "unknown"}: external = "unknown"
    timestamp = timestamp or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    carried_request_id = request_id or getattr(source_context, "request_id", None)
    client_candidate = declared_client if declared_client is not None else declared_client_name
    if client_candidate is None: client_candidate = getattr(source_context, "declared_client", None)
    client_version_candidate = declared_client_version
    if client_version_candidate is None: client_version_candidate = getattr(source_context, "declared_client_version", None)
    client = _safe_token(client_candidate, 80)
    event = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "product_id": _safe_token(product_id, 40) or "unknown",
        "event_type": _safe_token(event_type, 64) or "unknown",
        "source_bucket": normalize_source_bucket(source_context),
        "external_classification": external,
        "owner_test": bool(owner_test),
        "deployment_revision": str(deployment_revision or "unknown").strip() or "unknown",
        "timestamp": str(timestamp),
        "request_id": request_id_from_meta(None, fallback=carried_request_id),
        "declared_client": client,
        "declared_client_name": client,
        "declared_client_version": _safe_token(client_version_candidate, 32),
        "payment_status": normalize_payment_status(payment_status, event_type=event_type, outcome=outcome),
    }
    if tool_name is not None: event["tool_name"] = _safe_token(tool_name, 128)
    if outcome is not None: event["outcome"] = _safe_token(str(outcome).upper(), 64)
    return event
