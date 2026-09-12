"""Shared V21 aggregate attribution contract for England Works Watch."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import parse_qs

SOURCE_BUCKETS = frozenset({
    "official_registry", "glama", "docker", "tensorblock", "mcpso",
    "mcpservers_org", "mcpmux", "punkpeye_remote", "mcpindex", "direct", "unknown",
})
OWNER_TEST_MARKERS = frozenset({"portfolio_owner_probe_v21", "portfolio_ci_probe_v21"})
OWNER_TEST_ACTORS = frozenset({"owned", "owned_ci", "owner", "test", "smoke"})
OWNER_TEST_MODES = frozenset({"test", "staging", "acceptance", "owner_probe"})


def normalize_source_bucket(value: Any) -> str:
    if not isinstance(value, str):
        return "unknown"
    value = value.strip().lower()
    return value if value in SOURCE_BUCKETS else "unknown"


def source_bucket_from_query(query: Any) -> str:
    if not isinstance(query, str):
        return "unknown"
    values = parse_qs(query, keep_blank_values=True).get("src", [])
    return normalize_source_bucket(values[0] if values else None)


def source_context_from_meta(meta: Mapping[str, Any] | None) -> str:
    meta = meta or {}
    return normalize_source_bucket(meta.get("source_context"))


def owner_test_from_meta(meta: Mapping[str, Any] | None, *, deployment_mode: Any = "production") -> bool:
    meta = meta or {}
    marker = meta.get("owner_test_marker") or meta.get("englandworkswatch/owner_test_marker")
    actor = str(meta.get("englandworkswatch/actor") or "").strip().lower()
    mode = deployment_mode.strip().lower() if isinstance(deployment_mode, str) else "production"
    return marker in OWNER_TEST_MARKERS or actor in OWNER_TEST_ACTORS or mode in OWNER_TEST_MODES


def external_classification(meta: Mapping[str, Any] | None, *, actor: str | None = None) -> tuple[str, bool]:
    owner_test = owner_test_from_meta(meta)
    if owner_test:
        return "owner_test", True
    effective_actor = actor or str((meta or {}).get("englandworkswatch/actor") or "").strip().lower()
    if effective_actor == "declared_external":
        return "confirmed_external", False
    return "unknown", False


def make_event(*, product_id: str, event_type: str, deployment_revision: str,
               source_context: Any = None, external: str = "unknown",
               owner_test: bool = False, timestamp: Any = None) -> dict[str, Any]:
    if owner_test:
        external = "owner_test"
    if external not in {"confirmed_external", "owner_test", "unknown"}:
        external = "unknown"
    if timestamp is None:
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "product_id": product_id,
        "event_type": event_type,
        "source_bucket": normalize_source_bucket(source_context),
        "external_classification": external,
        "owner_test": bool(owner_test),
        "deployment_revision": str(deployment_revision or "unknown").strip() or "unknown",
        "timestamp": str(timestamp),
    }
