from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from . import server

READ = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

DIRECTORY_NAME = "UK Sponsor Change Checker"
DIRECTORY_DESCRIPTION = (
    "Check whether a salary, role, work location, absence, delayed start, stopping sponsorship, "
    "organisation change, TUPE transfer, merger or takeover affects UK Skilled Worker sponsor duties. "
    "Returns AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, or INSUFFICIENT_INPUT with official GOV.UK "
    "evidence and required next actions. Read-only compliance preflight; not legal advice."
)

directory_mcp = MCPServer(
    DIRECTORY_NAME,
    version=server.SERVICE_VERSION,
    instructions=(
        DIRECTORY_DESCRIPTION
        + " Use assess_change_impact when the user provides facts about a specific sponsor-related change. "
        + "Use list_supported_change_events when the user's change type is unclear. "
        + "Use licensing_source_status only when source freshness or evidence status is relevant. "
        + "This directory edition is read-only and does not request, initiate, or process payments or cryptocurrency transfers."
    ),
)


@directory_mcp.tool(annotations=READ, structured_output=True)
def sponsor_change_checker_info(ctx: Context) -> dict[str, Any]:
    """Explain the UK Skilled Worker sponsor-change checker scope and supported decision states."""
    return server._measured(
        "directory_sponsor_change_checker_info",
        lambda: {
            "service": DIRECTORY_NAME,
            "powered_by": "England Works Watch",
            "description": DIRECTORY_DESCRIPTION,
            "scope": server.RULES["scope"],
            "supported_events": server.SUPPORTED_EVENTS,
            "decision_labels": [
                "AFFECTED",
                "NOT_AFFECTED",
                "REVIEW_REQUIRED",
                "INSUFFICIENT_INPUT",
            ],
            "evidence": "Official GOV.UK sponsor guidance with runtime fingerprint/change monitoring.",
            "read_only": True,
            "not_legal_advice": True,
        },
        billable=False,
        meta=server._meta(ctx),
    )


@directory_mcp.tool(annotations=READ, structured_output=True)
def list_supported_change_events(ctx: Context) -> dict[str, Any]:
    """List sponsor-change event types this checker can assess for Skilled Worker sponsor duties."""
    return server._measured(
        "directory_list_supported_change_events",
        lambda: {
            "events": server.SUPPORTED_EVENTS,
            "rule_pack_version": server.RULES["rule_pack_version"],
            "effective_date": server.RULES["effective_date"],
        },
        billable=False,
        meta=server._meta(ctx),
    )


@directory_mcp.tool(annotations=READ, structured_output=True)
def licensing_source_status(ctx: Context) -> dict[str, Any]:
    """Check freshness and review status of the official GOV.UK evidence used by the sponsor-change checker."""
    return server._measured(
        "directory_licensing_source_status",
        server.production_source_status,
        billable=False,
        meta=server._meta(ctx),
    )


def directory_assess(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the shared deterministic engine without the x402 payment boundary."""
    return server._assess(dict(payload))


@directory_mcp.tool(annotations=READ, structured_output=True)
def assess_change_impact(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Check whether a specific employee/company change affects UK Skilled Worker sponsor duties. Use for salary, role, work-location, absence, delayed-start, stop-sponsoring, organisation, TUPE, merger or takeover changes. Returns an evidence-linked decision and required next action."""
    return server._measured(
        "directory_assess_change_impact",
        lambda: directory_assess(payload),
        billable=False,
        meta=server._meta(ctx),
    )
