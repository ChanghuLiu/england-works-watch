from england_works_watch.keyword_taxonomy import KEYWORD_TAXONOMY, LONG_TAIL_RULES, generate_supported_long_tail, taxonomy_terms


def test_taxonomy_is_unique_nonempty_and_bounded():
    terms = taxonomy_terms()
    assert len(terms) == 34
    assert len(set(terms)) == len(terms)
    assert all(1 <= len(term) <= 100 for term in terms)
    assert set(KEYWORD_TAXONOMY) == {"sponsor_compliance_scope", "reportable_worker_changes", "sponsor_organisation_events", "evidence_and_monitoring", "professional_agent_workflows"}
    assert len(LONG_TAIL_RULES) == 4


def test_long_tail_generation_requires_structured_supported_values():
    result = generate_supported_long_tail([
        {"event": "salary change", "source": "Home Office", "workflow": "HR"},
        {"event": "role change", "source": "Part 2", "workflow": "People Ops"},
    ])
    assert "salary change sponsor compliance change monitoring" in result
    assert "Part 2 sponsor guidance changed since checkpoint" in result
    assert all("raw" not in value.lower() for value in result)
