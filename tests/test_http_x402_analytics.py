from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from england_works_watch import analytics
from england_works_watch.http_x402 import ASSESS_PATH
from england_works_watch.http_x402_analytics import HttpX402TelemetryASGI


def _app(status: int):
    async def endpoint(_request):
        return JSONResponse({"ok": True}, status_code=status)

    return HttpX402TelemetryASGI(
        Starlette(routes=[Route(ASSESS_PATH, endpoint, methods=["POST"])])
    )


def test_http_challenge_records_canonical_business_event_and_bounded_monitor_source(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    with TestClient(_app(402)) as client:
        response = client.post(
            ASSESS_PATH,
            headers={
                "user-agent": "x402-list-monitor/1.0 (+https://x402-list.com)",
            },
        )

    assert response.status_code == 402
    window = analytics._window_summary(24)
    assert window["commercial_funnel"]["paid_challenge"]["raw"] == 1
    assert window["commercial_funnel"]["paid_executed"]["raw"] == 0
    assert window["source_attribution"]["x402_list"]["paid_challenge"] == 1


def test_http_paid_execution_records_canonical_business_event(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    with TestClient(_app(200)) as client:
        response = client.post(
            ASSESS_PATH,
            headers={
                "payment-signature": "not-stored",
                "x-eww-client": "external-agent-test",
            },
        )

    assert response.status_code == 200
    window = analytics._window_summary(24)
    assert window["commercial_funnel"]["paid_executed"]["raw"] == 1
    assert window["commercial_funnel"]["paid_executed"]["confirmed_external"] == 1
    assert window["confirmed_external_by_tool"]["paid_executed"] == {
        "assess_change_impact": 1
    }


def test_generic_node_client_remains_unresolved_machine_not_confirmed_external(tmp_path, monkeypatch):
    monkeypatch.setenv("EWW_RUNTIME_DIR", str(tmp_path))

    with TestClient(_app(402)) as client:
        response = client.post(ASSESS_PATH, headers={"user-agent": "node"})

    assert response.status_code == 402
    window = analytics._window_summary(24)
    assert window["commercial_funnel"]["paid_challenge"]["raw"] == 1
    assert window["commercial_funnel"]["paid_challenge"]["confirmed_external"] == 0
    assert window["source_attribution"]["unknown_machine"]["paid_challenge"] == 1
