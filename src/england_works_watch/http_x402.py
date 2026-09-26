from __future__ import annotations

import json
import os
from typing import Any

from starlette.responses import JSONResponse

from . import server

ASSESS_PATH = "/api/v1/assess-change-impact"
BATCH_PATH = "/api/v1/batch-assess-changes"
DEFAULT_NETWORK = "eip155:8453"

ASSESS_EXAMPLE: dict[str, Any] = {
    "event_type": "unauthorised_absence",
    "route": "skilled_worker",
    "consecutive_working_days": 11,
}
BATCH_EXAMPLE: dict[str, Any] = {
    "changes": [
        {
            "event_type": "salary_change",
            "route": "skilled_worker",
            "same_salary_option_still_met": True,
        },
        {
            "event_type": "work_location_change",
            "route": "skilled_worker",
            "permanent_remote_work": True,
        },
    ]
}

ASSESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "event_type": {
            "type": "string",
            "description": "Supported Skilled Worker sponsor change event type.",
        },
        "route": {
            "type": "string",
            "description": "Sponsored-work route; current decision layer is bounded to Skilled Worker.",
        },
    },
    "required": ["event_type"],
    "additionalProperties": True,
}
BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": True},
            "minItems": 1,
            "maxItems": 25,
            "description": "One to 25 structured sponsor-change events assessed independently.",
        }
    },
    "required": ["changes"],
    "additionalProperties": False,
}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def settings() -> dict[str, str | bool]:
    return {
        "enabled": _truthy(os.getenv("EWW_PAYMENT_ENFORCED", "0")),
        "network": os.getenv("EWW_X402_NETWORK", DEFAULT_NETWORK).strip() or DEFAULT_NETWORK,
        "pay_to": os.getenv("EWW_X402_PAY_TO", "").strip(),
        "facilitator_url": os.getenv(
            "EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network"
        ).strip(),
        "http_facilitator": os.getenv(
            "EWW_HTTP_X402_FACILITATOR", "payai"
        ).strip().lower() or "payai",
        "http_facilitator_url": os.getenv(
            "EWW_HTTP_X402_FACILITATOR_URL", ""
        ).strip(),
        "assess_price": os.getenv("EWW_X402_PRICE_ASSESS", "$0.02").strip() or "$0.02",
        "batch_price": os.getenv("EWW_X402_PRICE_BATCH", "$0.05").strip() or "$0.05",
    }


def _http_facilitator_config(cfg: dict[str, str | bool]):
    """Select the paid HTTP facilitator without changing MCP settlement."""
    from x402.http import FacilitatorConfig

    mode = str(cfg.get("http_facilitator") or "payai").strip().lower()
    if mode == "cdp":
        if not os.getenv("CDP_API_KEY_ID", "").strip() or not os.getenv(
            "CDP_API_KEY_SECRET", ""
        ).strip():
            raise RuntimeError(
                "CDP_API_KEY_ID and CDP_API_KEY_SECRET are required when "
                "EWW_HTTP_X402_FACILITATOR=cdp"
            )
        try:
            from cdp.x402 import create_facilitator_config
        except ImportError as exc:
            raise RuntimeError("CDP HTTP x402 support requires cdp-sdk") from exc
        return create_facilitator_config()

    if mode in {"payai", "legacy", "url"}:
        url = str(cfg.get("http_facilitator_url") or cfg.get("facilitator_url") or "").strip()
        if not url:
            raise RuntimeError("HTTP x402 facilitator URL is required")
        return FacilitatorConfig(url=url)

    raise RuntimeError(
        "EWW_HTTP_X402_FACILITATOR must be one of: payai, url, cdp"
    )


def _amount(value: object) -> str:
    text = str(value)
    return text[1:] if text.startswith("$") else text


def paid_openapi_paths() -> dict[str, Any]:
    cfg = settings()

    def payment(amount: object) -> dict[str, Any]:
        return {
            "price": {"mode": "fixed", "currency": "USD", "amount": _amount(amount)},
            "protocols": [{"x402": {}}],
        }

    error_402 = {
        "description": (
            "Payment Required. Inspect the runtime x402 v2 PAYMENT-REQUIRED header "
            "for the authoritative chain, asset, amount and payment requirements."
        )
    }
    common = (
        "Deterministic Skilled Worker sponsor-change impact preflight using the same "
        "official-source freshness gate and decision engine as the MCP tools. "
        "Informational sponsor-compliance preflight only; not legal advice or a Home Office decision."
    )
    return {
        ASSESS_PATH: {
            "post": {
                "operationId": "england-works-watch-assess-change-impact",
                "summary": "Paid single sponsor-change impact preflight",
                "description": (
                    "Metered programmatic single-event compatibility path. " + common
                ),
                "tags": ["skilled-worker", "sponsor-compliance", "regulatory", "x402"],
                "x-payment-info": payment(cfg["assess_price"]),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": ASSESS_SCHEMA,
                            "example": ASSESS_EXAMPLE,
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Evidence-linked deterministic sponsor-change result."},
                    "402": error_402,
                    "422": {"description": "Invalid request."},
                },
            }
        },
        BATCH_PATH: {
            "post": {
                "operationId": "england-works-watch-batch-assess-changes",
                "summary": "Paid batch sponsor-change impact preflight",
                "description": (
                    "Primary paid API path for repeated work: assess one to 25 structured "
                    "sponsor changes in one request. " + common
                ),
                "tags": ["skilled-worker", "sponsor-compliance", "batch", "x402"],
                "x-payment-info": payment(cfg["batch_price"]),
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": BATCH_SCHEMA,
                            "example": BATCH_EXAMPLE,
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Evidence-linked batch sponsor-change results."},
                    "402": error_402,
                    "422": {"description": "Invalid request."},
                },
            }
        },
    }


