from io import BytesIO
import subprocess
import pytest
from england_works_watch import source_runtime as sr
from test_source_runtime import _setup
from datetime import datetime, timezone


def test_oversized_official_page_is_error_not_truncated_hash(monkeypatch):
    body = BytesIO(b'x' * 2_000_001)
    monkeypatch.setattr(sr.urllib.request, 'urlopen', lambda *a, **k: body)
    with pytest.raises(ValueError, match='download size limit'):
        sr.fetch_official_source({'url': 'https://example.test/source'})
    assert body.closed


def test_worker_seeds_state_and_has_bounded_lifetime(monkeypatch, tmp_path):
    now = datetime.now(timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    called = []
    def run(args, **kwargs):
        assert sr.state_path().exists()
        assert args[1:] == ['-m', 'england_works_watch.source_runtime', '--observe-once']
        assert kwargs == {'check': True, 'timeout': 180}
        called.append(args)
    monkeypatch.setattr(sr.subprocess, 'run', run)
    sr.observe_in_subprocess()
    assert len(called) == 1
    assert sr.production_source_status(now=now)['sources_with_fingerprint_baseline'] == len(sr.SOURCES['sources'])


def test_worker_failure_does_not_refresh_stale_evidence(monkeypatch, tmp_path):
    from datetime import timedelta
    now = datetime.now(timezone.utc) - timedelta(hours=25)
    _setup(monkeypatch, tmp_path, now)
    sr.ensure_runtime_seeded(now)
    original = sr.state_path().read_bytes()
    def fail(*a, **k): raise subprocess.TimeoutExpired('owned fixture', 180)
    monkeypatch.setattr(sr.subprocess, 'run', fail)
    with pytest.raises(subprocess.TimeoutExpired): sr.observe_in_subprocess()
    assert sr.state_path().read_bytes() == original
    assert not sr.production_source_status()['coverage_complete']
