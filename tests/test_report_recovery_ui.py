import asyncio
from urllib.parse import urlencode

import httpx
from starlette.applications import Starlette
from starlette.routing import Route

from england_works_watch import server


def test_recovery_form_escapes_prefill_and_allows_its_styles():
    async def check():
        app = Starlette(routes=[Route("/monitoring-report/recover", server.monitoring_report_recover)])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://staging.example") as client:
            response = await client.get("/monitoring-report/recover?" + urlencode({"checkout_id": '"><img src=x onerror=alert(1)>'}))
            assert response.status_code == 200
            assert "&lt;img" in response.text and "<img" not in response.text
            assert 'for="checkout-id"' in response.text and 'for="contact-email"' in response.text
            assert "style-src 'unsafe-inline'" in response.headers["content-security-policy"]
            assert response.headers["cache-control"] == "no-store"
            assert "set-cookie" not in response.headers
            assert "No further payment is needed" in response.text
    asyncio.run(check())


def test_recovery_bootstrap_returns_to_the_order_from_the_email_link():
    response = server._recovery_bootstrap_response()
    page = response.body.decode()
    assert response.status_code == 200
    assert "/api/v1/report-access/redeem" in page
    assert "checkout_id='+encodeURIComponent(checkout_id)" in page


def test_recovery_bootstrap_retains_order_reference_on_success_return():
    response = server._recovery_bootstrap_response()
    page = response.body.decode()
    assert "/monitoring-report/checkout-success?checkout_id=" in page
    assert "encodeURIComponent(checkout_id)" in page


def test_recovery_service_failures_are_not_reported_as_accepted(monkeypatch):
    class Commercial:
        outcome = True
        calls = 0

        async def start_report_recovery(self, **kwargs):
            self.calls += 1
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

    service = Commercial()
    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", service)

    async def check():
        app = Starlette(routes=[Route("/api/v1/report-access/recovery", server.start_report_recovery, methods=["POST"])])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://staging.example") as client:
            payload = {"checkout_id": "a" * 32, "contact_email": "buyer@example.invalid"}
            accepted = await client.post("/api/v1/report-access/recovery", json=payload)
            assert accepted.status_code == 200
            assert accepted.json()["status"] == "If a paid report matches those details, a recovery link will be sent."
            for outcome in (False, RuntimeError("Unavailable")):
                service.outcome = outcome
                denied = await client.post("/api/v1/report-access/recovery", json=payload)
                assert denied.status_code == 503
                assert denied.headers["cache-control"] == "no-store"
            for bad in ({**payload, "checkout_id": ""}, {**payload, "contact_email": "not-an-email"}):
                invalid = await client.post("/api/v1/report-access/recovery", json=bad)
                assert invalid.status_code == 422
            assert service.calls == 3
    asyncio.run(check())


def test_browser_errors_preserve_machine_status_without_exposing_internal_details():
    import json
    from types import SimpleNamespace
    from england_works_watch.purchase_ui import browser_report_response
    payload = {"status": "COMMERCIAL_UNAVAILABLE", "detail": "internal transport failure"}
    api = browser_report_response(SimpleNamespace(headers={}), payload, status_code=503, headers={"Cache-Control":"private, no-store"})
    assert api.status_code == 503 and json.loads(api.body) == payload
    assert api.headers["cache-control"] == "private, no-store"
    browser = browser_report_response(SimpleNamespace(headers={"accept":"text/html"}), payload, status_code=503)
    assert browser.status_code == 503
    assert "internal transport failure" not in browser.body.decode()
    assert "/monitoring-report/recover" in browser.body.decode()
    assert browser.headers["referrer-policy"] == "no-referrer"
