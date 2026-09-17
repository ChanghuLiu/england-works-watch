"""Monitoring primitives derived only from the official source lifecycle.

This module compares opaque source checkpoints. It deliberately accepts no
worker, employer, prompt, or case payload and never turns a source change into
a new regulatory conclusion. A changed or unavailable source is a review
signal; only the existing rule-pack source mapping is reported as potentially
affected.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .policy import RULES, SOURCE_BY_ID
from .source_runtime import load_state, production_source_status

MONITORING_STATES = ("UNCHANGED", "CHANGED", "REVIEW_REQUIRED")
_KNOWN_SOURCE_IDS = frozenset(SOURCE_BY_ID)

# This is a category index, not a decision engine. It is intentionally derived
# from the already-reviewed rule/event contract and is used only to tell a
# human which existing areas need review after source drift.
SOURCE_EVENT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "sponsor-part3": (
        "worker_start_delay", "unauthorised_absence", "work_location_change",
        "stop_sponsoring", "organisation_change", "tupe_transfer", "merger_takeover",
    ),
    "sponsor-part2": (
        "worker_start_delay", "unpaid_or_reduced_pay_absence", "role_change",
    ),
    "skilled-worker": ("salary_change",),
    "appendix-d": (),
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_ids(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return tuple(sorted(_KNOWN_SOURCE_IDS))
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return None
    values = tuple(dict.fromkeys(value))
    if not values or any(not isinstance(item, str) or item not in _KNOWN_SOURCE_IDS for item in values):
        return None
    return values


def _checkpoint_row(source_id: str, state: Mapping[str, Any]) -> dict[str, Any]:
    item = state["sources"].get(source_id) or {}
    return {
        "source_id": source_id,
        "source_version": item.get("source_version"),
        "semantic_sha256": item.get("last_semantic_sha256"),
        "observed_at": item.get("last_success_at"),
    }


def make_checkpoint(source_ids: Any = None) -> dict[str, Any]:
    """Return a bounded machine-readable checkpoint for later comparison."""
    ids = _source_ids(source_ids)
    if ids is None:
        raise ValueError("source_ids must contain only known source IDs")
    state = load_state()
    return {
        "schema_version": "c5-monitoring-v1",
        "created_at": _iso_now(),
        "sources": [_checkpoint_row(source_id, state) for source_id in ids],
    }


def _checkpoint_rows(checkpoint: Mapping[str, Any]) -> dict[str, Mapping[str, Any]] | None:
    rows = checkpoint.get("sources")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)) or not rows:
        return None
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        source_id = row.get("source_id")
        digest = row.get("semantic_sha256")
        version = row.get("source_version")
        if (
            not isinstance(source_id, str) or source_id not in _KNOWN_SOURCE_IDS
            or source_id in result or not isinstance(digest, str) or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest.lower())
            or not isinstance(version, str) or not version
        ):
            return None
        result[source_id] = row
    return result


def _categories(source_id: str) -> dict[str, Any]:
    rule_ids = tuple(rule["rule_id"] for rule in RULES["rules"] if rule["source_id"] == source_id)
    return {
        "source_id": source_id,
        "rule_ids": list(rule_ids),
        "event_types": list(SOURCE_EVENT_CATEGORIES.get(source_id, ())),
        "mapping_basis": "existing rule-pack source mapping; not a new decision",
    }


def changed_since(checkpoint: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Compare a checkpoint with current source lifecycle state.

    `CHANGED` means the current verified fingerprint/version differs from the
    supplied checkpoint. It is still not clearance: a changed source is
    marked decision_usable false and requires review. `REVIEW_REQUIRED` is
    reserved for malformed/missing checkpoints or unavailable/stale/invalid
    current evidence.
    """
    if not isinstance(checkpoint, Mapping):
        return _invalid_checkpoint("checkpoint must be an object")
    rows = _checkpoint_rows(checkpoint)
    if rows is None:
        return _invalid_checkpoint("checkpoint sources must contain known source IDs, versions and SHA-256 fingerprints")

    now = now or datetime.now(timezone.utc)
    state = load_state()
    lifecycle = production_source_status(now=now)
    current_by_id = {item["source_id"]: item for item in lifecycle["sources"]}
    results: list[dict[str, Any]] = []
    for source_id, prior in rows.items():
        current = current_by_id.get(source_id) or {}
        runtime = state["sources"].get(source_id) or {}
        unavailable = (
            bool(current.get("stale"))
            or current.get("last_fetch_status") in {"FETCH_ERROR", "INVALID_OBSERVATION", "MARKER_MISSING"}
            or not current.get("last_semantic_sha256")
        )
        changed = (
            prior.get("source_version") != current.get("source_version")
            or prior.get("semantic_sha256") != current.get("last_semantic_sha256")
        )
        if unavailable:
            status = "REVIEW_REQUIRED"
            reason = "current official evidence is stale, unavailable, invalid, or missing"
        elif changed:
            status = "CHANGED"
            reason = "current source version or semantic fingerprint differs from the checkpoint"
        else:
            status = "UNCHANGED"
            reason = "current source version and semantic fingerprint match the checkpoint"
        row = {
            **(_categories(source_id) if status == "CHANGED" else {"source_id": source_id, "rule_ids": [], "event_types": []}),
            "status": status,
            "reason": reason,
            "current_source_version": current.get("source_version"),
            "current_semantic_sha256": current.get("last_semantic_sha256"),
            "current_observed_at": runtime.get("last_success_at"),
            "decision_usable": status == "UNCHANGED" and not current.get("blocking"),
        }
        results.append(row)

    statuses = {row["status"] for row in results}
    overall = "REVIEW_REQUIRED" if "REVIEW_REQUIRED" in statuses else "CHANGED" if "CHANGED" in statuses else "UNCHANGED"
    return {
        "schema_version": "c5-monitoring-v1",
        "status": overall,
        "decision_usable": overall == "UNCHANGED" and all(row["decision_usable"] for row in results),
        "checked_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_gate": lifecycle["coverage_complete"],
        "sources": results,
        "next_action": "Continue only with current evidence." if overall == "UNCHANGED" else "Review current official GOV.UK evidence before relying on prior decisions.",
        "disclaimer": "Monitoring identifies source lifecycle changes; it is not legal advice, a Home Office decision, or clearance.",
    }


