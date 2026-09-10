from types import SimpleNamespace

from england_works_watch.x402_gate import _payment_state


def _result(*, structured=None, meta=None, is_error=False):
    return SimpleNamespace(
        structured_content=structured or {},
        meta=meta or {},
        is_error=is_error,
    )


def test_payment_required_is_challenge():
    result = _result(
        structured={"x402Version": 2, "accepts": [{"network": "eip155:8453"}]},
        is_error=True,
    )
    assert _payment_state(result) == "challenge"


def test_failed_settlement_takes_precedence_over_challenge_shape():
    result = _result(
        structured={
            "x402Version": 2,
            "accepts": [{"network": "eip155:8453"}],
            "x402/payment-response": {
                "success": False,
                "network": "eip155:8453",
                "transaction": "",
                "errorReason": "settlement_failed",
            },
        },
        is_error=True,
    )
    assert _payment_state(result) == "payment_error"


def test_successful_settlement_is_paid_executed():
    result = _result(
        meta={
            "x402/payment-response": {
                "success": True,
                "network": "eip155:8453",
                "transaction": "0xabc",
            }
        },
        is_error=False,
    )
    assert _payment_state(result) == "paid_executed"


def test_plain_error_is_payment_error():
    assert _payment_state(_result(is_error=True)) == "payment_error"
