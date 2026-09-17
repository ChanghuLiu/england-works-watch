from __future__ import annotations

import asyncio
import json

import httpx

from england_works_watch.commercial import CommercialPlatformClient, CommercialPlatformError, CommercialSettings
from england_works_watch.public_surfaces import render_policy_page, render_pricing_page


def test_public_policy_surfaces_and_pricing_are_bounded():
    for kind in ("privacy", "terms", "support"):
        page = render_policy_page(kind, origin="https://eww.example")
        assert "England Works Watch" in page
        assert "not immigration legal advice" in page
        assert "/pricing" in page and "/support" in page
    page = render_pricing_page(origin="https://eww.example", prices={"assess_change_impact": "$0.02 USDC per x402 call"})
    assert "$0.02" in page
    assert "Test-mode" in page


def test_commercial_adapter_sends_only_bounded_contract_and_fails_closed():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        if request.url.path.endswith("checkout/session"):
            return httpx.Response(200, json={"checkout_id": "co_1", "stripe_session_id": "cs_test_1", "checkout_url": "https://checkout.stripe.test/1"})
        return httpx.Response(200, json={"active": True, "entitlement_code": "eww_sponsor_monitoring_report", "token": "signed"})

    settings = CommercialSettings(platform_url="https://commercial.test", human_origin="https://eww.test", success_url="https://eww.test/success", cancel_url="https://eww.test/cancel")
    client = CommercialPlatformClient(settings, transport=httpx.MockTransport(handler))
    checkout = asyncio.run(client.create_checkout(principal_ref="eww_human_opaque", source_channel="openai", success_url="https://eww.test/success?return_token=opaque"))
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
    assert calls[0]["source_channel"] == "openai"
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
    assert server.england_works_watch_info(None)["payment"]["prices"] == {"assess_change_impact": "$0.02", "batch_assess_changes": "$0.05"}
    result = server._assess({"event_type": "unauthorised_absence", "route": "skilled_worker", "consecutive_working_days": 11})
    assert result["status"] == "AFFECTED"