def _invalid_checkpoint(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "c5-monitoring-v1",
        "status": "REVIEW_REQUIRED",
        "decision_usable": False,
        "sources": [],
        "review_reasons": [reason],
        "next_action": "Supply a checkpoint created by this service and review official evidence.",
        "disclaimer": "Monitoring is fail closed when checkpoint or official evidence is unavailable.",
    }


def revalidate_decision(decision: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Prevent a prior decision with stale evidence from being presented as clearance."""
    output = deepcopy(dict(decision))
    checkpoint = output.get("evidence_checkpoint")
    if not isinstance(checkpoint, Mapping):
        output.update({
            "status": "REVIEW_REQUIRED",
            "decision_code": "EW-EVIDENCE-CHECKPOINT-MISSING",
            "previous_status": decision.get("status"),
            "stale_prior_decision": True,
            "review_reasons": ["prior decision has no source checkpoint"],
            "required_actions": ["Re-run the decision after obtaining current official-source evidence."],
        })
        return output
    comparison = changed_since(checkpoint, now=now)
    if comparison.get("status") != "UNCHANGED" or not comparison.get("decision_usable"):
        output.update({
            "status": "REVIEW_REQUIRED",
            "decision_code": "EW-EVIDENCE-STALE",
            "previous_status": decision.get("status"),
            "stale_prior_decision": True,
            "review_reasons": [f"source_monitoring:{comparison.get('status', 'REVIEW_REQUIRED').lower()}"],
            "required_actions": ["Review current official GOV.UK evidence and re-run the decision."],
        })
    else:
        output["stale_prior_decision"] = False
    output["monitoring"] = comparison
    return output
