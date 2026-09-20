from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from . import server


def _read(title: str) -> ToolAnnotations:
    return ToolAnnotations(
        title=title,
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
OPENAI_NAME = "RegEvidenceHub UK Sponsor Change"


def _instructions() -> str:
    return (
        DIRECTORY_DESCRIPTION
        + " Use assess_change_impact when the user provides facts about a specific sponsor-related change. "
        + "Use list_supported_change_events when the user's change type is unclear. "
        + "Use licensing_source_status only when source freshness or evidence status is relevant. "
        + "Use only facts explicitly supplied by the user. Never infer or default missing compliance facts, including "
        + "same_salary_option_still_met, salary amounts, occupation codes, going rates, role changes, or work-location changes. "
        + "Pass omitted facts through as missing so the deterministic engine can return INSUFFICIENT_INPUT. "
        + "This public AI edition is read-only and does not request, initiate, or process payments or cryptocurrency transfers."
    )


def _info_payload() -> dict[str, Any]:
    return {
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
    }


def _events_payload() -> dict[str, Any]:
    return {
        "events": server.SUPPORTED_EVENTS,
        "rule_pack_version": server.RULES["rule_pack_version"],
        "effective_date": server.RULES["effective_date"],
    }


def directory_assess(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the shared deterministic engine without the x402 payment boundary."""
    return server._assess(dict(payload))


directory_mcp = MCPServer(
    DIRECTORY_NAME,
    version=server.SERVICE_VERSION,
    instructions=_instructions(),
)


@directory_mcp.tool(annotations=_read("UK sponsor change checker information"), structured_output=True)
def sponsor_change_checker_info(ctx: Context) -> dict[str, Any]:
    """Explain the UK Skilled Worker sponsor-change checker scope and supported decision states."""
    return server._measured(
        "directory_sponsor_change_checker_info",
        _info_payload,
        billable=False,
        meta=server._meta(ctx),
    )


@directory_mcp.tool(annotations=_read("List supported sponsor change events"), structured_output=True)
def list_supported_change_events(ctx: Context) -> dict[str, Any]:
    """List sponsor-change event types this checker can assess for Skilled Worker sponsor duties."""
    return server._measured(
        "directory_list_supported_change_events",
        _events_payload,
        billable=False,
        meta=server._meta(ctx),
    )


@directory_mcp.tool(annotations=_read("UK sponsor guidance source status"), structured_output=True)
def licensing_source_status(ctx: Context) -> dict[str, Any]:
    """Check freshness and review status of the official GOV.UK evidence used by the sponsor-change checker."""
    return server._measured(
        "directory_licensing_source_status",
        server.production_source_status,
        billable=False,
        meta=server._meta(ctx),
    )


@directory_mcp.tool(annotations=_read("Assess sponsor change impact"), structured_output=True)
def assess_change_impact(payload: dict[str, Any], ctx: Context) -> dict[str, Any]:
    """Check whether a specific employee/company change affects UK Skilled Worker sponsor duties. Use for salary, role, work-location, absence, delayed-start, stop-sponsoring, organisation, TUPE, merger or takeover changes. Use only facts explicitly supplied by the user; never infer or default missing compliance facts such as same_salary_option_still_met. Pass omissions through so the deterministic engine can return INSUFFICIENT_INPUT. Returns an evidence-linked decision and required next action."""
    return server._measured(
        "directory_assess_change_impact",
        lambda: directory_assess(payload),
        billable=False,
        meta=server._meta(ctx),
    )


# OpenAI's current submission review definition treats even internal log writes
# as a state mutation for readOnlyHint. Preserve directory/Grok observability on
# directory_mcp, while exposing a telemetry-free OpenAI-specific surface whose
# declared read-only annotations exactly match its implementation behavior.
openai_mcp = MCPServer(
    OPENAI_NAME,
    version=server.SERVICE_VERSION,
    instructions=_instructions(),
)


@openai_mcp.tool(name="sponsor_change_checker_info", annotations=_read("UK sponsor change checker information"), structured_output=True)
def openai_sponsor_change_checker_info() -> dict[str, Any]:
    """Explain the UK Skilled Worker sponsor-change checker scope and supported decision states."""
    return _info_payload()


@openai_mcp.tool(
    name="list_supported_change_events",
    annotations=_read("List supported sponsor change events"),
    structured_output=True,
)
def openai_list_supported_change_events() -> dict[str, Any]:
    """List sponsor-change event types this checker can assess for Skilled Worker sponsor duties."""
    return _events_payload()


@openai_mcp.tool(
    name="licensing_source_status",
    annotations=_read("UK sponsor guidance source status"),
    structured_output=True,
)
def openai_licensing_source_status() -> dict[str, Any]:
    """Check freshness and review status of the official GOV.UK evidence used by the sponsor-change checker."""
    return server.production_source_status()


@openai_mcp.tool(
    name="assess_change_impact",
    annotations=_read("Assess sponsor change impact"),
    structured_output=True,
)
def openai_assess_change_impact(payload: dict[str, Any]) -> dict[str, Any]:
    """Check whether a specific employee/company change affects UK Skilled Worker sponsor duties. Use for salary, role, work-location, absence, delayed-start, stop-sponsoring, organisation, TUPE, merger or takeover changes. Use only facts explicitly supplied by the user; never infer or default missing compliance facts such as same_salary_option_still_met. Pass omissions through so the deterministic engine can return INSUFFICIENT_INPUT. Returns an evidence-linked decision and required next action."""
    return directory_assess(payload)
