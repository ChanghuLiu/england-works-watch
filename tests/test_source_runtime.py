from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from england_works_watch import source_runtime as sr
from england_works_watch.policy import SOURCES


def _baseline(path: Path, generated: datetime) -> dict[str, str]:
    hashes = {}
    rows = []
    for index, source in enumerate(SOURCES["sources"]):
        digest = f"{index + 1:064x}"[-64:]
        hashes[source["source_id"]] = digest
        rows.append(
            {
                "source_id": source["source_id"],
                "state": "UNCHANGED",
                "http_status": 200,
                "semantic_sha256": digest,
                "missing_markers": [],
                "source_version": source["version"],
                "valid_from": source["valid_from"],
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at": generated.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "registry_version": SOURCES["registry_version"],
                "blocking_count": 0,
                "sources": rows,
            }
        )
    )
    return hashes


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, now: datetime):
    baseline = tmp_path / "baseline.json"
    hashes = _baseline(baseline, now)
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("EWW_SOURCE_BASELINE_PATH", str(baseline))
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("EWW_SOURCE_MAX_AGE_HOURS", "24")
    return hashes


def test_seed_has_full_baseline_coverage(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    state = sr.ensure_runtime_seeded(now)
    assert len(state["sources"]) == 4
    status = sr.production_source_status(now=now)
    assert status["coverage_complete"] is True
    assert status["sources_with_fingerprint_baseline"] == 4
    assert status["decision_sources_with_fingerprint_baseline"] == 4
    assert status["blocking_sources"] == []


def test_unchanged_observation_stays_ready(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)

    def fetcher(source):
        return {"http_status": 200, "semantic_sha256": hashes[source["source_id"]], "missing_markers": []}

    sr.observe_all(fetcher, now=now + timedelta(hours=1))
    status = sr.production_source_status(now=now + timedelta(hours=1))
    assert status["coverage_complete"] is True
    assert status["review_required_sources"] == []
    assert status["fetch_status_counts"] == {"UNCHANGED": 4}


def test_changed_fingerprint_fails_closed_without_promoting_baseline(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)
    changed_id = SOURCES["sources"][0]["source_id"]
    changed_hash = "f" * 64

    def fetcher(source):
        digest = changed_hash if source["source_id"] == changed_id else hashes[source["source_id"]]
        return {"http_status": 200, "semantic_sha256": digest, "missing_markers": []}

    state = sr.observe_all(fetcher, now=now + timedelta(hours=1))
    item = state["sources"][changed_id]
    assert item["baseline_semantic_sha256"] == hashes[changed_id]
    assert item["last_semantic_sha256"] == changed_hash
    assert item["review_required"] is True
    assert item["last_fetch_status"] == "CHANGED_PENDING_REVIEW"
    status = sr.production_source_status(now=now + timedelta(hours=1))
    assert status["coverage_complete"] is False
    assert changed_id in status["blocking_sources"]


def test_transient_fetch_error_uses_fresh_last_success_then_stales(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)
    failed_id = SOURCES["sources"][0]["source_id"]

    def fetcher(source):
        if source["source_id"] == failed_id:
            raise OSError("temporary network error")
        return {"http_status": 200, "semantic_sha256": hashes[source["source_id"]], "missing_markers": []}

    sr.observe_all(fetcher, now=now + timedelta(hours=1))
    fresh = sr.production_source_status(now=now + timedelta(hours=2))
    assert fresh["coverage_complete"] is True
    assert fresh["fetch_status_counts"]["FETCH_ERROR"] == 1

    stale = sr.production_source_status(now=now + timedelta(hours=25))
    assert stale["coverage_complete"] is False
    assert failed_id in stale["stale_sources"]
    assert failed_id in stale["blocking_sources"]


def test_missing_marker_fails_closed(monkeypatch, tmp_path):
    now = datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc)
    hashes = _setup(monkeypatch, tmp_path, now)
    failed_id = SOURCES["sources"][1]["source_id"]

    def fetcher(source):
        return {
            "http_status": 200,
            "semantic_sha256": hashes[source["source_id"]],
            "missing_markers": ["expected marker"] if source["source_id"] == failed_id else [],
        }

    sr.observe_all(fetcher, now=now + timedelta(hours=1))
    status = sr.production_source_status(now=now + timedelta(hours=1))
    assert status["coverage_complete"] is False
    assert failed_id in status["review_required_sources"]
