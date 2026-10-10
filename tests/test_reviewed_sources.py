from datetime import datetime, timezone
import json

import pytest

from england_works_watch import source_runtime as sr
from england_works_watch.policy import SOURCES, assess_change_impact
from england_works_watch.source_evidence import missing_expected_markers
from test_source_runtime import _setup


def test_previous_version_in_change_log_does_not_satisfy_current_version():
    html = '<main><p>Version 10/26</p><p>This version replaces Version 08/26.</p></main>'
    assert missing_expected_markers(html, ['Version 08/26']) == ['Version 08/26']
    assert missing_expected_markers(html, ['Version 10/26']) == []


def test_unreviewed_baseline_cannot_seed(monkeypatch, tmp_path):
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    payload = json.loads(sr.baseline_path().read_text())
    payload['sources'][0]['semantic_sha256'] = 'f' * 64
    sr.baseline_path().write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match='differs from reviewed'):
        sr.ensure_runtime_seeded(now)
    assert not sr.state_path().exists()


def test_explicit_review_upgrade_archives_state_and_only_applies_once(monkeypatch, tmp_path):
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    old = sr.ensure_runtime_seeded(now)
    old['registry_version'] = SOURCES['supersedes_registry_version']
    item = next(iter(old['sources'].values()))
    item['review_required'] = True
    item['last_semantic_sha256'] = 'e' * 64
    sr._atomic_write(sr.state_path(), old)
    upgraded = sr.ensure_runtime_seeded(now)
    assert upgraded['registry_version'] == SOURCES['registry_version']
    assert all(not s['review_required'] for s in upgraded['sources'].values())
    assert json.loads(sr.Path(upgraded['previous_state_archive']).read_text()) == old
    source = SOURCES['sources'][0]
    sr.apply_observation(upgraded, source, {'http_status': 200, 'semantic_sha256': 'f' * 64}, now=now)
    sr._atomic_write(sr.state_path(), upgraded)
    assert sr.ensure_runtime_seeded(now)['sources'][source['source_id']]['review_required']


def test_unknown_registry_never_auto_upgrades(monkeypatch, tmp_path):
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    _setup(monkeypatch, tmp_path, now)
    state = sr.ensure_runtime_seeded(now)
    state['registry_version'] = 'unknown'
    sr._atomic_write(sr.state_path(), state)
    with pytest.raises(RuntimeError, match='explicit review'):
        sr.ensure_runtime_seeded(now)
    assert json.loads(sr.state_path().read_text())['registry_version'] == 'unknown'


@pytest.mark.parametrize('flag', ['modern_slavery_identified', 'employment_conditions_lifted'])
def test_special_employment_conditions_require_review(flag):
    result = assess_change_impact({'event_type': 'role_change', 'same_occupation_code': False, flag: True})
    assert result['status'] == 'REVIEW_REQUIRED'
    assert result['affected_rules'][0]['locator'] == 'S8.28-S8.29'


def test_review_date_still_expires():
    from england_works_watch.policy import source_status
    assert source_status('2026-10-10')['coverage_complete']
    assert not source_status('2026-11-10')['coverage_complete']
