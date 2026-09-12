from __future__ import annotations

from copy import deepcopy
from typing import Any

SERVER_SELECTION_DESCRIPTION = (
    "UK Skilled Worker sponsor-compliance change intelligence for employer, HR and HRIS agents. "
    "Use for official GOV.UK source freshness, Home Office/UKVI sponsor reporting, supported sponsor change categories, "
    "and one-event or batch impact preflight. Supported vocabulary includes absence, salary, role or occupation-code "
    "change, work-location or home-working change, delayed starts, stopping sponsorship or worker departure, "
    "organisation changes, TUPE transfers, and mergers/takeovers. Paid deterministic decisions return AFFECTED, "
    "NOT_AFFECTED, REVIEW_REQUIRED or INSUFFICIENT_INPUT with evidence and fail closed on stale/changed sources. "
    "Not individual visa advice or a Home Office decision."
)

PAID_RESULT_PREVIEW: dict[str, Any] = {
    "label": "Example paid result",
    "scenario": {
        "event_type": "unauthorised_absence",
        "route": "skilled_worker",
        "consecutive_working_days": 11,
        "synthetic": True,
    },
    "decision_shape": {
        "status": "AFFECTED | NOT_AFFECTED | REVIEW_REQUIRED | INSUFFICIENT_INPUT",
        "decision_code": "for example, EW-ABS-REPORT",
        "event_type": "the supplied supported event type",
        "scope": "UK Skilled Worker sponsor duties and sponsor change-impact preflight only",
        "rule_pack_version": "version-bound rule pack",
        "effective_date": "rule-pack effective date",
        "rationale": ["evidence-linked explanation"],
        "required_actions": ["next sponsor action when applicable"],
        "deadline": {"working_days": "when applicable", "trigger": "event-specific trigger"},
        "missing_inputs": [],
        "review_reasons": [],
        "affected_rules": [
            {"rule_id": "SPONSOR-ABSENCE-10", "source_id": "sponsor-part3", "locator": "C1.15", "version": "08/26"}
        ],
        "disclaimer": "Evidence-first sponsor compliance preflight. Not legal advice.",
    },
    "review_example": {
        "status": "REVIEW_REQUIRED",
        "review_reasons": ["source_not_current or an unresolved input conflict"],
        "required_actions": ["review the blocking evidence or supply the missing facts"],
    },
    "value": "The paid decision adds a deterministic outcome, evidence-linked rationale, required action/deadline fields, and an explicit fail-closed review state. Free tools provide scope, supported-event vocabulary, and source lifecycle status; they do not return a change-impact decision.",
}

FREE_PAID_BOUNDARY: dict[str, Any] = {
    "free": [
        "england_works_watch_info: scope, supported events, price and payment metadata",
        "licensing_source_status: official-source freshness and review state",
        "list_supported_change_events: supported sponsor-change vocabulary",
    ],
    "paid": [
        "assess_change_impact: one structured sponsor-change decision",
        "batch_assess_changes: 1-25 structured sponsor-change decisions",
    ],
    "paid_adds": "Free tools do not return a change-impact decision. Paid tools add a deterministic AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, or INSUFFICIENT_INPUT result with evidence-linked rationale and next-action fields.",
}

PAYMENT_GUIDANCE: dict[str, Any] = {
    "label": "x402 payment guidance",
    "network": "Base mainnet (eip155:8453)",
    "token": "USDC",
    "steps": [
        "Call the paid tool without payment metadata to receive the x402 PaymentRequired challenge.",
        "Review the amount and sign the accepted Base-USDC authorization buyer-side.",
        "Retry the same paid tool call with the payment metadata.",
        "The service verifies payment before returning the deterministic decision.",
    ],
    "not_completed": "If payment is not completed or settlement is not verified, the paid decision is not executed; follow the returned challenge or payment error guidance.",
    "security": "Never send private keys or seed phrases to this service. Wallet compatibility is determined by the buyer runtime and its x402 support.",
}

