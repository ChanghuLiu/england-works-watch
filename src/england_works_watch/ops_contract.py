from __future__ import annotations

from typing import Any

OPS_CONTRACT_VERSION = "regevidencehub-ops-v1"
ALERT_POLICY = {
    "notify_on": ["source_drift_or_blocking", "payment_error", "service_degraded"],
    "ignore": ["crawler_discovery", "ordinary_payment_challenge", "owner_test"],
}


def _overall_status(*, source_state: str, payment_state: str, service_degraded: bool) -> str:
    if service_degraded or source_state == "degraded" or payment_state == "degraded":
        return "degraded"
    if source_state == "review_required":
        return "review_required"
    return "ok"


def build_alerts(
    *,
    source_state: str,
    source_issue_count: int = 0,
    payment_errors: int = 0,
    service_degraded: bool = False,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if source_state == "degraded":
        alerts.append({"code": "SOURCE_DEGRADED", "severity": "critical", "count": max(1, int(source_issue_count or 0))})
    elif source_state == "review_required" and source_issue_count:
        alerts.append({"code": "SOURCE_REVIEW_REQUIRED", "severity": "warning", "count": int(source_issue_count)})
    if payment_errors:
        alerts.append({"code": "PAYMENT_FAILURES", "severity": "critical", "count": int(payment_errors)})
    if service_degraded:
        alerts.append({"code": "SERVICE_DEGRADED", "severity": "critical", "count": 1})
    return alerts


def health_payload(
    *,
    service: str,
    version: str,
    commit: str | None,
    source_state: str,
    payment_state: str,
    service_degraded: bool,
) -> dict[str, Any]:
    return {
        "contract": OPS_CONTRACT_VERSION,
        "status": _overall_status(source_state=source_state, payment_state=payment_state, service_degraded=service_degraded),
        "service": service,
        "version": version,
        "commit": commit,
        "serving": not service_degraded,
        "source_state": source_state,
        "payment_state": payment_state,
    }


def version_payload(*, service: str, version: str, commit: str | None, public_origin: str) -> dict[str, Any]:
    return {
        "contract": OPS_CONTRACT_VERSION,
        "service": service,
        "version": version,
        "commit": commit,
        "public_origin": public_origin,
    }


def status_payload(
    *,
    service: str,
    version: str,
    commit: str | None,
    source_state: str,
    payment_state: str,
    alerts: list[dict[str, Any]],
    service_degraded: bool,
) -> dict[str, Any]:
    return {
        "contract": OPS_CONTRACT_VERSION,
        "status": _overall_status(source_state=source_state, payment_state=payment_state, service_degraded=service_degraded),
        "service": service,
        "version": version,
        "commit": commit,
        "serving": not service_degraded,
        "source_state": source_state,
        "payment_state": payment_state,
        "alerts": alerts,
        "alert_policy": ALERT_POLICY,
    }
