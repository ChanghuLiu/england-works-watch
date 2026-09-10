from __future__ import annotations


def test_windowed_commercial_funnel_separates_owner_external_and_unattributed(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    from england_works_watch.analytics import record, summary

    external_meta = {
        "io.modelcontextprotocol/clientInfo": {"name": "external-agent", "version": "1.0"}
    }
    owner_meta = {
        "englandworkswatch/actor": "owned_ci",
        "io.modelcontextprotocol/clientInfo": {"name": "local-owner-paid-smoke"},
    }

    record("england_works_watch_info", "ok", billable=False, meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=external_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta=owner_meta)
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta={})

    window = summary()["windows"]["24h"]["commercial_funnel"]

    assert window["free_business_call"]["raw"] == 1
    assert window["free_business_call"]["confirmed_external"] == 1
    assert window["paid_executed"]["raw"] == 4
    assert window["paid_executed"]["confirmed_external"] == 2
    assert window["repeat_paid"]["raw"] == 1
    assert window["repeat_paid"]["confirmed_external"] == 1
