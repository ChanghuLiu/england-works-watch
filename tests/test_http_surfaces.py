from __future__ import annotations

from datetime import datetime, timezone
import json

import asyncio

import httpx

from test_source_runtime import _baseline


class ASGIClient:
    """Synchronous test facade that avoids TestClient's AnyIO portal startup."""

    def __init__(self, app):
        self.app = app
        self.cookies = httpx.Cookies()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def request(self, method, url, **kwargs):
        async def send():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://testserver",
                cookies=self.cookies,
                follow_redirects=kwargs.pop("follow_redirects", False),
            ) as client:
                response = await client.request(method, url, **kwargs)
                self.cookies.update(response.cookies)
                return response
        return asyncio.run(send())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)


def test_local_public_policy_discovery_and_health_routes_return_200(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, now)
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")

    from england_works_watch.entrypoint import build_http_app

    client = ASGIClient(build_http_app())
    if True:
        for path in ("/health", "/pricing", "/privacy", "/terms", "/support", "/monitoring-report", "/llms.txt", "/sitemap.xml", "/openapi.json", "/.well-known/mcp/server-card.json", "/.well-known/x402", "/.well-known/agent-card.json"):
            response = client.get(path)
            assert response.status_code == 200, (path, response.text)
        assert client.get("/health").json()["status"] == "ok"
        assert "/monitoring-report" in client.get("/sitemap.xml").text
        assert "create_source_checkpoint" in client.get("/openapi.json").text or "monitoring" in client.get("/openapi.json").text
        llms = client.get("/llms.txt").text
        assert "Public AI/directory edition" in llms
        assert "Primary paid API: batch_assess_changes" in llms
        assert "30-day Sponsor Decision Evidence Check" in llms
        assert "free tools provide scope, source status" not in llms
        x402 = client.get("/.well-known/x402").json()
        assert x402["tools"]["batch_assess_changes"]["role"] == "primary paid API path for repeated work"
        assert x402["tools"]["batch_assess_changes"]["max_events"] == 25
        assert x402["recommended_paid_paths"]["monitoring_report"]["price"] == "£49"
        assert x402["public_ai_alternative"]["url"].endswith("/ai/mcp")
        agent_card = client.get("/.well-known/agent-card.json").json()
        assert agent_card["public_ai_mcp"].endswith("/ai/mcp")
        assert agent_card["monitoring_report"].endswith("/monitoring-report")
        assert "Sponsor Decision Evidence Check" in agent_card["commercial_value"]["continued_monitoring"]
        assert agent_card["capabilities"]["monitoring"] is True
        assert "batch_assess_changes" in agent_card["commercial_value"]["primary_paid_api"]
        assert "one-off interactive" in agent_card["instructions"]


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

        async def create_report_checkout(self, **kwargs):
            self.checkout_payload = kwargs
            self.checkout_count = getattr(self, "checkout_count", 0) + 1
            checkout_id = f"co_test_{self.checkout_count}"
            return {"checkout_id": checkout_id, "checkout_url": "https://checkout.stripe.test/eww", "report_claim_token": f"claim-{checkout_id}"}

        async def claim_report_access(self, *, checkout_id, report_claim_token):
            assert report_claim_token == f"claim-{checkout_id}"
            return {"report_session": f"session-{checkout_id}"}

        async def verify_report_access(self, *, checkout_id, report_session):
            return self.active and report_session == f"session-{checkout_id}"

        async def record_event(self, **kwargs):
            self.events.append(kwargs)

    fake = FakeCommercial()
    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", fake)
    with ASGIClient(build_http_app()) as client:
        started = client.post("/monitoring-report/checkout", json={"source_ids": ["sponsor-part2"], "contact_email": "buyer@example.test", "worker_name": "must-not-cross-boundary"})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["status"] == "CHECKOUT_REQUIRED"
        assert "worker_name" not in json.dumps(fake.checkout_payload)
        completed = client.get("/monitoring-report/checkout-success", headers={"accept": "application/json", "cookie": "report_claim_co_test_1=claim-co_test_1"})
        assert completed.status_code == 200
        assert completed.json()["status"] == "READY"
        assert completed.json()["report"]["status"] == "UNCHANGED"
        assert [event["event_type"] for event in fake.events] == [
            "paid_intent", "checkout_started", "payment_succeeded", "entitlement_activated", "premium_fulfilled",
        ]
        assert all(event["commercial_intent"] == "monitoring" for event in fake.events)
        assert all(event["source_channel"] == "direct" for event in fake.events)
        assert {event["external_classification"] for event in fake.events} <= {"unknown", "automated_external"}, fake.events
        assert all(event["owner_test"] is False for event in fake.events)

        owner_started = client.post(
            "/monitoring-report/checkout?run=owner",
            json={"source_ids": ["sponsor-part2"], "contact_email": "buyer@example.test"},
        )
        assert owner_started.status_code == 200
        owner_completed = client.get("/monitoring-report/checkout-success", headers={"accept": "application/json", "cookie": "report_claim_co_test_2=claim-co_test_2"})
        assert owner_completed.status_code == 200
        assert all(event["external_classification"] == "owner_test" and event["owner_test"] is True for event in fake.events[5:])

        fake.active = False
        denied_started = client.post(
            "/monitoring-report/checkout",
            json={"source_ids": ["sponsor-part2"], "contact_email": "buyer@example.test"},
        )
        # Each checkout claim is bound to its own cookie; do not let the prior
        # successful browser session authorize this unpaid checkout.
        denied_id = denied_started.json()["checkout_id"]
        denied = client.get("/monitoring-report/checkout-success", headers={"accept": "text/html", "cookie": f"report_claim_{denied_id}=claim-{denied_id}"})
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
        async def create_report_checkout(self, **_kwargs):
            self.counter = getattr(self, "counter", 0) + 1
            checkout_id = f"co_telemetry_{self.counter}"
            return {"checkout_id": checkout_id, "checkout_url": "https://checkout.stripe.test/eww", "report_claim_token": f"claim-{checkout_id}"}

        async def claim_report_access(self, *, checkout_id, report_claim_token):
            return {"report_session": f"session-{checkout_id}"}

        async def verify_report_access(self, **_kwargs):
            return True

        async def record_event(self, **_kwargs):
            raise RuntimeError("telemetry unavailable")

    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", FailingTelemetry())
    client = ASGIClient(build_http_app())
    started = client.post("/monitoring-report/checkout", json={"source_ids": ["sponsor-part2"], "contact_email": "buyer@example.test"})
    checkout_id = started.json()["checkout_id"]
    completed = client.get("/monitoring-report/checkout-success", headers={"accept": "application/json", "cookie": f"report_claim_{checkout_id}=claim-{checkout_id}"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "READY"


def test_paid_report_entitlement_code_wraps_without_layout_overflow():
    from england_works_watch.server import _monitoring_paid_page

    page = _monitoring_paid_page(
        entitlement_code="e" * 160,
        report={"status": "UNCHANGED", "decision_usable": True, "source_gate": True},
        checkout_id="sample-checkout-id",
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
        checkout_id="private-checkout-id",
    )
    assert SOURCE_BY_ID["sponsor-part3"]["url"] in page
    assert SOURCE_BY_ID["sponsor-part3"]["title"] in page
    assert 'target="_blank" rel="noopener noreferrer"' in page
    assert "no detected change since that snapshot" in page
    assert "&lt;untrusted&gt;" in page
    assert "<untrusted>" not in page
    assert "<strong>unknown-source</strong>" in page