TOOL_SELECTION_DESCRIPTIONS: dict[str, str] = {
    "england_works_watch_info": (
        "Free product information. Use for service scope, what England Works Watch does, pricing, cost, x402 network, "
        "payment, MCP endpoint, discovery metadata, or legal-advice disclaimer. Not for source freshness, supported-event "
        "lists, or change decisions. See the Example paid result and x402 payment guidance for the paid boundary."
    ),
    "licensing_source_status": (
        "Free GOV.UK evidence source status. Use for current guidance, source freshness, stale sources, changed "
        "fingerprints, blocking sources, review status, evidence lifecycle, or source coverage. Not for a specific "
        "sponsor change decision."
    ),
    "list_supported_change_events": (
        "Free supported-event list. Use for capability questions such as 'Does this support salary, role and work location changes?' "
        "or when asking which sponsor events the tool can handle, which change "
        "types/categories are supported, or to list supported events: absence, salary, role or occupation code, "
        "work location or home working, delayed start, stopping sponsorship or worker departure, organisation change, "
        "TUPE, merger, takeover, or Home Office/UKVI sponsor reporting. Capability/list only; not impact, reporting, "
        "or required-action decisions."
    ),
    "assess_change_impact": (
        "Paid single-event change decision. Use for one concrete Skilled Worker sponsor event to determine impact, "
        "including questions such as 'Does moving one sponsored worker to permanent home working trigger reporting?', "
        "whether Home Office/UKVI sponsor reporting is triggered, whether it is AFFECTED/NOT_AFFECTED, what the sponsor "
        "must do, or required actions. Handles one absence, salary, role or occupation-code, remote/home/work-location, "
        "delayed-start, stop-sponsoring/worker-departure, organisation, TUPE, merger, or takeover event. Returns an "
        "evidence-linked rationale, required action/deadline fields, and explicit review or missing-input state. "
        "Payment: x402 Base mainnet USDC; sign buyer-side and retry this same tool with payment metadata. Not multiple events."
    ),
    "batch_assess_changes": (
        "Paid batch/multiple-event change decision for 1-25 events. Use for a list, batch, set, several, many, multiple, "
        "5, 8, 20 or other collection of sponsor changes; evaluate them together and return per-event results plus "
        "outcome counts. Payment: x402 Base mainnet USDC; sign buyer-side and retry this same tool with payment metadata. "
        "Not for one event."
    ),
}

CHANGE_PROPERTIES: dict[str, dict[str, Any]] = {
    "event_type": {
        "type": "string",
        "enum": [
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
        ],
        "description": "Sponsor change event category to assess: absence; salary; role or occupation-code change; work-location or home-working change; delayed start; stopping sponsorship or worker departure; organisation change; TUPE transfer; or merger/takeover."
    },
    "route": {
        "type": "string",
        "enum": ["skilled_worker"],
        "description": "Visa route for the sponsor-duty decision. V0.1 supports Skilled Worker only; unsupported routes fail closed."
    },
    "delay_days": {"type": "integer", "minimum": 0, "description": "For worker_start_delay: days after the relevant Skilled Worker start-date trigger."},
    "consecutive_working_days": {"type": "integer", "minimum": 0, "description": "For unauthorised_absence: consecutive working days absent without authorisation."},
    "total_weeks": {"type": "number", "minimum": 0, "description": "For unpaid_or_reduced_pay_absence: total weeks of the absence at unpaid or reduced pay."},
    "valid_exception": {"type": "boolean", "description": "For an absence: whether a listed permitted-absence exception is established."},
    "compelling_reason": {"type": "boolean", "description": "For an absence: whether a compelling reason is established under the sponsor-duty rule."},
    "direction": {"type": "string", "enum": ["increase", "decrease"], "description": "Whether the salary change increases or decreases pay."},
    "pre_registration_nurse_or_midwife": {"type": "boolean", "description": "For salary_change: whether the worker is a pre-registration nurse or midwife covered by the modeled salary branch."},
    "same_salary_option_still_met": {"type": "boolean", "description": "For salary_change: whether the original Skilled Worker salary option remains met after the change."},
    "revised_salary_meets_skilled_worker": {"type": "boolean", "description": "For salary_change: whether the revised salary still meets a Skilled Worker salary basis."},
    "same_occupation_code": {"type": "boolean", "description": "For role_change: whether the new role keeps the same occupation code; occupation-code changes may require a new CoS/application."},
    "role_eligible": {"type": "boolean", "description": "For role_change: whether the proposed role is eligible under the Skilled Worker route."},
    "salary_requirements_met": {"type": "boolean", "description": "For role_change: whether the proposed role and pay continue to meet applicable salary requirements."},
    "hybrid_only": {"type": "boolean", "description": "For work_location_change: whether work remains hybrid with the main office unchanged."},
    "new_main_office": {"type": "boolean", "description": "For work_location_change: whether the worker has a new normal main office or branch."},
    "new_client_site": {"type": "boolean", "description": "For work_location_change: whether the worker has a new normal client site."},
    "permanent_remote": {"type": "boolean", "description": "For work_location_change: whether the worker moves to permanent or full-time home working."},
    "occasional_only": {"type": "boolean", "description": "For work_location_change: whether the location change is only occasional and day-to-day."},
    "reason": {"type": "string", "description": "Reason for stopping sponsorship or the worker's departure, or the relevant organisation-change reason."},
    "change_kind": {"type": "string", "description": "For organisation_change or TUPE: the specific organisation or transfer change being assessed."},
    "duties_unchanged": {"type": "boolean", "description": "For TUPE or merger/takeover: whether the worker's duties remain unchanged."},
    "new_sponsor_has_relevant_licence": {"type": "boolean", "description": "For TUPE or merger/takeover: whether the receiving sponsor holds the relevant sponsor licence."},
    "change_type": {"type": "string", "description": "For merger_takeover: merger, takeover, or similar sponsor-organisation change type."},
    "old_entity_continues_trading": {"type": "boolean", "description": "For merger_takeover: whether the old sponsor entity continues trading after the change."},
    "new_entity_has_relevant_licence": {"type": "boolean", "description": "For merger_takeover: whether the new entity has the relevant sponsor licence."},
}

