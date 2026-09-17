from __future__ import annotations

from datetime import datetime, timedelta, timezone

from england_works_watch import source_runtime as sr
from england_works_watch.monitoring import changed_since, make_checkpoint, revalidate_decision
from england_works_watch.policy import SOURCES

from test_source_runtime import _setup


def test_checkpoint_round_trip_is_unchanged(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    checkpoint = make_checkpoint(["sponsor-part2", "skilled-worker"])
    result = changed_since(checkpoint, now=now)
    assert result["status"] == "UNCHANGED"
    assert result["decision_usable"] is True
    assert all(row["rule_ids"] == [] for row in result["sources"])


def test_changed_checkpoint_is_review_signal_with_existing_categories(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)
    checkpoint = make_checkpoint(["sponsor-part3"])
    source = next(item for item in SOURCES["sources"] if item["source_id"] == "sponsor-part3")
    sr.observe_all(lambda current: {"http_status": 200, "semantic_sha256": "f" * 64, "missing_markers": []} if current["source_id"] == source["source_id"] else {"http_status": 200, "semantic_sha256": hashes[current["source_id"]], "missing_markers": []}, now=now + timedelta(hours=1))
    result = changed_since(checkpoint, now=now + timedelta(hours=1))
    row = result["sources"][0]
    assert result["status"] == "CHANGED"
    assert result["decision_usable"] is False
    assert "unauthorised_absence" in row["event_types"]
    assert row["rule_ids"]


def test_stale_checkpoint_and_evidence_unavailable_fail_closed(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    checkpoint = make_checkpoint(["sponsor-part2"])
    stale = changed_since(checkpoint, now=now + timedelta(hours=25))
    assert stale["status"] == "REVIEW_REQUIRED"
    assert stale["decision_usable"] is False

    sr.observe_all(lambda _source: (_ for _ in ()).throw(OSError("source unavailable")), now=now + timedelta(hours=1))
    unavailable = changed_since(checkpoint, now=now + timedelta(hours=1))
    assert unavailable["status"] == "REVIEW_REQUIRED"
    assert unavailable["decision_usable"] is False


def test_prior_decision_without_or_with_stale_checkpoint_cannot_be_clearance(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)
    checkpoint = make_checkpoint(["sponsor-part2"])
    decision = {"status": "AFFECTED", "decision_code": "example", "evidence_checkpoint": checkpoint}
    current = revalidate_decision(decision, now=now)
    assert current["stale_prior_decision"] is False
    sr.observe_all(lambda source: {"http_status": 200, "semantic_sha256": "e" * 64, "missing_markers": []} if source["source_id"] == "sponsor-part2" else {"http_status": 200, "semantic_sha256": hashes[source["source_id"]], "missing_markers": []}, now=now + timedelta(hours=1))
    stale = revalidate_decision(decision, now=now + timedelta(hours=1))
    assert stale["status"] == "REVIEW_REQUIRED"
    assert stale["stale_prior_decision"] is True
    missing = revalidate_decision({"status": "NOT_AFFECTED"}, now=now)
    assert missing["status"] == "REVIEW_REQUIRED"
    assert missing["stale_prior_decision"] is True


def test_malformed_checkpoint_is_review_required(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    result = changed_since({"sources": [{"source_id": "unknown", "semantic_sha256": "0" * 64, "source_version": "x"}]})
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["decision_usable"] is False
