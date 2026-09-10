from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = 8765
URL = f"http://127.0.0.1:{PORT}/mcp"
HEALTH = f"http://127.0.0.1:{PORT}/health"


def wait_health(timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(HEALTH, timeout=1) as response:
                body = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and body.get("status") == "ok":
                    return
        except Exception as exc:  # server may still be starting
            last = exc
        time.sleep(0.15)
    raise RuntimeError(f"health did not become ready: {last!r}")


def dump_model(value):
    fn = getattr(value, "model_dump", None)
    if callable(fn):
        return fn(by_alias=True, exclude_none=True)
    return value


async def smoke() -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(URL) as streams:
        read_stream, write_stream = streams[0], streams[1]
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            init_dump = dump_model(init)
            assert init_dump, "initialize returned no data"

            listed = await session.list_tools()
            tools_dump = dump_model(listed)
            tools = tools_dump.get("tools", [])
            names = [tool.get("name") for tool in tools]
            expected = [
                "england_works_watch_info",
                "licensing_source_status",
                "list_supported_change_events",
                "assess_change_impact",
                "batch_assess_changes",
            ]
            assert names == expected, f"unexpected tool list/order: {names!r}"

            assess = next(tool for tool in tools if tool.get("name") == "assess_change_impact")
            schema = assess.get("inputSchema") or assess.get("input_schema") or {}
            props = schema.get("properties") or {}
            assert "payload" in props, f"assess_change_impact schema missing payload: {schema!r}"
            assert "payload" in (schema.get("required") or []), f"payload not required: {schema!r}"

            src_result = await session.call_tool("licensing_source_status", arguments={})
            src_dump = dump_model(src_result)
            src = src_dump.get("structuredContent") or src_dump.get("structured_content")
            assert isinstance(src, dict), f"source status lacks structured content: {src_dump!r}"
            assert src.get("coverage_complete") is True, f"source gate not complete: {src!r}"
            assert src.get("blocking_sources") == [], f"blocking sources present: {src!r}"

            decision_result = await session.call_tool(
                "assess_change_impact",
                arguments={
                    "payload": {
                        "event_type": "unauthorised_absence",
                        "route": "skilled_worker",
                        "consecutive_working_days": 11,
                    }
                },
            )
            decision_dump = dump_model(decision_result)
            decision = decision_dump.get("structuredContent") or decision_dump.get("structured_content")
            assert isinstance(decision, dict), f"decision lacks structured content: {decision_dump!r}"
            assert decision.get("status") == "AFFECTED", decision
            assert decision.get("decision_code") == "EW-ABS-REPORT", decision
            evidence = decision.get("affected_rules") or []
            assert evidence and all(str(item.get("url", "")).startswith("https://www.gov.uk/") for item in evidence), decision

            print(
                json.dumps(
                    {
                        "mcp_transport_smoke": "PASS",
                        "server": init_dump.get("serverInfo") or init_dump.get("server_info"),
                        "tools": names,
                        "assess_input_schema": schema,
                        "source_gate": {
                            "coverage_complete": src.get("coverage_complete"),
                            "blocking_sources": src.get("blocking_sources"),
                            "rule_pack_version": src.get("rule_pack_version"),
                        },
                        "decision": {
                            "status": decision.get("status"),
                            "decision_code": decision.get("decision_code"),
                            "evidence_rule_ids": [x.get("rule_id") for x in evidence],
                            "official_urls": [x.get("url") for x in evidence],
                        },
                    },
                    indent=2,
                    sort_keys=True,
                )
            )


def main() -> None:
    env = os.environ.copy()
    env.update(
        {
            "HOST": "127.0.0.1",
            "PORT": str(PORT),
            "EWW_PAYMENT_ENFORCED": "0",
            "EWW_RUNTIME_DIR": "/tmp/eww-mcp-smoke",
        }
    )
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
            raise RuntimeError(f"smoke server exited unexpectedly: {process.returncode}")


if __name__ == "__main__":
    main()
