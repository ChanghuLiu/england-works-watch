from __future__ import annotations

from england_works_watch.ops_contract import build_alerts, health_payload, status_payload, version_payload


def test_ops_contract_shapes_and_alert_policy():
    alerts = build_alerts(
        source_state="ready",
        source_issue_count=0,
        payment_errors=2,
        service_degraded=False,
    )
    assert alerts == [{"code": "PAYMENT_FAILURES", "severity": "critical", "count": 2}]

    health = health_payload(
        service="svc",
        version="1",
        commit="abc",
        source_state="ready",
        payment_state="ready",
        service_degraded=False,
    )
    assert health["contract"] == "regevidencehub-ops-v1"
    assert health["status"] == "ok"
    assert health["serving"] is True

    version = version_payload(service="svc", version="1", commit="abc", public_origin="https://example.com")
    assert version["public_origin"] == "https://example.com"

    status = status_payload(
        service="svc",
        version="1",
        commit="abc",
        source_state="ready",
        payment_state="ready",
        alerts=[],
        service_degraded=False,
    )
    assert status["alert_policy"]["ignore"] == ["crawler_discovery", "ordinary_payment_challenge", "owner_test"]
