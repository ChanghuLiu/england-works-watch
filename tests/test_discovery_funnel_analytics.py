from __future__ import annotations


def test_discovery_hits_are_raw_only_and_windowed(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    from england_works_watch.analytics import record_discovery, summary

    record_discovery("/.well-known/ai-catalog.json")
    record_discovery("/.well-known/api-catalog")

    window = summary()["windows"]["24h"]
    discovery = window["commercial_funnel"]["discovery"]

    assert discovery["measured"] is True
    assert discovery["raw"] == 2
    assert discovery["confirmed_external"] is None
    assert window["discovery_by_route"]["/.well-known/ai-catalog.json"] == 1
    assert window["discovery_by_route"]["/.well-known/api-catalog"] == 1
