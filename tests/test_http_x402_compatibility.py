from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from england_works_watch.http_x402 import (
    ASSESS_EXAMPLE,
    ASSESS_PATH,
    BATCH_PATH,
    paid_openapi_paths,
    wrap_http_x402,
)


PAY_TO = "0xDAAef0FD525278aAD0bA11066A96c338642A3d1A"


def test_paid_openapi_paths_declare_x402_and_prices(monkeypatch):
    monkeypatch.setenv("EWW_X402_PRICE_ASSESS", "$0.02")
    monkeypatch.setenv("EWW_X402_PRICE_BATCH", "$0.05")

    paths = paid_openapi_paths()

    assert paths[ASSESS_PATH]["post"]["x-payment-info"]["price"]["amount"] == "0.02"
    assert paths[BATCH_PATH]["post"]["x-payment-info"]["price"]["amount"] == "0.05"
    assert paths[ASSESS_PATH]["post"]["x-payment-info"]["protocols"] == [{"x402": {}}]
    assert "402" in paths[ASSESS_PATH]["post"]["responses"]


def test_unpaid_http_compatibility_route_stops_at_x402(monkeypatch):
    monkeypatch.setenv("EWW_PAYMENT_ENFORCED", "1")
    monkeypatch.setenv("EWW_X402_PAY_TO", PAY_TO)
    monkeypatch.setenv("EWW_X402_NETWORK", "eip155:8453")
    monkeypatch.setenv("EWW_X402_FACILITATOR_URL", "https://facilitator.payai.network")

    executed = {"value": False}

    async def endpoint(_request):
        executed["value"] = True
        return JSONResponse({"unexpected": True})

    app = Starlette(routes=[Route(ASSESS_PATH, endpoint, methods=["POST"])])
    wrapped = wrap_http_x402(app)

    with TestClient(wrapped) as client:
        response = client.post(ASSESS_PATH, json=ASSESS_EXAMPLE)

    assert response.status_code == 402
    assert executed["value"] is False
    assert response.headers.get("payment-required")
