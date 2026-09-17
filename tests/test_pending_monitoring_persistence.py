import time

from england_works_watch.commercial import PendingMonitoringCheckoutStore


def _checkpoint():
    return {
        "schema_version": "c5-monitoring-v1",
        "created_at": "2026-09-17T12:00:00Z",
        "sources": [{
            "source_id": "sponsor-part2",
            "source_version": "2026-07-01",
            "semantic_sha256": "a" * 64,
            "observed_at": "2026-09-17T11:00:00Z",
        }],
    }


def test_pending_monitoring_checkout_survives_store_recreation(tmp_path):
    path = tmp_path / "pending-monitoring.json"

    first = PendingMonitoringCheckoutStore(
        1800,
        path=path,
    )

    created = first.create(
        checkpoint=_checkpoint(),
        source_channel="direct",
        classification="owner_test",
        owner_test=True,
    )

    first.attach_checkout(
        created.return_token,
        "checkout_test_restart",
    )

    second = PendingMonitoringCheckoutStore(
        1800,
        path=path,
    )

    restored = second.get(created.return_token)

    assert restored is not None
    assert restored.return_token == created.return_token
    assert restored.principal_ref == created.principal_ref
    assert restored.checkout_id == "checkout_test_restart"
    assert restored.source_channel == "direct"
    assert restored.checkpoint == created.checkpoint
    assert restored.classification == "owner_test"
    assert restored.owner_test is True
    assert restored.expires_at > time.time()
    persisted = path.read_text(encoding="utf-8")
    assert "worker_name" not in persisted
    assert "employer" not in persisted
    assert "case_fact" not in persisted
    assert "stripe_secret" not in persisted.lower()
    assert "STRIPE_SECRET_KEY" not in persisted
    assert "STRIPE_WEBHOOK_SECRET" not in persisted
    assert path.stat().st_mode & 0o077 == 0


def test_expired_persisted_checkout_is_not_restored(tmp_path):
    path = tmp_path / "pending-monitoring.json"

    first = PendingMonitoringCheckoutStore(
        60,
        path=path,
    )

    created = first.create(
        checkpoint=_checkpoint(),
        source_channel="direct",
    )

    import json

    payload = json.loads(path.read_text())
    payload["rows"][0]["expires_at"] = time.time() - 1
    path.write_text(json.dumps(payload))

    second = PendingMonitoringCheckoutStore(
        60,
        path=path,
    )

    assert second.get(created.return_token) is None


def test_no_path_preserves_process_local_behavior_and_rejects_case_facts():
    store = PendingMonitoringCheckoutStore(1800)
    created = store.create(checkpoint=_checkpoint(), source_channel="direct")
    assert store.get(created.return_token) is created

    try:
        store.create(
            checkpoint={**_checkpoint(), "worker_name": "must-not-persist"},
            source_channel="direct",
        )
    except ValueError as exc:
        assert "unsupported fields" in str(exc)
    else:
        raise AssertionError("case facts must not be accepted into pending state")


def test_corrupt_persisted_file_fails_safely(tmp_path):
    path = tmp_path / "pending-monitoring.json"
    path.write_text("not-json", encoding="utf-8")
    try:
        PendingMonitoringCheckoutStore(1800, path=path)
    except RuntimeError as exc:
        assert "unreadable" in str(exc)
    else:
        raise AssertionError("corrupt state must fail closed")
