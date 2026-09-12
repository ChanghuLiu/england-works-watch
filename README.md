# England Works Watch

**UK sponsor compliance/change intelligence** for AI agents and employer workflows.

This product converts current UK Home Office sponsor guidance into deterministic, evidence-linked change-impact decisions for **Skilled Worker sponsors**. It is designed for employer HR/People Ops agents, HRIS/payroll/recruitment workflows, sponsor-compliance tooling, and regulated adviser tooling. It is not an individual visa-advice chatbot.

## Decision contract

Every supported change returns exactly one of:

- `AFFECTED`
- `NOT_AFFECTED`
- `REVIEW_REQUIRED`
- `INSUFFICIENT_INPUT`

Every substantive decision includes rule-pack version, effective date, rationale, official GOV.UK evidence, source version, source locator, and required next action where applicable. Missing critical facts, unsupported routes, contradictory inputs, or non-current source evidence fail closed.

## V0.1 scope

Supported events: worker start delay; unauthorised absence; unpaid/reduced-pay absence; salary change; role/occupation change; normal work-location change; stopping sponsorship; sponsor organisation changes; TUPE transfer; merger/takeover.

Route scope is deliberately limited to **Skilled Worker + sponsor duties**.

## Validation gate

- 10 independent change-impact cases
- 6 negative controls
- 5 sponsor-event cases
- 4 explicit fail-closed cases
- 25 / 25 current fixture decisions passing

## MCP tools

Free: `england_works_watch_info`, `licensing_source_status`, `list_supported_change_events`.

Decision: `assess_change_impact`, `batch_assess_changes` (up to 25 events).

Production transport is stateless Streamable HTTP at `/mcp`.

## x402

Base mainnet `eip155:8453`, USDC, exact scheme, PayAI facilitator. `assess_change_impact` is `$0.02`; `batch_assess_changes` is `$0.05`. Payment is controlled by `EWW_PAYMENT_ENFORCED`; when enabled `EWW_X402_PAY_TO` is mandatory.

The free tools provide scope, supported-event vocabulary and official-source status. Paid tools add a deterministic change decision, evidence-linked rationale, required action/deadline fields, and explicit `REVIEW_REQUIRED` or `INSUFFICIENT_INPUT` states. At the x402 boundary, call the paid tool to receive `PaymentRequired`, sign the accepted Base-USDC authorization buyer-side, then retry the same tool call with payment metadata. The decision is not executed until payment is verified. The public `england_works_watch_info` tool includes a synthetic example result shape. Never send private keys or seed phrases.

## Public discovery

`/health`, `/mcp`, `/openapi.json`, `/llms.txt`, `/.well-known/x402`, `/.well-known/mcp/server-card.json`, `/analytics/summary`.

## Architecture

`Agent structured facts -> MCP/x402 boundary -> source lifecycle gate -> deterministic rule engine -> evidence-linked result -> privacy-minimal analytics`

There is no server-side LLM in the decision path.

## Safety

Evidence-first sponsor compliance preflight only. Not legal advice, a Home Office decision, or a guarantee of compliance. `REVIEW_REQUIRED` and `INSUFFICIENT_INPUT` must never be presented downstream as clearance.