_CHANGE_SCHEMA = {
    "type": "object",
    "properties": CHANGE_PROPERTIES,
    "required": ["event_type", "route"],
    "additionalProperties": True,
}

PAID_TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "assess_change_impact": {
        "type": "object",
        "properties": {
            "payload": {
                **deepcopy(_CHANGE_SCHEMA),
                "description": "One structured Skilled Worker sponsor-change event. Supply the event-specific facts you know; missing required decision facts fail closed rather than being guessed.",
                "examples": [
                    {"event_type": "unauthorised_absence", "route": "skilled_worker", "consecutive_working_days": 11}
                ],
            }
        },
        "required": ["payload"],
        "additionalProperties": False,
        "title": "assess_change_impactArguments",
    },
    "batch_assess_changes": {
        "type": "object",
        "properties": {
            "payload": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "array",
                        "items": deepcopy(_CHANGE_SCHEMA),
                        "minItems": 1,
                        "maxItems": 25,
                        "description": "1-25 structured Skilled Worker sponsor-change events.",
                    }
                },
                "required": ["changes"],
                "additionalProperties": False,
            }
        },
        "required": ["payload"],
        "additionalProperties": False,
        "title": "batch_assess_changesArguments",
    },
}


def _tool_registry(mcp_server: Any) -> dict[str, Any]:
    manager = getattr(mcp_server, "_tool_manager", None)
    tools = getattr(manager, "_tools", None)
    if not isinstance(tools, dict):
        raise RuntimeError("MCPServer tool registry unavailable for selection metadata override")
    return tools


def apply_selection_metadata(mcp_server: Any) -> None:
    lowlevel = getattr(mcp_server, "_lowlevel_server", None)
    if lowlevel is None or not hasattr(lowlevel, "description"):
        raise RuntimeError("MCPServer low-level description unavailable for selection metadata override")
    lowlevel.description = SERVER_SELECTION_DESCRIPTION

    tools = _tool_registry(mcp_server)
    missing = sorted(set(TOOL_SELECTION_DESCRIPTIONS) - set(tools))
    if missing:
        raise RuntimeError(f"MCP tools missing before selection metadata override: {', '.join(missing)}")
    for name, description in TOOL_SELECTION_DESCRIPTIONS.items():
        tools[name].description = description
    for name, schema in PAID_TOOL_INPUT_SCHEMAS.items():
        tools[name].parameters = deepcopy(schema)
