from england_works_watch.discovery_ecosystem import classify_source


def test_smithery_scanner_is_bounded_indexer_source():
    assert classify_source("SmitheryBot/1.0 (+https://smithery.ai)", "mcp_server_card") == ("smithery", "indexer")