async def openapi_http(request):
    """Overlay the two paid HTTP compatibility routes onto the existing OpenAPI."""
    response = await server.openapi(request)
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except Exception:
        payload = {
            "openapi": "3.1.0",
            "info": {
                "title": "England Works Watch",
                "version": server.SERVICE_VERSION,
                "description": server.SERVER_SELECTION_DESCRIPTION,
            },
            "paths": {},
        }
    paths = payload.setdefault("paths", {})
    if isinstance(paths, dict):
        paths.update(paid_openapi_paths())
    info = payload.setdefault("info", {})
    if isinstance(info, dict):
        info["description"] = (
            str(info.get("description") or server.SERVER_SELECTION_DESCRIPTION)
            + " The two paid HTTP compatibility routes execute the same deterministic "
              "decision engine as the MCP tools."
        )
    return JSONResponse(payload)


def _disabled_response() -> JSONResponse:
    return JSONResponse(
        {"error": "HTTP x402 compatibility surface is disabled in this environment."},
        status_code=503,
    )


@server.mcp.custom_route(ASSESS_PATH, methods=["POST"], include_in_schema=False)
async def assess_change_impact_http(request):
    if not _truthy(os.getenv("EWW_PAYMENT_ENFORCED", "0")):
        return _disabled_response()
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected a JSON object body."}, status_code=422)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "Expected a JSON object body."}, status_code=422)
    result = server._measured(
        "assess_change_impact_http",
        lambda: server._assess(dict(payload)),
        billable=True,
    )
    return JSONResponse(result)


@server.mcp.custom_route(BATCH_PATH, methods=["POST"], include_in_schema=False)
async def batch_assess_changes_http(request):
    if not _truthy(os.getenv("EWW_PAYMENT_ENFORCED", "0")):
        return _disabled_response()
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Expected a JSON object body."}, status_code=422)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "Expected a JSON object body."}, status_code=422)
    result = server._measured(
        "batch_assess_changes_http",
        lambda: server._batch(dict(payload)),
        billable=True,
    )
    return JSONResponse(result)


def wrap_http_x402(app: Any) -> Any:
    cfg = settings()
    if not cfg["enabled"]:
        return app
    if not cfg["pay_to"]:
        raise RuntimeError("EWW_X402_PAY_TO is required when HTTP x402 is enabled")

    try:
        from x402.extensions.bazaar import (
            OutputConfig,
            bazaar_resource_server_extension,
            declare_discovery_extension,
        )
        from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
        from x402.http.middleware.fastapi import PaymentMiddlewareASGI
        from x402.http.types import RouteConfig
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
        from x402.server import x402ResourceServer
    except ImportError as exc:
        raise RuntimeError("HTTP x402 support requires x402[fastapi,evm]") from exc

    network = str(cfg["network"])
    if not network.startswith("eip155:"):
        raise RuntimeError("England Works Watch HTTP x402 supports eip155:* exact payment only")

    facilitator = HTTPFacilitatorClient(_http_facilitator_config(cfg))
    resource_server = x402ResourceServer(facilitator)
    resource_server.register(network, ExactEvmServerScheme())
    resource_server.register_extension(bazaar_resource_server_extension)

    def discovery_extension(
        example: dict[str, Any],
        schema: dict[str, Any],
        output_example: dict[str, Any],
    ) -> dict[str, Any]:
        extensions = declare_discovery_extension(
            input=example,
            input_schema=schema,
            body_type="json",
            output=OutputConfig(
                example=output_example,
                schema={"type": "object", "additionalProperties": True},
            ),
        )
        bazaar = extensions.get("bazaar", {})
        info = bazaar.get("info", {}) if isinstance(bazaar, dict) else {}
        input_info = info.get("input", {}) if isinstance(info, dict) else {}
        if not isinstance(input_info, dict):
            raise RuntimeError("Bazaar HTTP discovery declaration missing input metadata")
        input_info["method"] = "POST"
        return extensions

    common = (
        "Deterministic Skilled Worker sponsor-change impact preflight with official-source "
        "freshness gates. Payment verification precedes business execution. "
        "Not legal advice or a Home Office decision."
    )
    routes = {
        f"POST {ASSESS_PATH}": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=str(cfg["pay_to"]),
                    price=str(cfg["assess_price"]),
                    network=network,
                )
            ],
            resource=f"{server.PUBLIC_ORIGIN}{ASSESS_PATH}",
            mime_type="application/json",
            description="Paid single sponsor-change impact preflight. " + common,
            extensions=discovery_extension(
                ASSESS_EXAMPLE,
                ASSESS_SCHEMA,
                {"status": "AFFECTED", "decision_code": "example"},
            ),
        ),
        f"POST {BATCH_PATH}": RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact",
                    pay_to=str(cfg["pay_to"]),
                    price=str(cfg["batch_price"]),
                    network=network,
                )
            ],
            resource=f"{server.PUBLIC_ORIGIN}{BATCH_PATH}",
            mime_type="application/json",
            description="Paid batch sponsor-change impact preflight. " + common,
            extensions=discovery_extension(
                BATCH_EXAMPLE,
                BATCH_SCHEMA,
                {"total": 2, "results": []},
            ),
        ),
    }
    from .http_x402_analytics import HttpX402TelemetryASGI

    protected = PaymentMiddlewareASGI(app, routes=routes, server=resource_server)
    return HttpX402TelemetryASGI(protected)
