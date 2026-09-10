# England Works Watch — Conversion Audit

Date: 2026-09-08

## Scope correction

The live England Works Watch service is the UK Skilled Worker sponsor-compliance / change-impact product. The legacy UK Premises Licence Railway service is dormant and has no active deployment. This audit therefore follows the live England Works Watch funnel rather than attributing its traffic to Premises Licence.

## Live production state

- Production MCP: `https://england-works-watch-production.up.railway.app/mcp`
- Payment: x402 v2, Base mainnet USDC
- Single assessment: `$0.02`
- Batch assessment: `$0.05`
- Payment enforcement: enabled
- MCP Registry: live
- Public Bazaar metadata gate: PASS
- PayAI Bazaar listing: pending first successful real settlement

## Funnel instrumentation added during conversion work

Analytics now separates:

- actor class (`owned_ci`, `declared_external`, `unattributed`)
- tool by actor
- outcome by actor
- business-tool calls by actor
- paid funnel by actor
- sanitized declared client name
- paid funnel by declared client
- timestamped unattributed paid-tool events

This prevents owner CI and scanners from being mistaken for commercial demand.

## Current measured funnel

Latest conversion snapshot during this audit:

- total tool events: `115`
- owned CI: `80`
- unattributed: `35`
- business-tool calls: `42`
  - owned CI: `37`
  - unattributed: `5`
- payment challenges: `42`
  - owned CI: `37`
  - unattributed: `5`
- confirmed `paid_executed`: `0`

The five unattributed paid challenges decompose as follows:

1. Two challenge events correlate with a liveness-only scanner session and are not commercial intent.
2. One challenge event is the repository's own GitHub smoke client but lacked the actor marker in that run.
3. Two challenge events at `2026-09-08T17:12:11Z` and `2026-09-08T17:12:12Z` came from an otherwise-unidentified HTTP client. This is the only plausible external paid-intent episode in the current data. Both stopped at the x402 challenge; neither settled.

## Conversion diagnosis

Current evidence does **not** support a price cut or more product functionality.

The dominant issue is traffic quality / buyer payment compatibility:

- external discovery is real;
- many visitors are registries, graders, scanners, crawlers, or research agents;
- the x402 challenge is being generated correctly;
- there is no confirmed external settlement;
- the only plausible external paid-intent session reached the challenge and stopped.

At `$0.02`, there is not enough evidence to classify price as the problem. The next useful distribution step is to make the service visible to x402-capable buyers, for which the PayAI Bazaar listing is especially relevant.

## Hard next gate

Run exactly one **owner-controlled** real Base-mainnet `$0.02` settlement using `england-works-watch/scripts/paid_mcp_buyer_smoke.py` from a local machine holding the buyer key. The key must never be placed in GitHub, Railway, logs, or chat.

A successful owner smoke is infrastructure validation only, not external demand. After it succeeds:

1. confirm `paid_executed` in persistent analytics;
2. re-probe PayAI Bazaar;
3. verify the England Works Watch listing becomes discoverable;
4. resume commercial observation with the hard success metric: a non-owner, non-probe `paid_executed` event.

## Commercial success metric

Do not call the product commercially validated until there is at least one attributable or defensibly external paid execution. Discovery, liveness probes, tool listing, and unpaid x402 challenges are not payment evidence.
