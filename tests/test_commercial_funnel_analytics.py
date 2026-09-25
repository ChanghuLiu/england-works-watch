from __future__ import annotations


def test_windowed_commercial_funnel_separates_owner_external_and_unattributed(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    from england_works_watch.analytics import record, summary

    external_meta = {
        "io.modelcontextprotocol/clientInfo": {"name": "external-agent", "version": "1.0"},
        "source_context": "glama",
    }
    owner_meta = {
        "englandworkswatch/actor": "owned_ci",
        "io.modelcontextprotocol/clientInfo": {"name": "local-owner-paid-smoke"},
    }

    record("england_works_watch_info", "ok", billable=False, meta=external_meta)
    record("list_supported_change_events", "ok", billable=False, meta=external_meta)
    record("batch_assess_changes", "challenge", billable=True, payment_state="challenge", meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=owner_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta={})

    summary_24h = summary()["windows"]["24h"]
    window = summary_24h["commercial_funnel"]

    assert window["free_business_call"]["raw"] == 2
    assert window["free_business_call"]["confirmed_external"] == 2
    assert window["paid_executed"]["raw"] == 4
    assert window["paid_executed"]["confirmed_external"] == 2
    assert summary_24h["confirmed_external_by_tool"] == {
        "free_business_call": {
            "england_works_watch_info": 1,
            "list_supported_change_events": 1,
        },
        "paid_challenge": {"batch_assess_changes": 1},
        "paid_executed": {"assess_change_impact": 2},
    }
    assert summary_24h["confirmed_external_by_source"] == {
        "free_business_call": {"glama": 2},
        "paid_challenge": {"glama": 1},
        "paid_executed": {"glama": 2},
    }
    assert window["repeat_paid"]["raw"] == 1
    assert window["repeat_paid"]["confirmed_external"] == 1


def test_known_declared_client_fills_unknown_source_without_exposing_client(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    from england_works_watch.analytics import record, summary

    record(
        "assess_change_impact",
        "challenge",
        billable=True,
        payment_state="challenge",
        meta={"io.modelcontextprotocol/clientInfo": {"name": "grok-connector", "version": "1.0"}},
    )
    record(
        "assess_change_impact",
        "challenge",
        billable=True,
        payment_state="challenge",
        meta={"io.modelcontextprotocol/clientInfo": {"name": "external-agent", "version": "1.0"}},
    )

    window = summary()["windows"]["24h"]

    assert window["confirmed_external_by_source"]["paid_challenge"] == {
        "grok": 1,
        "unknown": 1,
    }
    assert window["confirmed_external_by_software_family"]["paid_challenge"] == {
        "grok": 1,
        "other_declared_software": 1,
    }
    assert "grok-connector" not in str(window)
    assert "external-agent" not in str(window)
