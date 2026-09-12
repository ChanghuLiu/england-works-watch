from __future__ import annotations

import json


def test_allowlisted_unknown_and_no_source_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))
    from england_works_watch.analytics import record, record_discovery, summary
    from england_works_watch.attribution import normalize_source_bucket, source_bucket_from_query

    assert normalize_source_bucket("docker") == "docker"
    assert normalize_source_bucket("this_should_not_be_persisted") == "unknown"
    assert source_bucket_from_query("") == "unknown"
    record_discovery("/", query="src=docker&raw_personal_value=discard")
    record("england_works_watch_info", "ok", billable=False, meta={"source_context": "not-allowed"})
    payload = json.dumps(summary())
    assert "raw_personal_value" not in payload
    assert "not-allowed" not in payload
    assert summary()["windows"]["24h"]["source_attribution"]["docker"]["discovery_observed"] == 1
    assert summary()["windows"]["24h"]["source_attribution"]["unknown"]["free_business_call"] == 1


def test_owner_external_and_paid_events_have_common_attribution_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("EWW_DEPLOY_REV", "test-revision")
    from england_works_watch.analytics import _db, record, summary

    record("england_works_watch_info", "ok", billable=False, meta={"source_context": "glama", "englandworkswatch/actor": "owned_ci"})
    record("england_works_watch_info", "ok", billable=False, meta={"source_context": "glama", "englandworkswatch/actor": "declared_external"})
    record("assess_change_impact", "ok", billable=True, payment_state="challenge", meta={"source_context": "docker", "englandworkswatch/actor": "owned_ci"})
    record("assess_change_impact", "ok", billable=True, payment_state="paid_executed", meta={"source_context": "docker", "englandworkswatch/actor": "declared_external"})

    with _db() as connection:
        row = connection.execute("SELECT source_bucket,external_classification,owner_test,deployment_revision FROM events ORDER BY id DESC LIMIT 1").fetchone()
    assert row == ("docker", "confirmed_external", 0, "test-revision")
    funnel = summary()["windows"]["24h"]["commercial_funnel"]
    assert funnel["free_business_call"]["confirmed_external"] == 1
    assert funnel["paid_challenge"]["confirmed_external"] == 0
    assert funnel["paid_executed"]["confirmed_external"] == 1
