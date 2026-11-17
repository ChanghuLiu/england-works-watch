from __future__ import annotations

from contextlib import closing
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import os
import re
import sqlite3

from .attribution import (
    external_classification,
    normalize_payment_status,
    normalize_source_bucket,
    request_id_from_meta,
    source_bucket_from_query,
    source_context_from_meta,
)

UTC = timezone.utc
BUSINESS_TOOLS = {"assess_change_impact", "batch_assess_changes"}
FREE_TOOLS = {"england_works_watch_info", "licensing_source_status", "list_supported_change_events"}
DISCOVERY_TOOL = "__machine_discovery__"
DEFAULT_OWNED_CLIENT_NAMES = {
    "github-public-runner",
    "github-smoke",
    "local-owner-paid-smoke",
    "github-production-smoke",
    "england-works-watch-owned-smoke",
}


def runtime_dir() -> Path:
    p = Path(os.getenv("EWW_RUNTIME_DIR", "/data" if Path("/data").exists() else "runtime"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db():
    c = sqlite3.connect(runtime_dir() / "analytics.sqlite")
    c.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "occurred_at TEXT NOT NULL,"
        "tool TEXT NOT NULL,"
        "outcome TEXT NOT NULL,"
        "billable INTEGER NOT NULL,"
        "payment_state TEXT,"
        "actor_class TEXT NOT NULL,"
        "declared_client TEXT,"
        "latency_ms REAL"
        ")"
    )
    existing = {row[1] for row in c.execute("PRAGMA table_info(events)")}
    for column, definition in (
        ("event_type", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("source_bucket", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("external_classification", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("owner_test", "INTEGER NOT NULL DEFAULT 0"),
        ("deployment_revision", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("request_id", "TEXT"),
        ("payment_status", "TEXT NOT NULL DEFAULT 'unknown'"),
    ):
        if column not in existing:
            c.execute(f"ALTER TABLE events ADD COLUMN {column} {definition}")
    c.commit()
    return c


def _safe(v: Any, max_len: int = 80):
    if not isinstance(v, str) or not v.strip():
        return None
    return re.sub(r"[^A-Za-z0-9._:/+@-]", "_", v.strip())[:max_len]


def _owned_client_names() -> set[str]:
    extra = {item.strip() for item in os.getenv("EWW_OWNED_CLIENT_NAMES", "").split(",") if item.strip()}
    return DEFAULT_OWNED_CLIENT_NAMES | extra


KNOWN_CLIENT_SOURCE_MARKERS = (
    ("chatgpt", "openai"),
    ("openai", "openai"),
    ("claude", "claude"),
    ("anthropic", "claude"),
    ("grok", "grok"),
    ("glama", "glama"),
    ("smithery", "smithery"),
    ("mcpbeat", "mcpbeat"),
    ("agent402", "agent402"),
    ("402explorer", "402explorer"),
    ("golemreach", "golemreach"),
    ("mcpindex", "mcpindex"),
    ("mcpservers", "mcpservers_org"),
    ("docker", "docker"),
)


def _effective_source_bucket(source: Any, client: Any) -> str:
    """Fill an unknown source only from strongly recognizable software client labels."""
    explicit = normalize_source_bucket(source)
    if explicit != "unknown":
        return explicit
    candidate = str(_safe(client) or "").lower()
    for marker, bucket in KNOWN_CLIENT_SOURCE_MARKERS:
        if marker in candidate:
            return bucket
    return "unknown"


def _declared_software_family(client: Any) -> str:
    """Return a bounded software family without exposing arbitrary client labels."""
    candidate = str(_safe(client) or "").lower()
    for marker, bucket in KNOWN_CLIENT_SOURCE_MARKERS:
        if marker in candidate:
            return bucket
    return "other_declared_software"


def _effective_actor(actor: str | None, client: str | None) -> str:
    actor = str(actor or "").strip().lower()
    client = _safe(client)
    if actor == "owned_ci":
        return "owned_ci"
    if client:
        return "owned_ci" if client in _owned_client_names() else "declared_external"
    if actor == "declared_external":
        return "declared_external"
    return "unattributed"


def classify_actor(meta: dict[str, Any] | None):
    meta = meta or {}
    source = str(meta.get("englandworkswatch/actor", "")).strip().lower()
    ci = meta.get("io.modelcontextprotocol/clientInfo")
    name = _safe(ci.get("name") if isinstance(ci, dict) else None)
    if source == "owned_ci":
        return "owned_ci", name
    if source == "declared_external":
        return "declared_external", name
    return _effective_actor(None, name), name


def record(
    tool: str,
    outcome: str,
    *,
    billable: bool,
    payment_state: str | None = None,
    meta: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    event_type: str | None = None,
    source_context: Any = None,
    owner_test_marker: Any = None,
):
    meta = dict(meta or {})
    if source_context is not None:
        meta["source_context"] = source_context
    if owner_test_marker is not None:
        meta["owner_test_marker"] = owner_test_marker
    actor, client = classify_actor(meta)
    classification, owner_test = external_classification(meta, actor=actor)
    if event_type is None:
        event_type = "free_business_call" if not billable else {
            "challenge": "paid_challenge",
            "paid_executed": "paid_executed",
            "payment_error": "payment_error",
        }.get(payment_state or "", "paid_executed")
    revision = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("EWW_DEPLOY_REV") or "unknown").strip() or "unknown"
    correlation_id = request_id_from_meta(meta)
    payment_status = normalize_payment_status(
        None,
        event_type=event_type,
        outcome={
            "challenge": "CHALLENGE",
            "paid_executed": "PAID_EXECUTED",
            "payment_error": "PAYMENT_ERROR",
        }.get(payment_state or "", None),
    )
    with _db() as c:
        c.execute(
            """INSERT INTO events(
            occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms,
            event_type,source_bucket,external_classification,owner_test,deployment_revision,request_id,payment_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                tool,
                outcome,
                int(billable),
                payment_state,
                actor,
                client,
                latency_ms,
                event_type,
                source_context_from_meta(meta),
                classification,
                int(owner_test),
                revision,
                correlation_id,
                payment_status,
            ),
        )


def record_discovery(route: str, *, query: str | None = None) -> None:
    """Persist one privacy-minimal public machine-discovery observation."""
    normalized = _safe(route, 120) or "unknown"
    try:
        record(
            DISCOVERY_TOOL,
            normalized,
            billable=False,
            event_type="discovery_observed",
            source_context=source_bucket_from_query(query),
        )
    except sqlite3.Error:
        pass


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC)


def _load_rows(hours: int | None = None):
    """Stream events so summary memory does not grow with the full event history."""
    cutoff = None if hours is None else datetime.now(UTC) - timedelta(hours=hours)
    try:
        with closing(_db()) as connection:
            rows = connection.execute(
                """SELECT occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms,
                event_type,source_bucket,external_classification,owner_test,deployment_revision,request_id,payment_status
                FROM events ORDER BY id ASC"""
            )
            for row in rows:
                if cutoff is not None:
                    when = _parse_time(row[0])
                    if when is None or when < cutoff:
                        continue
                yield row
    except sqlite3.Error:
        return


def _window_summary(hours: int | None) -> dict[str, Any]:
    total_events = discovery_count = free_count = challenge_count = executed_count = payment_error_count = 0
    external_free_count = external_challenge_count = external_executed_count = 0
    by_actor, by_tool, by_payment_status, discovery_by_route, paid_funnel = (Counter() for _ in range(5))
    external_free_by_tool, external_challenge_by_tool, external_executed_by_tool = (Counter() for _ in range(3))
    external_free_by_source, external_challenge_by_source, external_executed_by_source = (Counter() for _ in range(3))
    external_free_by_software_family, external_challenge_by_software_family, external_executed_by_software_family = (Counter() for _ in range(3))
    external_free_clients, external_challenge_clients, external_executed_clients = set(), set(), set()
    paid_by_external_client = Counter()
    paid_funnel_by_actor: dict[str, dict[str, int]] = {}
    source_attribution: dict[str, dict[str, int]] = {}

    for row in _load_rows(hours):
        tool, outcome, billable = row[1], row[2], bool(row[3])
        payment_state = row[4] or "none"
        actor, client = _effective_actor(row[5], row[6]), _safe(row[6])
        event_type, source_bucket = row[8] or "unknown", _effective_source_bucket(row[9], row[6])
        total_events += 1
        by_actor[actor] += 1
        by_tool[tool] += 1
        by_payment_status[row[14] or "unknown"] += 1
        is_discovery = tool == DISCOVERY_TOOL
        is_free = tool in FREE_TOOLS and not billable
        is_paid = billable and tool in BUSINESS_TOOLS
        if is_discovery:
            discovery_count += 1
            discovery_by_route[outcome] += 1
        if is_free:
            free_count += 1
            if actor == "declared_external":
                external_free_count += 1
                external_free_by_tool[tool] += 1
                external_free_by_source[source_bucket] += 1
                external_free_by_software_family[_declared_software_family(client)] += 1
                if client:
                    external_free_clients.add(client)
        if is_paid:
            paid_funnel[payment_state] += 1
            bucket = paid_funnel_by_actor.setdefault(actor, {})
            bucket[payment_state] = bucket.get(payment_state, 0) + 1
            if payment_state == "challenge":
                challenge_count += 1
                if actor == "declared_external":
                    external_challenge_count += 1
                    external_challenge_by_tool[tool] += 1
                    external_challenge_by_source[source_bucket] += 1
                    external_challenge_by_software_family[_declared_software_family(client)] += 1
                    if client:
                        external_challenge_clients.add(client)
            elif payment_state == "paid_executed":
                executed_count += 1
                if actor == "declared_external":
                    external_executed_count += 1
                    external_executed_by_tool[tool] += 1
                    external_executed_by_source[source_bucket] += 1
                    external_executed_by_software_family[_declared_software_family(client)] += 1
                    if client:
                        external_executed_clients.add(client)
                        paid_by_external_client[client] += 1
            elif payment_state == "payment_error":
                payment_error_count += 1
        # Exactly the same three disjoint commercial populations as before.
        if is_discovery or is_free or is_paid:
            bucket = source_attribution.setdefault(source_bucket, {})
            bucket[event_type] = bucket.get(event_type, 0) + 1

    repeat_clients = {name: count for name, count in paid_by_external_client.items() if count >= 2}
    repeat_integrations = len(repeat_clients)
    repeat_executions = sum(count - 1 for count in repeat_clients.values())

    return {
        "hours": hours,
        "total_events": total_events,
        "by_tool": dict(by_tool),
        "by_actor_class": dict(by_actor),
        "by_payment_status": dict(by_payment_status),
        "discovery_by_route": dict(discovery_by_route),
        "paid_funnel": dict(paid_funnel),
        "paid_funnel_by_actor": paid_funnel_by_actor,
        "confirmed_external_by_tool": {
            "free_business_call": dict(external_free_by_tool),
            "paid_challenge": dict(external_challenge_by_tool),
            "paid_executed": dict(external_executed_by_tool),
        },
        "confirmed_external_by_source": {
            "free_business_call": dict(external_free_by_source),
            "paid_challenge": dict(external_challenge_by_source),
            "paid_executed": dict(external_executed_by_source),
        },
        "confirmed_external_by_software_family": {
            "free_business_call": dict(external_free_by_software_family),
            "paid_challenge": dict(external_challenge_by_software_family),
            "paid_executed": dict(external_executed_by_software_family),
        },
        "software_family_note": (
            "Only allow-listed software families are exposed. Arbitrary self-declared client labels "
            "are collapsed to other_declared_software and are never returned verbatim."
        ),
        "confirmed_external_client_cohorts": {
            "free_business_call_unique_clients": len(external_free_clients),
            "paid_challenge_unique_clients": len(external_challenge_clients),
            "paid_executed_unique_clients": len(external_executed_clients),
            "free_to_paid_challenge_overlap_clients": len(external_free_clients & external_challenge_clients),
            "paid_challenge_to_paid_executed_overlap_clients": len(external_challenge_clients & external_executed_clients),
            "free_to_paid_executed_overlap_clients": len(external_free_clients & external_executed_clients),
        },
        "client_cohort_note": (
            "Counts and cross-stage overlaps only. No client labels, hashes, IDs, IPs, user-agents, "
            "wallets, request payloads or payment signatures are exposed."
        ),
        "source_attribution": source_attribution,
        "source_attribution_scope": "commercial_funnel_rows_only",
        "commercial_funnel": {
            "discovery": {
                "raw": discovery_count,
                "confirmed_external": None,
                "measured": True,
                "note": "Privacy-minimal machine discovery observations; raw discovery is not a customer count.",
            },
            "free_business_call": {
                "raw": free_count,
                "confirmed_external": external_free_count,
                "measured": True,
                "note": "Confirmed external requires a non-owned declared software identity.",
            },
            "paid_challenge": {
                "raw": challenge_count,
                "confirmed_external": external_challenge_count,
                "measured": True,
                "note": "x402 challenges; owner CI and unattributed traffic are excluded from confirmed external.",
            },
            "paid_executed": {
                "raw": executed_count,
                "confirmed_external": external_executed_count,
                "measured": True,
                "note": "Settled/verified paid business executions; owner validation is technical proof only.",
            },
            "repeat_paid": {
                "raw": repeat_integrations,
                "confirmed_external": repeat_integrations,
                "measured": True,
                "repeat_executions_beyond_first": repeat_executions,
                "note": "Non-owned declared software integrations with at least two successful paid executions.",
            },
        },
        "payment_errors": payment_error_count,
        "privacy": (
            "No employer/worker facts, raw MCP metadata, payment signatures, wallet addresses, private keys, seed phrases, discovery IPs, user-agents or raw query strings are stored. "
            "Only bounded source/request correlation and sanitized self-declared software identifiers are retained."
        ),
        "correlation_note": "Request IDs correlate stages only when explicitly propagated by the client/path; generated IDs are event-local and are not user identity.",
    }


def _confirmed_external_client_sets(hours: int | None) -> dict[str, set[str]]:
    free: set[str] = set()
    challenge: set[str] = set()
    executed: set[str] = set()
    for row in _load_rows(hours):
        actor = _effective_actor(row[5], row[6])
        client = _safe(row[6])
        if actor != "declared_external" or not client:
            continue
        tool = row[1]
        billable = bool(row[3])
        payment_state = row[4] or "none"
        if tool in FREE_TOOLS and not billable:
            free.add(client)
        if tool in BUSINESS_TOOLS and billable and payment_state == "challenge":
            challenge.add(client)
        if tool in BUSINESS_TOOLS and billable and payment_state == "paid_executed":
            executed.add(client)
    return {"free": free, "challenge": challenge, "executed": executed}


def summary():
    all_time = _window_summary(None)
    clients_all = _confirmed_external_client_sets(None)
    clients_7d = _confirmed_external_client_sets(24 * 7)
    clients_24h = _confirmed_external_client_sets(24)
    cross_window = {
        "24h_free_to_all_time_paid_challenge_overlap_clients": len(clients_24h["free"] & clients_all["challenge"]),
        "7d_free_to_all_time_paid_challenge_overlap_clients": len(clients_7d["free"] & clients_all["challenge"]),
        "24h_free_to_all_time_paid_executed_overlap_clients": len(clients_24h["free"] & clients_all["executed"]),
        "7d_free_to_all_time_paid_executed_overlap_clients": len(clients_7d["free"] & clients_all["executed"]),
    }
    return {
        **all_time,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "windows": {
            "24h": _window_summary(24),
            "7d": _window_summary(24 * 7),
            "all_time": all_time,
        },
        "cross_window_external_client_cohorts": cross_window,
        "cross_window_client_note": (
            "Cross-window overlap counts only. They show whether currently active confirmed-external "
            "software clients have ever reached a later payment stage, without exposing client identity."
        ),
        "classification_note": (
            "Exact owner client names are excluded. A sanitized declared client name that is not on the owner allow-list is classified as declared_external. "
            "Requests without a usable client identity remain unattributed and are never counted as confirmed customers. Discovery HTTP hits are raw-only by design."
        ),
    }
