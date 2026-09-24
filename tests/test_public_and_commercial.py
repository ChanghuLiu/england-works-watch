from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx

from england_works_watch.attribution import normalize_source_bucket
from england_works_watch.commercial import CommercialPlatformClient, CommercialPlatformError, CommercialSettings
from england_works_watch.public_surfaces import monitoring_page, render_policy_page, render_pricing_page


def test_public_policy_surfaces_and_pricing_are_bounded():
    for kind in ("privacy", "terms", "support"):
        page = render_policy_page(kind, origin="https://eww.example")
        assert "England Works Watch" in page
        assert "not immigration legal advice" in page
        assert "/pricing" in page and "/support" in page
    page = render_pricing_page(origin="https://eww.example", prices={"assess_change_impact": "$0.02 USDC per x402 call"})
    assert "$0.02" in page
    assert "Test-mode" not in page
    assert "shared commercial Stripe checkout" in page


def test_commercial_adapter_sends_only_bounded_contract_and_fails_closed():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        if request.url.path.endswith("checkout/session"):
            return httpx.Response(200, json={"checkout_id": "co_1", "stripe_session_id": "cs_test_1", "checkout_url": "https://checkout.stripe.test/1"})
        return httpx.Response(200, json={"active": True, "entitlement_code": "eww_sponsor_monitoring_report", "token": "signed"})

    settings = CommercialSettings(platform_url="https://commercial.test", human_origin="https://eww.test", success_url="https://eww.test/success", cancel_url="https://eww.test/cancel")
    client = CommercialPlatformClient(settings, transport=httpx.MockTransport(handler))
    checkout = asyncio.run(client.create_checkout(
        principal_ref="eww_human_opaque",
        source_channel="linkedin_post",
        external_classification="confirmed_external",
        success_url="https://eww.test/success?return_token=opaque",
    ))
    entitlement = asyncio.run(client.verify_entitlement(principal_ref="eww_human_opaque"))
    for event_type in ("checkout_started", "payment_succeeded", "entitlement_activated", "premium_fulfilled"):
        asyncio.run(client.record_event(
            event_type=event_type,
            source_channel="openai",
            external_classification="owner_test",
            owner_test=True,
        ))
    assert checkout["checkout_url"].startswith("https://")
    assert entitlement["active"] is True
    encoded = json.dumps(calls)
    assert "worker_name" not in encoded and "raw_prompt" not in encoded
    assert calls[0]["source_channel"] == "linkedin"
    assert calls[0]["external_classification"] == "confirmed_external"
    assert calls[0]["owner_test"] is False
    event_payloads = [payload for payload in calls if payload.get("event_type")]
    assert [payload["event_type"] for payload in event_payloads] == [
        "checkout_started", "payment_succeeded", "entitlement_activated", "premium_fulfilled",
    ]
    assert all(payload["commercial_intent"] == "monitoring" for payload in event_payloads)
    assert all(payload["source_channel"] == "openai" for payload in event_payloads)
    assert all(payload["external_classification"] == "owner_test" for payload in event_payloads)
    assert all(payload["owner_test"] is True for payload in event_payloads)

    bad = CommercialPlatformClient(settings, transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"active": True, "token": None})))
    try:
        asyncio.run(bad.verify_entitlement(principal_ref="eww_human_opaque"))
    except CommercialPlatformError as exc:
        assert "invalid active entitlement" in str(exc)
    else:
        raise AssertionError("invalid entitlement must fail closed")


def test_shared_platform_outage_cannot_break_free_info_or_decision(monkeypatch):
    from england_works_watch import server

    class OfflineCommercial:
        async def record_event(self, **_kwargs):
            raise AssertionError("telemetry should not be required by core tools")

    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", OfflineCommercial())
    monkeypatch.setattr(
        server,
        "production_source_status",
        lambda: {
            "coverage_complete": True,
            "blocking_sources": [],
            "review_required_sources": [],
            "stale_sources": [],
        },
    )
    assert server.england_works_watch_info(None)["payment"]["prices"] == {"assess_change_impact": "$0.02", "batch_assess_changes": "$0.05"}
    result = server._assess({"event_type": "unauthorised_absence", "route": "skilled_worker", "consecutive_working_days": 11})
    assert result["status"] == "AFFECTED"


def test_c7b_acquisition_aliases_and_monitoring_form_are_bounded():
    assert normalize_source_bucket("linkedin_post") == "linkedin"
    assert normalize_source_bucket("organic_search") == "organic"
    assert normalize_source_bucket("glama") == "glama"
    assert normalize_source_bucket("arbitrary-campaign") == "unknown"

    page = monitoring_page(origin="https://eww.test", source_channel="linkedin")
    assert 'name="source_channel" value="linkedin"' in page
    assert "Secure Stripe checkout" in page
    assert "Stripe Test checkout" not in page
    assert "Lock today\'s sponsor-guidance baseline — £49" in page
    assert "Lock today's sponsor-guidance baseline — £49" in page
    assert page.count('<form method="post" action="/monitoring-report/checkout">') == 2
    assert page.count('name="source_ids"') == 8
    for source_id in ("sponsor-part2", "sponsor-part3", "skilled-worker", "appendix-d"):
        assert page.count(f'value="{source_id}"') == 2
    assert 'name="independent_customer_confirmation"' in page
    assert 'value="yes" required' in page
    assert "Real purchase — not an operator/test run" in page
    assert "Sponsor duties and compliance — Part 3" in page
    assert "Keep sponsor-change decisions tied to current GOV.UK guidance for 30 days" in page
    assert "What you get for £49" in page
    assert "Create my 30-day evidence baseline — £49" in page
    assert "Source IDs" not in page

    owner_page = monitoring_page(
        origin="https://eww.test",
        source_channel="direct",
        owner_test=True,
    )
    assert 'name="run_class" value="owner_test"' in owner_page
    assert 'name="independent_customer_confirmation"' not in owner_page
    assert "excluded from customer and revenue evidence" in owner_page


