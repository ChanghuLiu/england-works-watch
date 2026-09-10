from england_works_watch.selection_metadata import (
    CHANGE_PROPERTIES,
    SERVER_SELECTION_DESCRIPTION,
    TOOL_SELECTION_DESCRIPTIONS,
)


def test_discovery_description_covers_supported_router_vocabulary():
    vocabulary = (
        "absence",
        "salary",
        "occupation-code",
        "home-working",
        "delayed starts",
        "worker departure",
        "organisation changes",
        "TUPE",
        "mergers/takeovers",
        "Home Office/UKVI sponsor reporting",
    )
    text = " ".join((SERVER_SELECTION_DESCRIPTION, *TOOL_SELECTION_DESCRIPTIONS.values()))
    for term in vocabulary:
        assert term.lower() in text.lower()


def test_event_schema_describes_router_terms_without_changing_event_values():
    assert CHANGE_PROPERTIES["event_type"]["enum"] == [
        "worker_start_delay",
        "unauthorised_absence",
        "unpaid_or_reduced_pay_absence",
        "salary_change",
        "role_change",
        "work_location_change",
        "stop_sponsoring",
        "organisation_change",
        "tupe_transfer",
        "merger_takeover",
    ]
    assert "occupation-code" in CHANGE_PROPERTIES["same_occupation_code"]["description"]
    assert "home working" in CHANGE_PROPERTIES["permanent_remote"]["description"]
