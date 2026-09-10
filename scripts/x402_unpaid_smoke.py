from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = 8766
URL = f"http://127.0.0.1:{PORT}/mcp"
HEALTH = f"http://127.0.0.1:{PORT}/health"
PAY_TO = "0xDAAef0FD525278aAD0bA11066A96c338642A3d1A"


def wait_health(timeout: float = 25.0) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH, timeout=1) as response:
                body = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and body.get("status") == "ok" and body.get("payment_enforced") is True:
                    return
        except Exception as exc:
            last = exc
        time.sleep(0.2)
    raise RuntimeError(f"paid-mode health did not become ready: {last!r}")


def dump_model(value):
    fn = getattr(value, "model_dump", None)
    if callable(fn):
        return fn(by_alias=True, exclude_none=True)
    return value


def contains_business_decision(value) -> bool:
    if isinstance(value, dict):
        forbidden = {"decision_code", "affected_rules", "required_actions", "rationale"}
        if forbidden.intersection(value):
            return True
        status = value.get("status")
        if status in {"AFFECTED", "NOT_AFFECTED", "REVIEW_REQUIRED", "INSUFFICIENT_INPUT"}:
            return True
        return any(contains_business_decision(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_business_decision(v) for v in value)
    if isinstance(value, str):
        return any(token in value for token in ("EW-ABS-REPORT", '"AFFECTED"', "SPONSOR-ABSENCE-10"))
    return False


async def smoke() -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(URL) as streams:
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # A free tool must remain callable when payment enforcement is on.
            info_result = await session.call_tool("england_works_watch_info", arguments={})
            info_dump = dump_model(info_result)
            info = info_dump.get("structuredContent") or info_dump.get("structured_content")
            assert isinstance(info, dict), info_dump
            assert info.get("payment", {}).get("enforced") is True, info
            assert info.get("payment", {}).get("network") == "eip155:8453", info

            # An unpaid decision request must terminate at the payment boundary.
            result = await session.call_tool(
                "assess_change_impact",
                arguments={
                    "payload": {
                        "event_type": "unauthorised_absence",
                        "route": "skilled_worker",
                        "consecutive_working_days": 11,
                    }
                },
            )
            dumped = dump_model(result)
            structured = dumped.get("structuredContent") or dumped.get("structured_content") or {}
            meta = dumped.get("_meta") or dumped.get("meta") or {}
            text = "\n".join(str(x.get("text", "")) for x in dumped.get("content", []) if isinstance(x, dict))
            combined = {"structured": structured, "meta": meta, "text": text, "isError": dumped.get("isError", dumped.get("is_error"))}

            # x402 MCP implementations may place challenge fields in structured content,
            # metadata, or encoded text. Accept any of those locations, but require the
            # x402 protocol marker plus Base mainnet and prohibit all business-decision data.
            encoded = json.dumps(combined, sort_keys=True)
            assert ("x402Version" in encoded or "x402" in encoded.lower()), combined
            assert ("eip155:8453" in encoded), combined
            assert (PAY_TO.lower() in encoded.lower()), combined
            assert not contains_business_decision(combined), combined

            print(json.dumps({
                "x402_unpaid_smoke": "PASS",
                "free_tool_payment_enforced": info.get("payment", {}).get("enforced"),
                "network": "eip155:8453",
                "pay_to": PAY_TO,
                "decision_leak": False,
                "challenge_shape": combined,
            }, indent=2, sort_keys=True))


def main() -> None:
    env = os.environ.copy()
    env.update({
        "HOST": "127.0.0.1",
        "PORT": str(PORT),
        "EWW_PAYMENT_ENFORCED": "1",
        "EWW_X402_NETWORK": "eip155:8453",
        "EWW_X402_PAY_TO": PAY_TO,
        "EWW_X402_FACILITATOR_URL": "https://facilitator.payai.network",
        "EWW_X402_PRICE_ASSESS": "$0.02",
        "EWW_X402_PRICE_BATCH": "$0.05",
        "EWW_RUNTIME_DIR": "/tmp/eww-x402-smoke",
    })
    process = subprocess.Popen(
        [sys.executable, "-m", "england_works_watch.server", "--http"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_health()
        asyncio.run(smoke())
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)
        if process.returncode not in (0, -15):
            print(output, file=sys.stderr)
            raise RuntimeError(f"paid smoke server exited unexpectedly: {process.returncode}")


if __name__ == "__main__":
    main()
