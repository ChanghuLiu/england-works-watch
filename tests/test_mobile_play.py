from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from starlette.testclient import TestClient

from england_works_watch.commercial import PendingMonitoringCheckoutStore
from england_works_watch.entrypoint import build_http_app
from test_source_runtime import _baseline


def _http_environment(monkeypatch, tmp_path):
    baseline = tmp_path / "baseline.json"
    _baseline(baseline, datetime.now(timezone.utc))
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "1000")
    monkeypatch.setenv("EWW_SOURCE_MONITOR_ENABLED", "0")


def _report(_checkpoint):
    return {
        "status": "UNCHANGED", "status_label": "No verified change", "checked_at": "2026-10-18T12:00:00Z",
        "source_gate": True, "sources": [{"source_id": "sponsor-part2", "status": "UNCHANGED"}],
    }


def test_mobile_case_play_activation_persists_fingerprint_before_consumption(monkeypatch, tmp_path):
    from england_works_watch import server

    _http_environment(monkeypatch, tmp_path)
    store_path = tmp_path / "pending.json"
    store = PendingMonitoringCheckoutStore(1800, path=store_path)
    monkeypatch.setattr(server, "PENDING_MONITORING_CHECKOUTS", store)
    monkeypatch.setattr(server, "make_checkpoint", lambda ids: {
        "schema_version": "c5-monitoring-v1", "created_at": "2026-10-18T12:00:00Z",
        "sources": [{"source_id": ids[0], "source_version": "10/26", "semantic_sha256": "a" * 64, "observed_at": "2026-10-18T12:00:00Z"}],
    })
    monkeypatch.setattr(server, "changed_since", _report)
    google_purchase = {"productLineItem": [{"productId": "works_watch_30d", "productOfferDetails": {
        "purchaseOptionId": "one-watch", "quantity": 1,
        "consumptionState": "CONSUMPTION_STATE_YET_TO_BE_CONSUMED",
    }}], "purchaseStateContext": {"purchaseState": "PURCHASED"}}
    monkeypatch.setattr(server, "verify_purchase", lambda _token: google_purchase)
    consume_results = iter([False, True])
    consumed_tokens = []

    def consume(token):
        consumed_tokens.append(token)
        succeeded = next(consume_results)
        if succeeded:
            google_purchase["productLineItem"][0]["productOfferDetails"]["consumptionState"] = "CONSUMPTION_STATE_CONSUMED"
        return succeeded

    monkeypatch.setattr(server, "consume_purchase", consume)

    with TestClient(build_http_app()) as client:
        catalog = client.get("/api/mobile/v1/catalog").json()
        assert catalog["product_id"] == "works_watch_30d"
        assert catalog["purchase_option_id"] == "one-watch"
        assert catalog["payment_type"] == "one_time" and catalog["auto_renew"] is False
        created = client.post("/api/mobile/v1/cases", json={"source_ids": ["sponsor-part2"]}).json()
        assert created["status_label"] == "Ready to watch"
        case_token = created["case_token"]
        purchase_token = "play-secret-token-123"

        first = client.post("/api/mobile/v1/purchases/verify", json={"case_token": case_token, "purchase_token": purchase_token})
        assert first.status_code == 200 and first.json()["consume_pending"] is True
        persisted = json.loads(store_path.read_text())
        encoded = json.dumps(persisted)
        fingerprint = hashlib.sha256(purchase_token.encode()).hexdigest()
        assert purchase_token not in encoded
        assert fingerprint in encoded
        assert persisted["rows"][0]["paid_access_activated"] is True

        second = client.post("/api/mobile/v1/purchases/verify", json={"case_token": case_token, "purchase_token": purchase_token})
        assert second.status_code == 200 and second.json()["consume_pending"] is False
        expires_at = second.json()["access_expires_at"]
        third = client.post("/api/mobile/v1/purchases/verify", json={"case_token": case_token, "purchase_token": purchase_token})
        assert third.status_code == 200 and third.json()["access_expires_at"] == expires_at
        other_case = client.post("/api/mobile/v1/cases", json={"source_ids": ["sponsor-part2"]}).json()
        replay = client.post("/api/mobile/v1/purchases/verify", json={"case_token": other_case["case_token"], "purchase_token": purchase_token})
        assert replay.status_code == 403
        status = client.post("/api/mobile/v1/status", json={"case_token": case_token}).json()
        assert status["status"] == "ACTIVE"
        assert len(consumed_tokens) == 2
        assert consumed_tokens == [purchase_token, purchase_token]

    restarted = PendingMonitoringCheckoutStore(1800, path=store_path)
    restored = restarted.get(case_token)
    assert restored is not None and restored.paid_access_activated is True
    assert restored.purchase_token_sha256 == fingerprint
    assert restored.consume_pending is False


