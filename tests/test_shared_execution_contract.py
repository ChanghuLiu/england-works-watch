from datetime import datetime, timezone

from starlette.testclient import TestClient

from test_source_runtime import _baseline


def _healthy(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc))
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")


def test_continuation_case_and_shared_execution(monkeypatch, tmp_path):
    _healthy(monkeypatch, tmp_path)

    from england_works_watch import server
    from england_works_watch.case_state import DurableCaseStore
    from england_works_watch.entrypoint import build_http_app

    class FakeCommercial:
        async def issue_continuation(self, *, case_ref, state_ref):
            assert case_ref.startswith("eww_")
            assert state_ref.startswith("ews_")
            return {"continuation_token": "opaque-test-token", "expires_in_seconds": 1800}

    async def verified(token, *, platform_url, expected_product_id):
        assert token == "signed-entitlement"
        assert expected_product_id == "england_works_watch"
        return {"entitlement_code": "eww_sponsor_monitoring_report"}

    monkeypatch.setattr(server, "COMMERCIAL_CLIENT", FakeCommercial())
    monkeypatch.setattr(server, "DURABLE_CASES", DurableCaseStore(tmp_path / "runtime"))
    monkeypatch.setattr(server, "verify_entitlement_token", verified)

    with TestClient(build_http_app()) as client:
        created = client.post("/api/v1/continuation-case", json={
            "action": "sponsor_change_impact_preflight",
            "payload": {
                "event_type": "unauthorised_absence",
                "route": "skilled_worker",
                "consecutive_working_days": 11,
            },
            "source_bucket": "chatgpt",
            "classification": "synthetic",
            "owner_test": True,
        })
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["product_id"] == "england_works_watch"
        assert body["continuation_token"] == "opaque-test-token"

        denied = client.post("/api/v1/execute-restored-case", json={
            "contract_version": "reh-execution-v1",
            "product_id": "england_works_watch",
            "action": "wrong_action",
            "state_ref": body["state_ref"],
            "entitlement_token": "signed-entitlement",
        })
        assert denied.status_code == 422

        executed = client.post("/api/v1/execute-restored-case", json={
            "contract_version": "reh-execution-v1",
            "product_id": "england_works_watch",
            "action": "sponsor_change_impact_preflight",
            "state_ref": body["state_ref"],
            "entitlement_token": "signed-entitlement",
        })
        assert executed.status_code == 200, executed.text
        result = executed.json()
        assert result["contract_version"] == "reh-execution-v1"
        assert result["product_id"] == "england_works_watch"
        assert result["status"] == "executed"
        assert result["execution_id"].startswith("eww_")
        assert result["result"]["gateway_status"] == "OK"
        assert result["result"]["decision"]["event_type"] == "unauthorised_absence"
