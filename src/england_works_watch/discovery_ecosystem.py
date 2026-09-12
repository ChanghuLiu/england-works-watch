from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from .analytics import record_discovery
from .attribution import source_bucket_from_query

UTC = timezone.utc
EVENT_VERSION = 2
DISCOVERY_SURFACES = {
    "/": "root",
    "/robots.txt": "robots",
    "/sitemap.xml": "sitemap",
    "/llms.txt": "llms",
    "/openapi.json": "openapi",
    "/.well-known/x402": "x402",
    "/.well-known/mcp.json": "mcp_metadata",
    "/.well-known/mcp/server-card.json": "mcp_server_card",
    "/.well-known/agent-card.json": "agent_card",
    "/.well-known/agent.json": "agent_json",
    "/.well-known/glama.json": "glama",
    "/.well-known/ai-catalog.json": "ai_catalog",
    "/.well-known/api-catalog": "api_catalog",
    "/mcp": "mcp",
}
_SOURCE_RULES: tuple[tuple[str, str, str], ...] = (
    ("agent402", "agent402", "router"),
    ("402explorer", "402explorer", "router"),
    ("mcpbeat", "mcpbeat", "indexer"),
    ("agentindexbot", "agentindex", "indexer"),
    ("mcplookup.com", "mcplookup", "indexer"),
    ("agent-tools.cloud", "agent_tools_cloud", "indexer"),
    ("aive-mcp-endpointprobe", "aive", "indexer"),
    ("sentineloracle", "sentinel_oracle", "indexer"),
    ("mcp-stats-prober", "mcp_stats", "indexer"),
    ("proofbench", "proofbench", "indexer"),
    ("golemreachtrustbot", "golemreach", "indexer"),
    ("mcpscan", "mcpscan", "indexer"),
    ("rokmcp-collector", "rokmcp", "indexer"),
    ("wellknownbot", "wellknown", "indexer"),
    ("oai-searchbot", "openai_search", "search_engine"),
    ("gptbot", "openai_gptbot", "search_engine"),
    ("semrushbot", "semrush", "search_engine"),
    ("mcp-product-console-commercial-funnel", "owner_monitor", "owner_monitor"),
    ("mcp-selection-lab-railway-monitor", "owner_monitor", "owner_monitor"),
)
_MACHINE_TOKENS = ("python-httpx", "undici", "go-http-client", "curl/", "wget/")
_STRONG_SURFACES = {"llms", "openapi", "x402", "mcp_metadata", "mcp_server_card", "agent_card", "agent_json", "glama", "ai_catalog", "api_catalog"}
_OWNER_HEADER = b"x-mcp-commercial-actor"
_OWNER_VALUES = {"owned", "owned_ci", "owner", "test", "smoke"}


def _path() -> Path:
    root = Path(os.getenv("EWW_RUNTIME_DIR", "/data" if Path("/data").exists() else "runtime"))
    root.mkdir(parents=True, exist_ok=True)
    return root / "discovery_ecosystem.jsonl"


def current_revision() -> str:
    raw = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV") or "unknown").strip()
    return re.sub(r"[^A-Za-z0-9._-]", "_", raw)[:40] or "unknown"


def _safe(value: str | None) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "unknown_machine").strip().lower())[:40] or "unknown_machine"


def _headers(scope: dict[str, Any]) -> dict[bytes, bytes]:
    result: dict[bytes, bytes] = {}
    for item in scope.get("headers") or []:
        try:
            key, value = item
            result[key.lower()] = value
        except Exception:
            continue
    return result


def _owner(headers: dict[bytes, bytes]) -> bool:
    raw = headers.get(_OWNER_HEADER, b"")
    try:
        return raw.decode("latin1", errors="ignore").strip().lower() in _OWNER_VALUES
    except Exception:
        return False


def classify_source(user_agent: str, surface: str) -> tuple[str, str] | None:
    ua = str(user_agent or "").strip().lower()
    for token, family, category in _SOURCE_RULES:
        if token in ua:
            return family, category
    if any(token in ua for token in _MACHINE_TOKENS):
        return "unknown_machine", "unknown_machine"
    if surface in _STRONG_SURFACES:
        return "unknown_machine", "unknown_machine"
    return None


