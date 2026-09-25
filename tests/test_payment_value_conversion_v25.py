from __future__ import annotations


def test_representative_paid_preview_is_synthetic_and_matches_result_shape():
    from england_works_watch.policy import assess_change_impact
    from england_works_watch.selection_metadata import PAID_RESULT_PREVIEW

    preview = PAID_RESULT_PREVIEW
    assert preview["label"] == "Example paid result"
    assert preview["scenario"]["synthetic"] is True
    assert preview["scenario"]["event_type"] == "unauthorised_absence"

    actual = assess_change_impact(preview["scenario"] | {"consecutive_working_days": 11})
    assert set(preview["decision_shape"]) == set(actual)
    assert preview["decision_shape"]["status"] == "AFFECTED | NOT_AFFECTED | REVIEW_REQUIRED | INSUFFICIENT_INPUT"
    assert preview["review_example"]["status"] == "REVIEW_REQUIRED"


def test_free_paid_boundary_and_payment_guidance_are_explicit():
    from england_works_watch.selection_metadata import (
        FREE_PAID_BOUNDARY,
        PAYMENT_GUIDANCE,
        TOOL_SELECTION_DESCRIPTIONS,
    )

    assert "public AI/directory edition" in FREE_PAID_BOUNDARY["free"][0]
    assert "interactive" in FREE_PAID_BOUNDARY["free"][0]
    assert "assess_change_impact" in FREE_PAID_BOUNDARY["paid"][0]
    assert "batch_assess_changes" in FREE_PAID_BOUNDARY["paid"][1]
    assert "Sponsor Decision Evidence Check" in FREE_PAID_BOUNDARY["paid"][2]
    assert "automation and repeated business use" in FREE_PAID_BOUNDARY["paid_adds"]
    assert PAYMENT_GUIDANCE["network"] == "Base mainnet (eip155:8453)"
    assert PAYMENT_GUIDANCE["token"] == "USDC"
    assert "PaymentRequired" in PAYMENT_GUIDANCE["steps"][0]
    assert "retry the same paid tool" in PAYMENT_GUIDANCE["steps"][2].lower()
    assert "not executed" in PAYMENT_GUIDANCE["not_completed"]
    assert "Base mainnet USDC" in TOOL_SELECTION_DESCRIPTIONS["assess_change_impact"]


def test_price_network_token_and_payment_protocol_contract_are_unchanged():
    from england_works_watch.server import PRICE_ASSESS, PRICE_BATCH, _payment_info

    assert PRICE_ASSESS == "$0.02"
    assert PRICE_BATCH == "$0.05"
    payment = _payment_info()
    assert payment["protocol"] == "x402-v2"
    assert payment["scheme"] == "exact"
    assert payment["network"] == "eip155:8453"
    assert payment["asset"] == "USDC"
    assert payment["prices"] == {
        "assess_change_impact": "$0.02",
        "batch_assess_changes": "$0.05",
    }
    assert payment["recommended_paid_paths"]["batch_api"]["tool"] == "batch_assess_changes"
    assert payment["recommended_paid_paths"]["monitoring_report"]["price"] == "£49"
    assert "dated checkpoint" in payment["recommended_paid_paths"]["monitoring_report"]["value"]
    assert "public AI edition" in payment["recommended_paid_paths"]["single_event_api"]["positioning"]


def test_paid_decision_schema_and_attribution_contract_remain_separate():
    from england_works_watch.attribution import make_event
    from england_works_watch.policy import assess_change_impact

    result = assess_change_impact({
        "event_type": "unauthorised_absence",
        "route": "skilled_worker",
        "consecutive_working_days": 11,
    })
    assert {"status", "decision_code", "rationale", "required_actions", "affected_rules"} <= set(result)

    event = make_event(
        product_id="england_works_watch",
        event_type="paid_challenge",
        deployment_revision="test-revision",
        source_context="docker",
        owner_test=True,
    )
    assert event["source_bucket"] == "docker"
    assert event["owner_test"] is True
    assert event["external_classification"] == "owner_test"


def test_commercial_source_status_recommends_paid_next_step_without_changing_health(monkeypatch):
    from england_works_watch import server

    baseline = {
        "coverage_complete": True,
        "blocking_sources": [],
        "review_required_sources": [],
        "stale_sources": [],
        "rule_pack_version": "test-rules",
    }
    monkeypatch.setattr(server, "production_source_status", lambda: dict(baseline))

    result = server._commercial_source_status_payload()

    for key, value in baseline.items():
        assert result[key] == value
    next_step = result["recommended_next_step"]
    assert next_step["single_event"] == {
        "tool": "assess_change_impact",
        "price": "$0.02",
        "use_for": "One structured sponsor change requiring metered programmatic execution.",
    }
    assert next_step["batch_or_repeated"]["tool"] == "batch_assess_changes"
    assert next_step["batch_or_repeated"]["price"] == "$0.05"
    assert next_step["batch_or_repeated"]["max_events"] == 25
    assert next_step["payment"]["protocol"] == "x402-v2"
    assert next_step["payment"]["network"] == "eip155:8453"
    assert next_step["payment"]["asset"] == "USDC"
