from __future__ import annotations

import asyncio

from england_works_watch.directory_server import DIRECTORY_DESCRIPTION, directory_mcp


def test_directory_tools_are_read_only_and_payment_free():
    tools = asyncio.run(directory_mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == {
        "sponsor_change_checker_info",
        "list_supported_change_events",
        "licensing_source_status",
        "assess_change_impact",
    }

    for tool in by_name.values():
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False

    combined = " ".join(
        [DIRECTORY_DESCRIPTION]
        + [tool.description or "" for tool in by_name.values()]
    ).lower()
    assert "x402" not in combined
    assert "usdc" not in combined
    assert "crypto" not in combined
    assert "payment" not in combined