def test_production_pricing_route_has_no_stale_test_mode_label():
    from england_works_watch import server

    response = asyncio.run(server.pricing(None))
    body = response.body.decode("utf-8")
    assert "Test-mode" not in body
    assert "shared commercial Stripe checkout" in body
    assert "£49" in body


def test_c7c_monitoring_traffic_quality_classification_is_bounded():
    from england_works_watch import server

    browser = SimpleNamespace(headers={"user-agent": "Mozilla/5.0"}, query_params={})
    node = SimpleNamespace(headers={"user-agent": "node"}, query_params={})
    indexer = SimpleNamespace(
        headers={"user-agent": "x402lens-indexer/1.0 (+https://x402lens.com/methodology)"},
        query_params={},
    )
    owner_node = SimpleNamespace(
        headers={"user-agent": "node"},
        query_params={"run": "owner_test"},
    )

    assert server._monitoring_classification(browser, {}) == ("unknown", False)
    assert server._monitoring_classification(
        browser, {"independent_customer_confirmation": "yes"}
    ) == ("confirmed_external", False)
    assert server._monitoring_classification(
        browser, {"independent_customer_confirmation": True}
    ) == ("confirmed_external", False)
    assert server._monitoring_classification(node, {}) == ("automated_external", False)
    assert server._monitoring_classification(
        node, {"independent_customer_confirmation": "yes"}
    ) == ("automated_external", False)
    assert server._monitoring_classification(indexer, {}) == ("automated_external", False)
    assert server._monitoring_classification(owner_node, {}) == ("owner_test", True)
    assert server._monitoring_classification(
        owner_node, {"independent_customer_confirmation": "yes"}
    ) == ("owner_test", True)


def test_paid_monitoring_return_requires_entitlement_and_reuses_link(monkeypatch, tmp_path):
    from england_works_watch import server
    from england_works_watch.commercial import PendingMonitoringCheckoutStore

    checkpoint = {
        "schema_version": "c5-monitoring-v1",
        "created_at": "2026-09-23T00:00:00Z",
        "sources": [{
            "source_id": "sponsor-part2",
            "source_version": "08/26",
            "semantic_sha256": "a" * 64,
            "observed_at": "2026-09-23T00:00:00Z",
        }],
    }
    store = PendingMonitoringCheckoutStore(1800, path=tmp_path / "pending.json")
    row = store.create(checkpoint=checkpoint, source_channel="direct")
    store.attach_checkout(row.return_token, "checkout_paid")
    request = SimpleNamespace(
        headers={"accept": "text/html"},
        query_params={"return_token": row.return_token},
    )

    class VerifiedCommercial:
        active = False

        async def verify_entitlement(self, **_kwargs):
            return {
                "active": self.active,
                "token": "signed" if self.active else None,
                "entitlement_code": "eww_sponsor_monitoring_report",
            }

    client = VerifiedCommercial()
    events = []

    async def record_event(event_type, **_kwargs):
        events.append(event_type)

    monkeypatch.setattr(server, "PENDING_MONITORING_CHECKOUTS", store)
    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", client)
    monkeypatch.setattr(server, "_safe_commercial_event", record_event)
    monkeypatch.setattr(server, "changed_since", lambda _checkpoint: {
        "status": "UNCHANGED",
        "checked_at": "2026-09-23T12:00:00Z",
        "decision_usable": True,
        "source_gate": True,
        "next_action": "Keep monitoring.",
        "disclaimer": "Not legal advice.",
        "sources": [],
    })

    denied = asyncio.run(server.monitoring_report_success(request))
    assert denied.status_code == 403
    assert store.get(row.return_token).paid_access_activated is False
    assert events == []

    client.active = True
    first = asyncio.run(server.monitoring_report_success(request))
    expiry = store.get(row.return_token).expires_at
    second = asyncio.run(server.monitoring_report_success(request))
    assert first.status_code == second.status_code == 200
    assert store.get(row.return_token).expires_at == expiry
    assert first.headers["referrer-policy"] == "no-referrer"
    assert first.headers["cache-control"] == "private, no-store"
    assert row.return_token in first.body.decode("utf-8")
    assert "Check these sources again" in first.body.decode("utf-8")
    assert events.count("payment_succeeded") == 1
    assert events.count("entitlement_activated") == 1
    assert events.count("premium_fulfilled") == 2


def test_monitoring_form_preserves_multiple_source_choices_and_legacy_comma_input():
    from england_works_watch import server

    class FormRequest:
        headers = {"content-type": "application/x-www-form-urlencoded"}

        def __init__(self, body: bytes):
            self.encoded = body

        async def body(self):
            return self.encoded

    selected = asyncio.run(server._read_monitoring_request(FormRequest(
        b"source_ids=sponsor-part2&source_ids=appendix-d&source_channel=organic"
    )))
    assert server._monitoring_ids(selected) == ["sponsor-part2", "appendix-d"]
    assert selected["source_channel"] == "organic"

    legacy = asyncio.run(server._read_monitoring_request(FormRequest(
        b"source_ids=sponsor-part2%2Csponsor-part3"
    )))
    assert server._monitoring_ids(legacy) == ["sponsor-part2", "sponsor-part3"]
