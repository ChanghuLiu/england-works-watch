from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import os
import re
import sqlite3

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
    c.commit()
    return c


def _safe(v: Any, max_len: int = 80):
    if not isinstance(v, str) or not v.strip():
        return None
    return re.sub(r"[^A-Za-z0-9._:/+@-]", "_", v.strip())[:max_len]


def _owned_client_names() -> set[str]:
    extra = {
        item.strip()
        for item in os.getenv("EWW_OWNED_CLIENT_NAMES", "").split(",")
        if item.strip()
    }
    return DEFAULT_OWNED_CLIENT_NAMES | extra


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
):
    actor, client = classify_actor(meta)
    with _db() as c:
        c.execute(
            "INSERT INTO events(occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                tool,
                outcome,
                int(billable),
                payment_state,
                actor,
                client,
                latency_ms,
            ),
        )


def record_discovery(route: str) -> None:
    """Persist one public machine-discovery surface hit without request identity.

    Deliberately stores only the normalized route name. No IP, user-agent,
    query string, headers, or cookies are retained, so these events measure raw
    discovery activity but never claim a confirmed external customer.
    """
    normalized = _safe(route, 120) or "unknown"
    try:
        record(DISCOVERY_TOOL, normalized, billable=False)
    except sqlite3.Error:
        # Observability must never break a discovery response.
        pass


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(UTC)


def _load_rows(hours: int | None = None):
    try:
        with _db() as c:
            rows = c.execute(
                "SELECT occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms "
                "FROM events ORDER BY id ASC"
            ).fetchall()
    except sqlite3.Error:
        return []
    if hours is None:
        return rows
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    selected = []
    for row in rows:
        when = _parse_time(row[0])
        if when is not None and when >= cutoff:
            selected.append(row)
    return selected


def _window_summary(hours: int | None) -> dict[str, Any]:
    rows = _load_rows(hours)
    normalized = [
        {
            "occurred_at": row[0],
            "tool": row[1],
            "outcome": row[2],
            "billable": bool(row[3]),
            "payment_state": row[4] or "none",
            "actor": _effective_actor(row[5], row[6]),
            "client": _safe(row[6]),
            "latency_ms": row[7],
        }
        for row in rows
    ]
    discovery_rows = [row for row in normalized if row["tool"] == DISCOVERY_TOOL]
    free_rows = [row for row in normalized if row["tool"] in FREE_TOOLS and not row["billable"]]
    paid_rows = [row for row in normalized if row["billable"] and row["tool"] in BUSINESS_TOOLS]
    challenge_rows = [row for row in paid_rows if row["payment_state"] == "challenge"]
    executed_rows = [row for row in paid_rows if row["payment_state"] == "paid_executed"]
    payment_error_rows = [row for row in paid_rows if row["payment_state"] == "payment_error"]

    external_free = [row for row in free_rows if row["actor"] == "declared_external"]
    external_challenge = [row for row in challenge_rows if row["actor"] == "declared_external"]
    external_executed = [row for row in executed_rows if row["actor"] == "declared_external"]

    paid_by_external_client = Counter(
        row["client"] for row in external_executed if row["client"]
    )
    repeat_clients = {name: count for name, count in paid_by_external_client.items() if count >= 2}
    repeat_integrations = len(repeat_clients)
    repeat_executions = sum(count - 1 for count in repeat_clients.values())

    by_actor = Counter(row["actor"] for row in normalized)
    by_tool = Counter(row["tool"] for row in normalized)
    discovery_by_route = Counter(row["outcome"] for row in discovery_rows)
    paid_funnel = Counter(row["payment_state"] for row in paid_rows)
    paid_funnel_by_actor: dict[str, dict[str, int]] = {}
    for row in paid_rows:
        bucket = paid_funnel_by_actor.setdefault(row["actor"], {})
        state = row["payment_state"]
        bucket[state] = bucket.get(state, 0) + 1

    return {
        "hours": hours,
        "total_events": len(normalized),
        "by_tool": dict(by_tool),
        "by_actor_class": dict(by_actor),
        "discovery_by_route": dict(discovery_by_route),
        "paid_funnel": dict(paid_funnel),
        "paid_funnel_by_actor": paid_funnel_by_actor,
        "commercial_funnel": {
            "discovery": {
                "raw": len(discovery_rows),
                "confirmed_external": None,
                "measured": True,
                "note": "Privacy-minimal hits to machine capability/discovery routes. No IP/UA/query data is stored, so raw discovery is not a customer count.",
            },
            "free_business_call": {
                "raw": len(free_rows),
                "confirmed_external": len(external_free),
                "measured": True,
                "note": "Free MCP info/source/event calls; confirmed external requires a non-owned declared software identity.",
            },
            "paid_challenge": {
                "raw": len(challenge_rows),
                "confirmed_external": len(external_challenge),
                "measured": True,
                "note": "x402 challenges; owner CI and unattributed traffic are excluded from confirmed external.",
            },
            "paid_executed": {
                "raw": len(executed_rows),
                "confirmed_external": len(external_executed),
                "measured": True,
                "note": "Settled/verified paid business executions; owner validation is technical proof only.",
            },
            "repeat_paid": {
                "raw": repeat_integrations,
                "confirmed_external": repeat_integrations,
                "measured": True,
                "repeat_executions_beyond_first": repeat_executions,
                "note": "Count of non-owned declared software integrations with at least two successful paid executions in the window.",
            },
        },
        "payment_errors": len(payment_error_rows),
        "privacy": (
            "No employer/worker facts, raw MCP metadata, payment signatures, wallet addresses, private keys, seed phrases, discovery IPs, user-agents or query strings are stored. "
            "Only sanitized self-declared software identifiers are retained for paid/free attribution and repeat-use aggregation."
        ),
    }


def summary():
    all_time = _window_summary(None)
    return {
        **all_time,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "windows": {
            "24h": _window_summary(24),
            "7d": _window_summary(24 * 7),
            "all_time": all_time,
        },
        "classification_note": (
            "Exact owner client names are excluded. A sanitized declared client name that is not on the owner allow-list is classified as declared_external. "
            "Requests without a usable client identity remain unattributed and are never counted as confirmed customers. Discovery HTTP hits are raw-only by design."
        ),
    }
