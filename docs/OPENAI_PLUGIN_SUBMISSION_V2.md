# OpenAI Plugin Submission V2 — RegEvidenceHub Sponsor

Prepared: 2026-09-20

This is the current OpenAI Platform **With MCP** submission packet for the UK Skilled Worker sponsor-change product.

## Submission

- Type: **With MCP**
- MCP URL mode: **Universal**
- Authentication: **None**
- Custom UI: **None**
- Production OpenAI MCP URL: `https://works.regevidencehub.com/openai/mcp`
- Existing Grok/vendor-neutral AI connector remains at `https://works.regevidencehub.com/ai/mcp`
- Commercial MCP remains separate at `https://works.regevidencehub.com/mcp`
- Import file: `chatgpt-app-submission.json`

The OpenAI endpoint is intentionally telemetry-free so its `readOnlyHint=true` annotations exactly match OpenAI's current submission-review definition. The existing `/ai/mcp` surface retains its established operational telemetry and Grok behavior.

## App Info

- Display name: `RegEvidenceHub Sponsor`
- Subtitle: `Sponsor change checks`
- Category: `BUSINESS`
- Website: `https://regevidencehub.com/products/works.html`
- Support: `https://regevidencehub.com/support/`
- Privacy: `https://regevidencehub.com/privacy/`
- Terms: `https://regevidencehub.com/terms/`
- Support email: `launchcircle.server@gmail.com`

## Tool snapshot

Expected scan result: exactly four tools:

1. `sponsor_change_checker_info`
2. `list_supported_change_events`
3. `licensing_source_status`
4. `assess_change_impact`

Each must scan with `readOnlyHint=true`, `openWorldHint=false`, and `destructiveHint=false`.

## Starter prompts

Use no more than three:

1. `A Skilled Worker has 11 consecutive working days of unauthorised absence. Check the sponsor impact.`
2. `We are reducing a Skilled Worker salary but the same salary option is still met. What changes?`
3. `A sponsored worker is moving to permanent remote work. Check the sponsor reporting impact.`

## Domain verification

The service exposes `/.well-known/openai-apps-challenge`. When the portal issues a token, set that exact token in the existing `OPENAI_APPS_CHALLENGE` production environment variable and verify:

`https://works.regevidencehub.com/.well-known/openai-apps-challenge`

## Review boundary

The submitted endpoint is an evidence-linked, deterministic Skilled Worker sponsor-change preflight. It does not expose x402, Stripe, checkout, paid batch tools, Home Office submission, visa application services, right-to-work verification, payroll, or legal advice.

## Portal steps

1. Wait for the deployment containing `/openai/mcp` to be healthy.
2. Create a new **With MCP** plugin.
3. Upload `chatgpt-app-submission.json` on the Info step.
4. Upload the production square directory icon and composer icon.
5. Select the verified developer/business identity.
6. Enter `https://works.regevidencehub.com/openai/mcp` as the Universal MCP URL.
7. Complete domain verification if requested.
8. Scan tools and confirm the four-tool snapshot above.
9. Review imported prompts and the exact five positive plus three negative tests.
10. Set availability and policy attestations.
11. Submit for review.
