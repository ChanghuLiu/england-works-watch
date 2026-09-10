from england_works_watch.x402_gate import PaidToolSpec, discovery_extensions


def test_assess_paid_tool_declares_mcp_bazaar_metadata():
    ext = discovery_extensions(
        PaidToolSpec(
            'assess_change_impact',
            '$0.02',
            'Official-source-backed Skilled Worker sponsor change-impact preflight.',
        )
    )
    assert set(ext) == {'bazaar'}
    info = ext['bazaar']['info']['input']
    assert info['type'] == 'mcp'
    assert info['toolName'] == 'assess_change_impact'
    assert info['transport'] == 'streamable-http'
    assert info['example']['payload']['event_type'] == 'unauthorised_absence'
    assert info['inputSchema']['required'] == ['payload']
    assert info['inputSchema']['properties']['payload']['required'] == ['event_type']


def test_batch_paid_tool_declares_bounded_changes_array():
    ext = discovery_extensions(
        PaidToolSpec(
            'batch_assess_changes',
            '$0.05',
            'Batch Skilled Worker sponsor change-impact preflight for up to 25 events.',
        )
    )
    info = ext['bazaar']['info']['input']
    changes = info['inputSchema']['properties']['payload']['properties']['changes']
    assert info['toolName'] == 'batch_assess_changes'
    assert changes['minItems'] == 1
    assert changes['maxItems'] == 25
    assert info['example']['payload']['changes'][0]['event_type'] == 'unauthorised_absence'
