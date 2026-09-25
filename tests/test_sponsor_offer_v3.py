from __future__ import annotations


def test_sponsor_offer_v3_positions_paid_value_around_decision_evidence():
    from england_works_watch.public_surfaces import monitoring_page

    page = monitoring_page(
        origin="https://works.regevidencehub.com",
        source_channel="direct",
        owner_test=False,
    )

    assert 'content="sponsor-offer-v3-2026-09-25"' in page
    assert "Before a sponsor change, check that the Home Office guidance you rely on is still current" in page
    assert "30-day Sponsor Decision Evidence Check" in page
    assert "Create sponsor decision evidence checkpoint — £49" in page
    assert "Dated GOV.UK evidence checkpoint" in page
    assert "No worker PII required" in page
    assert "£49" in page


def test_sponsor_offer_v3_does_not_overpromise_case_decision_or_alerting():
    from england_works_watch.public_surfaces import monitoring_page

    page = monitoring_page(
        origin="https://works.regevidencehub.com",
        source_channel="direct",
        owner_test=False,
    )

    assert "The report does not decide those cases" in page
    assert "this service does not send alerts" in page
    assert "does not replace Home Office guidance or legal advice" in page
