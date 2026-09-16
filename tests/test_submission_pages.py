from __future__ import annotations

import asyncio

from england_works_watch import submission_pages


def _body(response) -> str:
    return response.body.decode("utf-8")


def test_public_submission_pages_are_human_readable():
    product = asyncio.run(submission_pages.plugin_product_page(None))
    privacy = asyncio.run(submission_pages.privacy_page(None))
    terms = asyncio.run(submission_pages.terms_page(None))
    support = asyncio.run(submission_pages.support_page(None))

    for response in (product, privacy, terms, support):
        assert response.status_code == 200
        assert response.media_type == "text/html"
        assert "UK Sponsor Change Checker" in _body(response)

    assert "does <strong>not</strong> persist the substantive sponsor-change scenario payload" in _body(privacy)
    assert "Not legal advice" in _body(terms)
    assert "launchcircle.server@gmail.com" in _body(support)


def test_openai_domain_challenge_fails_closed_without_token(monkeypatch):
    monkeypatch.delenv("OPENAI_APPS_CHALLENGE", raising=False)
    response = asyncio.run(submission_pages.openai_apps_challenge(None))
    assert response.status_code == 404
    assert response.body == b""


def test_openai_domain_challenge_returns_exact_configured_token(monkeypatch):
    monkeypatch.setenv("OPENAI_APPS_CHALLENGE", "openai-domain-proof-123")
    response = asyncio.run(submission_pages.openai_apps_challenge(None))
    assert response.status_code == 200
    assert _body(response) == "openai-domain-proof-123"
