from datetime import datetime, timedelta, timezone
import sqlite3

from england_works_watch import analytics


def test_time_windows_keep_boundary_future_and_invalid_legacy_rows(tmp_path, monkeypatch):
    monkeypatch.setenv('EWW_RUNTIME_DIR', str(tmp_path))
    fixed = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed
    monkeypatch.setattr(analytics, 'datetime', Clock)
    with analytics._db() as db:
        for value in [fixed-timedelta(hours=24), fixed-timedelta(hours=24,seconds=1), fixed+timedelta(hours=1), None]:
            db.execute('INSERT INTO events(occurred_at,tool,outcome,billable,actor_class) VALUES(?,?,?,?,?)', (value.isoformat() if value else 'invalid', 'other', 'ok', 0, 'unknown'))
    assert analytics._window_summary(None)['total_events'] == 4
    assert analytics._window_summary(24)['total_events'] == 2
    assert analytics._window_summary(168)['total_events'] == 3


def test_row_stream_releases_database_when_closed_early(tmp_path, monkeypatch):
    path = tmp_path / 'events.sqlite'
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms,event_type,source_bucket,external_classification,owner_test,deployment_revision,request_id,payment_status)')
    connection.execute('INSERT INTO events(id,occurred_at) VALUES(1,?)', ('2026-11-17T12:00:00Z',))
    monkeypatch.setattr(analytics, '_db', lambda: connection)
    stream = analytics._load_rows()
    assert iter(stream) is stream
    next(stream)
    stream.close()
    import pytest
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connection.execute('SELECT 1')
