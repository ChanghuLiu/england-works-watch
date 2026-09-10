"""Run exactly one real x402 payment against England Works Watch.

Security and scope:
- The buyer private key may be supplied in EVM_PRIVATE_KEY or entered at the
  local hidden terminal prompt. It is never sent to the MCP server.
- Never commit, paste, upload, or send the private key to the server/chat.
- The payer must hold native Base mainnet USDC. PayAI submits the EIP-3009
  authorization on-chain and sponsors the settlement network gas.
- This script performs exactly one paid tool call and has no retry loop.
- It refuses to pay unless server identity, network, amount, asset, and pay-to
  all match the expected production values.
- A previously successful local or repository receipt blocks another payment.

This is an owner validation smoke, not evidence of external customer demand.
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
from pathlib import Path
from typing import Any

from eth_account import Account
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from x402 import x402ClientSync
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from x402.mcp import MCPToolResult, x402MCPClient

URL = os.getenv(
    "EWW_PAID_MCP_URL",
    "https://england-works-watch-production.up.railway.app/mcp",
)
EXPECTED_SERVER = "England Works Watch"
EXPECTED_PAY_TO = os.getenv(
    "EWW_EXPECTED_PAY_TO",
    "0xDAAef0FD525278aAD0bA11066A96c338642A3d1A",
)
EXPECTED_NETWORK = "eip155:8453"
EXPECTED_AMOUNT = "20000"
EXPECTED_ASSET = os.getenv(
    "EWW_EXPECTED_ASSET",
    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
)
TOOL = "assess_change_impact"
ARGS = {
    "payload": {
        "event_type": "unauthorised_absence",
        "route": "skilled_worker",
        "consecutive_working_days": 11,
    }
}


class MCPClientAdapter:
    def __init__(self, session: ClientSession):
        self._session = session

    async def connect(self, transport: Any) -> None:
        pass

    async def close(self) -> None:
        pass

    async def list_tools(self) -> Any:
        return await self._session.list_tools()

    async def call_tool(self, params: dict[str, Any], **kwargs: Any) -> MCPToolResult:
        # Preserve x402 payment metadata while also declaring this as owner CI so
        # commercial analytics can never mistake an owner smoke for external demand.
        request_meta = dict(params.get("_meta") or {})
        request_meta.setdefault("englandworkswatch/actor", "owned_ci")
        request_meta.setdefault(
            "io.modelcontextprotocol/clientInfo",
            {"name": "local-owner-paid-smoke"},
        )
        result = await self._session.call_tool(
            name=params.get("name", ""),
            arguments=params.get("arguments", {}) or {},
            meta=request_meta,
        )
        content: list[dict[str, Any]] = []
        for item in result.content:
            if hasattr(item, "text"):
                content.append({"type": "text", "text": item.text})
            else:
                content.append(
                    {
                        "type": getattr(item, "type", "text"),
                        "text": str(item),
                    }
                )

        # MCP CallToolResult carries wire metadata under _meta. Some SDK models
        # expose an alias/property named meta, so support both. The old adapter
        # read only result.meta and dropped x402/payment-response after a valid
        # settlement, causing the local smoke to falsely report a missing receipt.
        raw_meta = getattr(result, "_meta", None)
        if raw_meta is None:
            raw_meta = getattr(result, "meta", None)
        meta = (
            raw_meta.model_dump(by_alias=True, exclude_none=True)
            if hasattr(raw_meta, "model_dump")
            else dict(raw_meta or {})
        )
        structured = getattr(result, "structured_content", None)
        if structured is None:
            structured = getattr(result, "structuredContent", None)
        return MCPToolResult(
            content=content,
            is_error=getattr(result, "is_error", getattr(result, "isError", False)),
            meta=meta,
            structured_content=structured,
        )


def _same_address(left: Any, right: str) -> bool:
    return str(left or "").lower() == right.lower()


def _receipt_path() -> Path:
    configured = os.getenv("EWW_PAID_SMOKE_RECEIPT_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.cwd() / "paid-smoke-receipt.json"


def _repo_receipt_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".github" / "ops" / "england-works-watch-paid-smoke.json"


def _successful_receipt(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(payload.get("settlement_success")) and bool(payload.get("transaction"))


def _block_if_successful_receipt_exists() -> None:
    for path in (_receipt_path(), _repo_receipt_path()):
        if _successful_receipt(path):
            raise SystemExit(
                f"Existing successful paid-smoke receipt found at {path}; refusing a second payment."
            )


def _write_receipt(payload: dict[str, Any]) -> None:
    path = _receipt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"receipt_path={path}")


def _safe_failure_diagnostics(result: Any) -> None:
    """Print server response diagnostics without echoing payment payload/signature."""
    raw = getattr(result, "raw_result", None)
    structured = getattr(raw, "structured_content", None)
    if structured is None:
        structured = getattr(raw, "structuredContent", None)
    if isinstance(structured, dict):
        safe = dict(structured)
        safe.pop("x402/payment", None)
        print("server_structured_error=" + json.dumps(safe, sort_keys=True))
    content = getattr(result, "content", None) or []
    texts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
    if texts:
        print("server_error_text=" + " | ".join(texts))


def _load_buyer_key() -> str:
    key = os.getenv("EVM_PRIVATE_KEY", "").strip()
    if key:
        return key
    key = getpass.getpass("Base mainnet buyer private key (hidden): ").strip()
    if not key:
        raise SystemExit("No buyer private key supplied")
    return key


async def main() -> None:
    _block_if_successful_receipt_exists()
    key = _load_buyer_key()

    account = Account.from_key(key)
    print(f"payer={account.address}")
    print(f"paid_mcp_url={URL}")
    print("max_expected_payment=$0.02 Base mainnet USDC")
    print(f"expected_network={EXPECTED_NETWORK}")
    print(f"expected_asset={EXPECTED_ASSET}")
    print(f"expected_pay_to={EXPECTED_PAY_TO}")

    payment_client = x402ClientSync()
    register_exact_evm_client(payment_client, EthAccountSigner(account))

    async with streamable_http_client(URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            if init.server_info.name != EXPECTED_SERVER:
                raise SystemExit(f"Unexpected server: {init.server_info.name}")
            print(f"server={init.server_info.name}")

            def approve(payment_context: Any) -> bool:
                accepts = payment_context.payment_required.accepts
                if len(accepts) != 1:
                    raise RuntimeError(f"Expected exactly one payment option, got {len(accepts)}")
                option = accepts[0]
                print(
                    "payment_required="
                    f"amount={option.amount} asset={option.asset} network={option.network} "
                    f"pay_to={option.pay_to}"
                )
                if str(option.network) != EXPECTED_NETWORK:
                    raise RuntimeError(f"Unexpected network: {option.network}")
                if str(option.amount) != EXPECTED_AMOUNT:
                    raise RuntimeError(f"Unexpected amount: {option.amount}")
                if not _same_address(option.asset, EXPECTED_ASSET):
                    raise RuntimeError(f"Unexpected asset: {option.asset}")
                if not _same_address(option.pay_to, EXPECTED_PAY_TO):
                    raise RuntimeError(f"Unexpected payee: {option.pay_to}")
                print("payment_approved=true")
                return True

            paid_client = x402MCPClient(
                MCPClientAdapter(session),
                payment_client,
                auto_payment=True,
                on_payment_requested=approve,
            )
            result = await paid_client.call_tool(TOOL, ARGS)
            print(f"payment_made={result.payment_made}")
            print(f"is_error={result.is_error}")

            text = "\n".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in result.content
            )
            receipt = result.payment_response
            if not receipt:
                _safe_failure_diagnostics(result)
                raise SystemExit("Settlement receipt missing")

            print(f"settlement_success={receipt.success}")
            print(f"settlement_network={receipt.network}")
            print(f"settlement_transaction={receipt.transaction}")

            if result.is_error or not result.payment_made:
                _safe_failure_diagnostics(result)
                raise SystemExit("Paid MCP call did not complete successfully")
            if not receipt.success:
                _safe_failure_diagnostics(result)
                raise SystemExit("x402 settlement did not succeed")
            if str(receipt.network) != EXPECTED_NETWORK:
                raise SystemExit("Unexpected settlement network")
            if not receipt.transaction:
                raise SystemExit("Settlement transaction id missing")
            if "AFFECTED" not in text:
                raise SystemExit("Expected AFFECTED decision missing")
            if "EW-ABS-REPORT" not in text:
                raise SystemExit("Expected EW-ABS-REPORT decision code missing")

            receipt_payload = {
                "service": "England Works Watch",
                "tool": TOOL,
                "validation_class": "owned_mainnet_smoke",
                "payer": account.address,
                "network": str(receipt.network),
                "asset": EXPECTED_ASSET,
                "amount_atomic": EXPECTED_AMOUNT,
                "amount_usdc": "0.02",
                "pay_to": EXPECTED_PAY_TO,
                "transaction": str(receipt.transaction),
                "settlement_success": bool(receipt.success),
                "decision_marker": "AFFECTED",
                "decision_code": "EW-ABS-REPORT",
            }
            _write_receipt(receipt_payload)
            print("ENGLAND_WORKS_WATCH_X402_REAL_PAID_BUYER_SMOKE=PASS")


if __name__ == "__main__":
    asyncio.run(main())
