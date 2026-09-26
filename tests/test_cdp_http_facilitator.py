import pytest

from england_works_watch.http_x402 import _http_facilitator_config, settings


def test_http_facilitator_defaults_to_existing_payai_url(monkeypatch):
    monkeypatch.delenv("EWW_HTTP_X402_FACILITATOR", raising=False)
    monkeypatch.delenv("EWW_HTTP_X402_FACILITATOR_URL", raising=False)
    monkeypatch.setenv("EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network")
    assert getattr(_http_facilitator_config(settings()), "url", None) == "https://facilitator.payai.network"


def test_cdp_mode_fails_closed_without_credentials(monkeypatch):
    monkeypatch.setenv("EWW_HTTP_X402_FACILITATOR", "cdp")
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="CDP_API_KEY_ID"):
        _http_facilitator_config(settings())
