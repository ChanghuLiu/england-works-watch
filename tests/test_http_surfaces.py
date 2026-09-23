from __future__ import annotations

from datetime import datetime, timezone
import json

from starlette.testclient import TestClient

from test_source_runtime import _baseline


def test_local_public_policy_discovery_and_health_routes_return_200(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, now)
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")

    from england_works_watch.entrypoint import build_http_app

    with TestClient(build_http_app()) as client:
        for path in ("/health", "/pricing", "/privacy", "/terms", "/support", "/monitoring-report", "/llms.txt", "/sitemap.xml", "/openapi.json", "/.well-known/mcp/server-card.json", "/.well-known/x402"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
        assert client.get("/health").json()["status"] == "ok"
        assert "/monitoring-report" in client.get("/sitemap.xml").text
        assert "create_source_checkpoint" in client.get("/openapi.json").text or "monitoring" in client.get("/openapi.json").text
        llms = client.get("/llms.txt").text
        assert "Public AI/directory edition" in llms
        assert "Primary paid API: batch_assess_changes" in llms
        assert "30-day Sponsor Monitoring Report" in llms
        assert "free tools provide scope, source status" not in llms
        x402 = client.get("/.well-known/x402").json()
        assert x402["tools"]["batch_assess_changes"]["role"] == "primary paid API path for repeated work"
        assert x402["tools"]["batch_assess_changes"]["max_events"] == 25
        assert x402["recommended_paid_paths"]["monitoring_report"]["price"] == "£49"
        assert x402["public_ai_alternative"]["url"].endswith("/ai/mcp")


def test_monitoring_report_checkout_requires_verified_entitlement(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, now)
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")

    from england_works_watch import server
    from england_works_watch.entrypoint import build_http_app

    class FakeCommercial:
        def __init__(self):
            self.checkout_payload = None
            self.events = []
            self.active = True

        async def create_checkout(self, **kwargs):
            self.checkout_payload = kwargs
            return {"checkout_id": "co_test", "stripe_session_id": "cs_test", "checkout_url": "https://checkout.stripe.test/eww"}

        async def verify_entitlement(self, **_kwargs):
            return {
                "active": self.active,
                "entitlement_code": "eww_sponsor_monitoring_report" if self.active else None,
                "token": "signed" if self.active else None,
            }

        async def record_event(self, **kwargs):
            self.events.append(kwargs)

    fake = FakeCommercial()
    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", fake)
    with TestClient(build_http_app()) as client:
        started = client.post("/monitoring-report/checkout", json={"source_ids": ["sponsor-part2"], "worker_name": "must-not-cross-boundary"})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["status"] == "CHECKOUT_REQUIRED"
        assert "worker_name" not in json.dumps(fake.checkout_payload)
        completed = client.get(f"/monitoring-report/checkout-success?return_token={body['return_token']}")
        assert completed.status_code == 200
        assert completed.json()["status"] == "READY"
        assert completed.json()["report"]["status"] == "UNCHANGED"
        assert [event["event_type"] for event in fake.events] == [
            "paid_intent", "checkout_started", "payment_succeeded", "entitlement_activated", "premium_fulfilled",
        ]
        assert all(event["commercial_intent"] == "monitoring" for event in fake.events)
        assert all(event["source_channel"] == "direct" for event in fake.events)
        assert all(event["external_classification"] == "unknown" for event in fake.events)
        assert all(event["owner_test"] is False for event in fake.events)

        owner_started = client.post(
            "/monitoring-report/checkout?run=owner",
            json={"source_ids": ["sponsor-part2"]},
        )
        assert owner_started.status_code == 200
        owner_token = owner_started.json()["return_token"]
        owner_completed = client.get(f"/monitoring-report/checkout-success?return_token={owner_token}")
        assert owner_completed.status_code == 200
        assert all(event["external_classification"] == "owner_test" and event["owner_test"] is True for event in fake.events[5:])

        fake.active = False
        denied_started = client.post(
            "/monitoring-report/checkout",
            json={"source_ids": ["sponsor-part2"]},
        )
        denied = client.get(f"/monitoring-report/checkout-success?return_token={denied_started.json()['return_token']}")
        assert denied.status_code == 403
        fake.active = True


def test_monitoring_report_is_not_gated_by_telemetry_failure(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, now)
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")

    from england_works_watch import server
    from england_works_watch.entrypoint import build_http_app

    class FailingTelemetry:
        async def create_checkout(self, **_kwargs):
            return {"checkout_id": "co_test", "stripe_session_id": "cs_test", "checkout_url": "https://checkout.stripe.test/eww"}

        async def verify_entitlement(self, **_kwargs):
            return {"active": True, "entitlement_code": "eww_sponsor_monitoring_report", "token": "signed"}

        async def record_event(self, **_kwargs):
            raise RuntimeError("telemetry unavailable")

    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", FailingTelemetry())
    with TestClient(build_http_app()) as client:
        started = client.post("/monitoring-report/checkout", json={"source_ids": ["sponsor-part2"]})
        completed = client.get(f"/monitoring-report/checkout-success?return_token={started.json()['return_token']}")
    assert completed.status_code == 200
    assert completed.json()["status"] == "READY"


def test_paid_report_entitlement_code_wraps_without_layout_overflow():
    from england_works_watch.server import _monitoring_paid_page

    page = _monitoring_paid_page(
        entitlement_code="e" * 160,
        report={"status": "UNCHANGED", "decision_usable": True, "source_gate": True},
        return_token="sample-return-token",
    )
    assert "overflow-wrap:anywhere" in page
    assert "e" * 160 in page


def test_paid_monitoring_report_links_to_official_sources_and_escapes_result_text():
    from england_works_watch.policy import SOURCE_BY_ID
    from england_works_watch.server import _monitoring_paid_page

    page = _monitoring_paid_page(
        entitlement_code="monitoring",
        report={
            "status": "CHANGED",
            "checked_at": "2026-09-23T16:00:00Z",
            "sources": [
                {
                    "source_id": "sponsor-part3",
                    "status": "CHANGED",
                    "current_source_version": "08/26",
                    "current_observed_at": "2026-09-23T15:00:00Z",
                    "reason": "<untrusted>",
                },
                {
                    "source_id": "unknown-source",
                    "status": "REVIEW_REQUIRED",
                    "reason": "No official registry entry",
                },
            ],
        },
        return_token="private-token",
    )
    assert SOURCE_BY_ID["sponsor-part3"]["url"] in page
    assert SOURCE_BY_ID["sponsor-part3"]["title"] in page
    assert 'target="_blank" rel="noopener noreferrer"' in page
    assert "no detected change since that snapshot" in page
    assert "&lt;untrusted&gt;" in page
    assert "<untrusted>" not in page
    assert "<strong>unknown-source</strong>" in page
