from england_works_watch.attribution import make_event, normalize_source_bucket, source_context_from_meta


def test_unified_attribution_envelope_correlates_source_client_and_payment():
    source = source_context_from_meta({
        "source_context": "402explorer",
        "commercial/request_id": "req-eww-1",
        "io.modelcontextprotocol/clientInfo": {"name": "external-agent", "version": "5.0"},
    })
    event = make_event(
        product_id="eww",
        event_type="business_tool_call",
        source_context=source,
        deployment_revision="abc123",
        tool_name="assess_change_impact",
        outcome="OK",
    )
    assert event["schema_version"] == "commercial-attribution-v1"
    assert event["source_bucket"] == "402explorer"
    assert event["request_id"] == "req-eww-1"
    assert event["declared_client"] == "external-agent"
    assert event["declared_client_version"] == "5.0"
    assert event["tool_name"] == "assess_change_impact"
    assert event["outcome"] == "OK"
    assert event["payment_status"] == "not_applicable"


def test_paid_execution_maps_to_paid_status():
    event = make_event(
        product_id="eww",
        event_type="paid_executed",
        source_context="agent402",
        external="confirmed_external",
        deployment_revision="abc123",
        outcome="PAID_EXECUTED",
    )
    assert event["payment_status"] == "paid"
    assert event["external_classification"] == "confirmed_external"



def test_regevidencehub_source_is_preserved():
    assert normalize_source_bucket("regevidencehub") == "regevidencehub"