def test_mobile_purchase_verifier_missing_fails_closed(monkeypatch, tmp_path):
    from england_works_watch import server

    _http_environment(monkeypatch, tmp_path)
    store = PendingMonitoringCheckoutStore(1800)
    checkpoint = {
        "schema_version": "c5-monitoring-v1", "created_at": "2026-10-18T12:00:00Z",
        "sources": [{"source_id": "sponsor-part2", "source_version": "10/26", "semantic_sha256": "a" * 64, "observed_at": None}],
    }
    row = store.create(checkpoint=checkpoint, source_channel="direct")
    monkeypatch.setattr(server, "PENDING_MONITORING_CHECKOUTS", store)
    monkeypatch.setattr(server, "changed_since", _report)
    monkeypatch.setattr(server, "verify_purchase", lambda _token: (_ for _ in ()).throw(server.PlayVerifierUnavailable("missing")))

    with TestClient(build_http_app()) as client:
        response = client.post("/api/mobile/v1/purchases/verify", json={"case_token": row.return_token, "purchase_token": "not-persisted"})
    assert response.status_code == 503
    assert response.json()["status"] == "VERIFICATION_UNAVAILABLE"
    assert store.get(row.return_token).paid_access_activated is False


def test_source_uncertainty_suppresses_purchase_and_google_verification(monkeypatch, tmp_path):
    from england_works_watch import server

    _http_environment(monkeypatch, tmp_path)
    store = PendingMonitoringCheckoutStore(1800, path=tmp_path / "pending.json")
    monkeypatch.setattr(server, "PENDING_MONITORING_CHECKOUTS", store)
    monkeypatch.setattr(server, "make_checkpoint", lambda ids: {
        "schema_version": "c5-monitoring-v1", "created_at": "2026-10-18T12:00:00Z",
        "sources": [{"source_id": ids[0], "source_version": "10/26", "semantic_sha256": "a" * 64, "observed_at": None}],
    })
    monkeypatch.setattr(server, "changed_since", lambda _checkpoint: {
        "status": "REVIEW_REQUIRED", "status_label": "Source unavailable or review needed",
        "source_gate": False, "sources": [],
    })
    monkeypatch.setattr(server, "verify_purchase", lambda _token: (_ for _ in ()).throw(AssertionError("must not call Google when sources are uncertain")))

    with TestClient(build_http_app()) as client:
        created = client.post("/api/mobile/v1/cases", json={"source_ids": ["sponsor-part2"]}).json()
        assert created["purchase_available"] is False
        denied = client.post("/api/mobile/v1/purchases/verify", json={"case_token": created["case_token"], "purchase_token": "unused"})
    assert denied.status_code == 409
    assert denied.json()["status"] == "SOURCE_REVIEW_REQUIRED"
    assert store.get(created["case_token"]).paid_access_activated is False


def test_purchase_fingerprint_cannot_be_bound_to_two_cases(tmp_path):
    store = PendingMonitoringCheckoutStore(1800, path=tmp_path / "pending.json")
    checkpoint = {
        "schema_version": "c5-monitoring-v1", "created_at": "2026-10-18T12:00:00Z",
        "sources": [{"source_id": "sponsor-part2", "source_version": "10/26", "semantic_sha256": "a" * 64, "observed_at": None}],
    }
    first = store.create(checkpoint=checkpoint, source_channel="direct")
    second = store.create(checkpoint=checkpoint, source_channel="direct")
    fingerprint = hashlib.sha256(b"one play token").hexdigest()
    assert store.activate_play_purchase(first.return_token, fingerprint) == "activated"
    assert store.activate_play_purchase(second.return_token, fingerprint) == "purchase_already_bound"
    assert store.activate_play_purchase(first.return_token, fingerprint) == "already_active"
    assert store.get(first.return_token).expires_at > first.expires_at


def test_play_productpurchasev2_schema_is_checked(monkeypatch):
    from england_works_watch import play_billing

    class Response:
        status_code = 200

        def json(self):
            return {
                "purchaseStateContext": {"purchaseState": "PURCHASED"},
                "productLineItem": [{"productId": "works_watch_30d", "productOfferDetails": {
                    "purchaseOptionId": "one-watch", "quantity": 1,
                    "consumptionState": "CONSUMPTION_STATE_YET_TO_BE_CONSUMED",
                }}],
            }

    class Session:
        def get(self, url, timeout):
            assert "com.regevidencehub.workswatch/purchases/productsv2/tokens/" in url
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(play_billing, "_authorized_session", Session)
    result = play_billing.verify_purchase("play-token")
    assert result["purchaseStateContext"]["purchaseState"] == "PURCHASED"
