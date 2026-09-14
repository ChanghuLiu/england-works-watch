"""Offline x402 reconciliation fixture for V42.

It exercises the existing payment-state and attribution classifiers with
in-memory objects. It never calls a production MCP endpoint or payment rail.
"""
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from england_works_watch.attribution import external_classification, normalize_source_bucket

try:
    import x402.mcp  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    # The classifier only needs this public key. Keep the offline fixture
    # runnable in a dependency-light checkout; never use this shim in runtime.
    x402_package = types.ModuleType("x402")
    x402_mcp = types.ModuleType("x402.mcp")
    x402_mcp.MCP_PAYMENT_RESPONSE_META_KEY = "x402/payment-response"
    sys.modules.setdefault("x402", x402_package)
    sys.modules["x402.mcp"] = x402_mcp

from england_works_watch.x402_gate import _payment_state

LABEL = "FICTIONAL_SAMPLE — OFFLINE FIXTURE — NOT A REAL PAYMENT"


def result(*, structured: dict[str, Any] | None = None, meta: dict[str, Any] | None = None, is_error: bool = False):
    return SimpleNamespace(structured_content=structured or {}, meta=meta or {}, is_error=is_error)


def fixture() -> dict[str, Any]:
    challenge = result(structured={"x402Version": 2, "accepts": [{"network": "eip155:8453", "price": "$0.01"}]}, is_error=True)
    settled = result(meta={"x402/payment-response": {"success": True, "network": "eip155:8453", "transaction": "0xfixture"}})
    failed = result(meta={"x402/payment-response": {"success": False, "network": "eip155:8453", "errorReason": "settlement_failed"}}, is_error=True)
    owner_meta = {"englandworkswatch/actor": "owned_ci", "source_context": "direct"}
    external_meta = {"englandworkswatch/actor": "declared_external", "source_context": "direct"}
    return {
        "label": LABEL,
        "production_call_made": False,
        "real_payment_taken": False,
        "counts_as_genuine_external_paid_execution": False,
        "classifier_results": {
            "challenge": _payment_state(challenge),
            "successful_settlement": _payment_state(settled),
            "failed_settlement": _payment_state(failed),
        },
        "owner_classification": {
            "classification": external_classification(owner_meta, actor="owned_ci"),
            "owner_test_excluded": True,
        },
        "external_claim_classification": {
            "classification": external_classification(external_meta, actor="declared_external"),
            "requires_real_receipt_and_execution": True,
        },
        "reconciliation_record": {
            "product": "england-works-watch",
            "tool": "assess_change_impact",
            "payment_state": "CONFIRMED",
            "settlement_reference": "fixture-only-0xfixture",
            "execution_observed": True,
            "response_integrity": "fixture_validated",
            "source": normalize_source_bucket("direct"),
            "genuine_external": False,
            "owner_test_excluded": True,
            "failure_preserved": True,
            "dedupe_key": "fixture-only-tool-settlement-execution",
        },
        "operator_assertions": [
            "Challenge is not paid execution.",
            "Successful settlement must be linked to the same tool execution result.",
            "A failed settlement remains payment_error and never becomes success.",
            "Owner/test markers are excluded from external commercial counts.",
            "Duplicate settlement or execution keys are held for manual review.",
        ],
    }


def validate(payload: dict[str, Any]) -> None:
    assert payload["label"] == LABEL
    assert payload["production_call_made"] is False
    assert payload["real_payment_taken"] is False
    assert payload["counts_as_genuine_external_paid_execution"] is False
    assert payload["classifier_results"] == {
        "challenge": "challenge",
        "successful_settlement": "paid_executed",
        "failed_settlement": "payment_error",
    }
    assert payload["owner_classification"]["owner_test_excluded"] is True


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or validate an offline EWW x402 fixture.")
    parser.add_argument("command", choices=("fixture", "validate"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = fixture() if args.command == "fixture" else json.loads(args.input.read_text())
    validate(payload)
    output = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
