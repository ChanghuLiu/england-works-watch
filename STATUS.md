# England Works Watch — Status

Updated: 2026-09-08

Public description: **UK sponsor compliance/change intelligence**. The earlier Railway roadworks prototype is legacy and is not the current product direction.

## Current maturity

England Works Watch V0.1 is live on Railway as a **Skilled Worker sponsor-duty change-impact preflight** with deterministic decisions, official-source lifecycle gating, x402 payment enforcement, public agent discovery, MCP Registry publication, and persistent privacy-minimal funnel analytics.

The owner-controlled Base-mainnet payment gate is now complete. The product has moved into **external conversion validation**: first PayAI Bazaar indexing, then first non-owner paid execution.

## Completed product and release gates

- Skilled Worker + sponsor duties only
- 10 supported sponsor event types
- four-state fail-closed decision contract: `AFFECTED`, `NOT_AFFECTED`, `REVIEW_REQUIRED`, `INSUFFICIENT_INPUT`
- official GOV.UK evidence, source version/effective date and required next action per substantive decision
- persistent runtime source fingerprints and fail-closed source lifecycle gate
- 14 automated tests passing in the Railway release build
- 25 / 25 acceptance fixtures passing
- agent tool-selection benchmark release gate: baseline 14 / 25 (56%) -> effective 25 / 25 (100%)
- MCP 2.x Streamable HTTP transport smoke PASS
- x402 unpaid/non-leak release smoke PASS
- real owner Base-mainnet x402 settlement PASS
- production analytics recorded `paid_executed=1`

## Production state

- Railway production: `https://england-works-watch-production.up.railway.app`
- MCP endpoint: `https://england-works-watch-production.up.railway.app/mcp`
- production health: ready
- payment enforcement: enabled
- network: Base mainnet `eip155:8453`
- asset: native Base USDC
- seller wallet: `0xDAAef0FD525278aAD0bA11066A96c338642A3d1A`
- facilitator: `https://facilitator.payai.network`
- `assess_change_impact`: `$0.02`
- `batch_assess_changes`: `$0.05`
- persistent SQLite analytics on Railway volume `/data`

## Owner mainnet settlement evidence

A real owner-controlled payment completed on 2026-09-08T23:36:59Z.

- validation class: `owned_mainnet_smoke`
- tool: `assess_change_impact`
- amount: `$0.02` USDC
- network: `eip155:8453`
- transaction: `0x4823f8e8f4b55e005927de00e44509a890a451310ba05b2caff3b31d9c18e7ae`
- PayAI `/verify`: HTTP 200
- protected business execution: PASS (`AFFECTED`, `EW-ABS-REPORT`)
- PayAI `/settle`: HTTP 200
- settlement: success

This event is infrastructure validation only. It must **not** be counted as external customer demand.

## MCP Registry

Official MCP Registry listing is live:

- name: `io.github.ChanghuLiu/england-works-watch`
- version: `0.1.0`
- registry verification: `MCP_REGISTRY_LISTING=PASS`

## PayAI Bazaar

Post-settlement full-catalog scan result:

- PayAI catalog scanned: `28,323 / 28,323`
- England Works Watch matches: `0`
- current state: `INDEXING_PENDING`

The x402 Foundation MCP guide states that Bazaar-capable facilitators can index paid MCP tools from Bazaar metadata carried through a paid settlement. Our public unpaid challenge exposes the Bazaar extension and passes the public Bazaar metadata gate, so the next gate is to observe PayAI indexing rather than make another owner payment.

## Current conversion baseline

Production analytics immediately after the owner settlement:

- total events: `136`
- paid challenges: `58`
- paid executions: `1`
- known owner paid executions: `1`
- confirmed external paid executions: `0`

Known owner baseline event: `2026-09-08T23:36:59Z`. Any later `paid_executed` event must be investigated separately before being classified as external demand.

## Active next stage — External Conversion Validation

The active funnel is:

`PayAI/MCP discovery -> free inspection -> paid tool -> x402 challenge -> external settlement -> paid execution`

Hard success signals, in order:

1. England Works Watch appears in PayAI Bazaar.
2. A new non-owner Agent reaches the paid challenge.
3. A new non-owner settlement succeeds.
4. Production analytics records a second `paid_executed` event that is defensibly external.

Until one of these changes, do not add product scope, lower the `$0.02` price, or perform another owner payment. Maintain production/source freshness and observe conversion.
