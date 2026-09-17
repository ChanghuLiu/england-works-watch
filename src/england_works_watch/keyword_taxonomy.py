"""Controlled sponsor-compliance discovery taxonomy for C5."""
from __future__ import annotations

import re
from typing import Iterable

TAXONOMY_VERSION = "c5-v1.0.0"

KEYWORD_TAXONOMY: dict[str, tuple[str, ...]] = {
    "sponsor_compliance_scope": (
        "Skilled Worker sponsor duties", "sponsor compliance monitoring", "sponsor licence compliance",
        "UKVI sponsor compliance", "sponsor compliance change assessment", "sponsor compliance API",
    ),
    "reportable_worker_changes": (
        "reportable worker changes", "worker start delay", "unauthorised absence", "unpaid absence sponsor reporting",
        "salary change sponsor duties", "role change occupation code", "work location change sponsor duties",
        "stopping sponsorship", "worker departure sponsor reporting",
    ),
    "sponsor_organisation_events": (
        "TUPE sponsor duties", "merger takeover sponsor compliance", "sponsor organisation changes",
        "sponsor licence merger reporting", "sponsor compliance ownership change",
    ),
    "evidence_and_monitoring": (
        "Home Office sponsor guidance change monitoring", "sponsor guidance source freshness", "GOV.UK sponsor evidence",
        "sponsor compliance changed since checkpoint", "sponsor compliance review required", "stale sponsor compliance decision",
    ),
    "professional_agent_workflows": (
        "HR People Ops sponsor compliance", "HRIS sponsor compliance workflow", "payroll sponsor change workflow",
        "recruitment sponsor compliance workflow", "immigration compliance consultant workflow", "batch sponsor compliance assessment",
        "sponsor compliance monitoring report", "sponsor compliance MCP",
    ),
}

LONG_TAIL_RULES: tuple[dict[str, str], ...] = (
    {"id": "event-monitoring", "template": "{event} sponsor compliance change monitoring", "capability": "existing supported event category"},
    {"id": "source-checkpoint", "template": "{source} sponsor guidance changed since checkpoint", "capability": "official source fingerprint checkpoint"},
    {"id": "workflow-report", "template": "{workflow} sponsor compliance monitoring report", "capability": "bounded human monitoring/report entry"},
    {"id": "batch-assessment", "template": "batch {event} sponsor compliance assessment", "capability": "existing batch decision tool"},
)


def taxonomy_terms() -> tuple[str, ...]:
    return tuple(dict.fromkeys(term.strip() for values in KEYWORD_TAXONOMY.values() for term in values if term.strip()))


def generate_supported_long_tail(values: Iterable[dict[str, str]]) -> tuple[str, ...]:
    generated: list[str] = []
    for value in values:
        for rule in LONG_TAIL_RULES:
            fields = re.findall(r"{([^}]+)}", rule["template"])
            if all(key in value and isinstance(value[key], str) and value[key].strip() for key in fields):
                generated.append(rule["template"].format(**value))
    return tuple(generated)
