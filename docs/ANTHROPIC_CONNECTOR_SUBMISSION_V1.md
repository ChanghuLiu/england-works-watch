# Anthropic Connector Submission V1 — UK Sponsor Change Checker

Date: 2026-09-19

## Submission target

Anthropic Connectors Directory / remote MCP review.

- Connector name: **UK Sponsor Change Checker**
- Remote MCP URL: `https://england-works-watch-production.up.railway.app/mcp-directory/`
- Transport: Streamable HTTP
- Authentication: none
- Website: `https://england-works-watch-production.up.railway.app/uk-sponsor-change-checker`
- Support: `https://england-works-watch-production.up.railway.app/support`
- Privacy: `https://england-works-watch-production.up.railway.app/privacy`
- Support email: `launchcircle.server@gmail.com`

## Directory-safe boundary

This submission must use the dedicated directory MCP above, not the commercial `/mcp` surface.

The directory edition runs deterministic read-only sponsor-change assessment without requesting, initiating, or processing x402 or cryptocurrency payment.

The directory server is implemented with MCP `ToolAnnotations` using:

- `readOnlyHint=true`
- `destructiveHint=false`
- `idempotentHint=true`
- `openWorldHint=false`

It does not perform application submission, messaging, account mutation, financial transactions, or money/cryptocurrency transfer on behalf of the user.

## Tool inventory

- `sponsor_change_checker_info`
- `list_supported_change_events`
- `licensing_source_status`
- `assess_change_impact`

All tools are intended to be narrow, bounded, read-only and idempotent.

## Example use cases for review

1. `Our Skilled Worker employee's salary is being reduced. What sponsor action might be required?`
2. `A sponsored worker has had 11 consecutive working days of unauthorised absence. Check the sponsor impact.`
3. `A new entity is taking sponsored workers under TUPE. What sponsor-licence issues are affected?`

## Safety / data handling

- Do not request passwords, payment credentials, private keys, seed phrases, or unrelated personal data.
- Do not ask users to provide full case files when bounded structured facts are sufficient.
- Results are informational preflight/navigation, not regulator approval or legal advice.
- Unsupported, missing, stale, conflicting, or out-of-scope facts must not be guessed.
- The connector does not transfer funds or crypto assets.

## Review verification checklist

Before submission, verify against production:

1. MCP initialize succeeds.
2. `tools/list` exposes only the directory-safe tool inventory above.
3. Tool annotations remain read-only / non-destructive.
4. Each example prompt selects the expected tool.
5. Unsupported requests fail safely rather than fabricating a regulatory answer.
6. No x402/payment challenge is exposed on this directory endpoint.
7. Support/privacy pages are publicly reachable.
8. The submitter can demonstrate ownership/control of the endpoint.

## Human-only submission steps

1. Sign in to the Anthropic submission/review form with the publisher account.
2. Enter the connector name, MCP URL, support/privacy/product details and example prompts.
3. Provide any reviewer contact/test information requested by the form.
4. Complete policy attestations.
5. Submit for review.

Do not claim public Claude Directory listing until Anthropic accepts the submission.