def record_ecosystem(surface: str, family: str, category: str) -> None:
    if family == "owner_monitor" or category == "owner_monitor":
        return
    row = {
        "event_version": EVENT_VERSION,
        "event_id": uuid4().hex,
        "occurred_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "surface": _safe(surface),
        "source_family": _safe(family),
        "source_category": _safe(category),
        "observed_revision": current_revision(),
    }
    try:
        with _path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        pass


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def summary(hours: int) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    rows: list[dict[str, Any]] = []
    try:
        lines = _path().read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        when = _parse(row.get("occurred_at")) if isinstance(row, dict) else None
        if isinstance(row, dict) and int(row.get("event_version") or 0) in {1, 2} and when is not None and when >= cutoff:
            rows.append(row)

    surfaces = Counter(str(row.get("surface") or "unknown") for row in rows)
    families = Counter(str(row.get("source_family") or "unknown_machine") for row in rows)
    categories = Counter(str(row.get("source_category") or "unknown_machine") for row in rows)
    revision = current_revision()
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        family = str(row.get("source_family") or "unknown_machine")
        occurred = str(row.get("occurred_at") or "")
        prior = latest.get(family)
        if prior is None or occurred > str(prior.get("last_seen_at") or ""):
            observed = str(row.get("observed_revision") or "unknown")
            latest[family] = {
                "last_seen_at": occurred,
                "observed_revision": observed,
                "current_revision_seen": observed != "unknown" and revision != "unknown" and observed == revision,
            }
    stale_families = sorted(
        family for family, row in latest.items()
        if revision != "unknown" and not bool(row.get("current_revision_seen"))
    )

    return {
        "machine_discovery_non_owner_hits": len(rows),
        "machine_discovery_confirmed_external": None,
        "distinct_source_families": len(families),
        "by_surface": dict(sorted(surfaces.items())),
        "by_source_family": dict(sorted(families.items())),
        "by_source_category": dict(sorted(categories.items())),
        "current_revision": revision,
        "index_freshness_by_source_family": dict(sorted(latest.items())),
        "source_families_not_seen_on_current_revision": stale_families,
        "revision_drift_detected": bool(stale_families),
        "freshness_semantics": "A family is current only after that bounded crawler/router family is observed against the current deployment revision. Legacy events without revision are unknown, not fresh.",
        "privacy": "bounded labels plus deployment revision only; no IP, raw user-agent, query, payload, headers, signature, wallet or address",
        "interpretation": "Machine discovery activity only; not a customer, buyer-intent, settlement, or revenue count.",
    }


def overlay_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    windows = usage.get("windows") if isinstance(usage, dict) else None
    if not isinstance(windows, dict):
        return payload
    for key, hours in (("24h", 24), ("7d", 168)):
        window = windows.get(key)
        if not isinstance(window, dict):
            continue
        discovery = summary(hours)
        window["discovery_observability"] = discovery
        window["discovery_by_route"] = discovery["by_surface"]
        funnel = window.get("commercial_funnel")
        if isinstance(funnel, dict):
            stage = funnel.get("discovery")
            if isinstance(stage, dict):
                stage["raw"] = discovery["machine_discovery_non_owner_hits"]
                stage["confirmed_external"] = None
                stage["measured"] = True
                stage["note"] = "Privacy-safe bounded machine discovery. Discovery is not a customer count."
    payload["discovery_observability_version"] = "2.0"
    return payload


class DiscoveryEcosystemASGI:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        path = str(scope.get("path") or "").split("?", 1)[0] if scope.get("type") == "http" else ""
        if scope.get("type") == "http" and path in DISCOVERY_SURFACES:
            surface = DISCOVERY_SURFACES[path]
            method = str(scope.get("method") or "GET").upper()
            headers = _headers(scope)
            try:
                ua = headers.get(b"user-agent", b"").decode("latin1", errors="ignore")
            except Exception:
                ua = ""
            classified = classify_source(ua, surface)
            query_bytes = scope.get("query_string", b"")
            query = query_bytes.decode("ascii", errors="ignore") if isinstance(query_bytes, bytes) else ""
            # A source parameter is accepted only as a bounded discovery bucket.
            # The raw query is never passed to storage.
            has_source_parameter = "src=" in query.lower()
            recorded_discovery = False
            if has_source_parameter and method == "GET" and path != "/mcp":
                record_discovery(path, query=query)
                recorded_discovery = True
            if classified and not _owner(headers) and classified[1] != "owner_monitor":
                if path != "/mcp" or method in {"GET", "HEAD"} or classified[0] != "unknown_machine":
                    if not recorded_discovery:
                        record_discovery(path, query=query)
                    record_ecosystem(surface, classified[0], classified[1])

        if scope.get("type") != "http" or path != "/metrics":
            await self.app(scope, receive, send)
            return

        start_message = None
        body_parts: list[bytes] = []

        async def capture(message):
            nonlocal start_message
            if message.get("type") == "http.response.start":
                start_message = message
                return
            if message.get("type") == "http.response.body":
                body_parts.append(message.get("body", b""))
                if message.get("more_body"):
                    return
                body = b"".join(body_parts)
                try:
                    payload = json.loads(body.decode("utf-8"))
                    if isinstance(payload, dict):
                        body = json.dumps(overlay_metrics(payload), separators=(",", ":"), sort_keys=True).encode("utf-8")
                except Exception:
                    pass
                start = dict(start_message or {"type": "http.response.start", "status": 200, "headers": []})
                headers_out = [(k, v) for k, v in start.get("headers", []) if k.lower() != b"content-length"]
                headers_out.append((b"content-length", str(len(body)).encode("ascii")))
                start["headers"] = headers_out
                await send(start)
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            await send(message)

        await self.app(scope, receive, capture)
