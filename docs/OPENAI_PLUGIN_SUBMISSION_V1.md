# OpenAI Plugin Submission V1 — UK Sponsor Change Checker

Prepared for the OpenAI Platform **With MCP** public plugin flow.

## Submission type

- Type: **With MCP**
- MCP URL mode: **Universal**
- Authentication: **None**
- Custom UI: **None**
- Production MCP URL: `https://england-works-watch-production.up.railway.app/mcp-directory/`
- Product engine: England Works Watch deterministic Skilled Worker sponsor-change decision layer
- Commercial `/mcp` surface: out of scope for this plugin submission

## Listing details

**Plugin name**

`UK Sponsor Change Checker`

**Short description**

Check how employee or company changes affect UK Skilled Worker sponsor duties.

**Long description**

UK Sponsor Change Checker is a read-only compliance preflight for employers and advisers handling Skilled Worker sponsor duties. It evaluates defined changes such as salary, role, work location, unauthorised absence, unpaid or reduced-pay absence, delayed start, stopping sponsorship, organisation changes, TUPE transfers, mergers and takeovers. The checker returns an explicit AFFECTED, NOT_AFFECTED, REVIEW_REQUIRED, or INSUFFICIENT_INPUT state, together with official GOV.UK evidence and required next-action information where available. Unsupported routes, missing facts, conflicting inputs, or blocked/stale source evidence fail closed. The plugin is not legal advice and does not make Home Office decisions.

**Preferred category**

`Business` (use a more specific `Legal` / `Compliance` category only if the submission portal exposes one.)

**Website**

`https://england-works-watch-production.up.railway.app/uk-sponsor-change-checker`

**Support**

`https://england-works-watch-production.up.railway.app/support`

**Privacy policy**

`https://england-works-watch-production.up.railway.app/privacy`

**Terms**

`https://england-works-watch-production.up.railway.app/terms`

**Support email**

`launchcircle.server@gmail.com`

**Developer identity**

Select the verified individual or business identity in the OpenAI Platform. The selected identity must match the publisher information used in the public listing. Do not invent or substitute a legal entity name in the listing.

**Logo**

A production-ready square logo is still required in the portal. Do not submit a generic OpenAI, GOV.UK, Home Office, or lookalike government mark. The asset should identify `UK Sponsor Change Checker` / England Works Watch without implying government endorsement.

## MCP review information

### Domain verification

The production server exposes:

`https://england-works-watch-production.up.railway.app/.well-known/openai-apps-challenge`

The route fails closed with HTTP 404 until `OPENAI_APPS_CHALLENGE` is configured. When the OpenAI portal generates the verification token, set that exact token as the Railway environment variable `OPENAI_APPS_CHALLENGE`. The endpoint then returns only the token as plain text.

### Content security policy

The V1 plugin has **no custom UI** and performs no browser-side fetches. Use an empty/minimal UI CSP in the portal. Do not add unrelated fetch/resource domains.

### Authentication

None. Reviewers and users do not need an account, password, OAuth flow, MFA, SMS, or email confirmation.

### Data handling summary

- Processes only task-specific sponsor-change facts supplied to a tool call.
- Does not request full chat transcripts, precise location, contacts, passwords, payment credentials, private keys, or seed phrases.
- Application analytics do not persist the substantive sponsor-change scenario payload.
- Privacy-minimal operational telemetry can include time, tool name, outcome, latency, declared client/integration name when supplied, coarse source attribution, request/correlation ID when supplied, and deployment revision.
- Directory edition is separated from the commercial payment-enabled MCP surface.

## Tool inventory and annotation justification

| Tool | Purpose | readOnlyHint | openWorldHint | destructiveHint | Justification |
|---|---|---:|---:|---:|---|
| `sponsor_change_checker_info` | Explain scope, supported events and decision states | true | false | false | Reads bounded service metadata only; no external side effect |
| `list_supported_change_events` | List event types supported by the deterministic rule pack | true | false | false | Reads bounded local rule-pack metadata only |
| `licensing_source_status` | Return freshness/review status of service-maintained GOV.UK evidence | true | false | false | Reads the bounded source-monitoring state maintained by this service; the tool call itself does not perform open-ended web search |
| `assess_change_impact` | Compute a deterministic sponsor-change decision from supplied facts | true | false | false | Computes from bounded rule-pack and source state; no write, message, transaction, workflow or external mutation |

All four tools are also idempotent and do not expose the payment-enabled tools from the commercial MCP surface.

## Starter prompts

1. `Our Skilled Worker employee's salary is being reduced. What sponsor action might be required?`
2. `A sponsored worker has had 11 consecutive working days of unauthorised absence. Check the sponsor impact.`
3. `A sponsored worker will permanently work remotely. Do we need to report the location change?`
4. `Our sponsored employee is changing duties but staying in the same occupation code. What should we check?`
5. `A new entity is taking sponsored workers under TUPE. What sponsor-licence issues are affected?`
6. `A sponsored worker is starting 29 days late. Check whether the sponsor is affected.`
7. `We are merging companies and the old entity will stop trading. What sponsor duties should we review?`
8. `Show me which sponsor-change event types this checker supports.`

## Reviewer test cases

### Positive 1 — unauthorised absence threshold

- User prompt: `A Skilled Worker has been absent without permission for 11 consecutive working days. Do we need to report it?`
- Expected tool: `assess_change_impact`
- Reproducible payload: `{"event_type":"unauthorised_absence","route":"skilled_worker","consecutive_working_days":11}`
- Expected result: `status=AFFECTED`, `decision_code=EW-ABS-REPORT`
- Expected shape: decision state, decision code, rationale, required actions, evidence/affected rules, disclaimer
- Account/fixture requirement: none

### Positive 2 — salary reduction remains on same salary option

- User prompt: `We are reducing a Skilled Worker employee's salary, but the same salary option is still met. What is the sponsor impact?`
- Expected tool: `assess_change_impact`
- Reproducible payload: `{"event_type":"salary_change","route":"skilled_worker","direction":"decrease","same_salary_option_still_met":true}`
- Expected result: `status=AFFECTED`, `decision_code=EW-SALARY-REPORT`
- Expected shape: decision state, rationale, required actions, evidence/affected rules
- Account/fixture requirement: none

### Positive 3 — permanent remote work

- User prompt: `Our sponsored Skilled Worker is moving to permanent remote work rather than hybrid-only working. Check the reporting impact.`
- Expected tool: `assess_change_impact`
- Reproducible payload: `{"event_type":"work_location_change","route":"skilled_worker","permanent_remote":true,"hybrid_only":false}`
- Expected result: `status=AFFECTED`, `decision_code=EW-LOC-REPORT`
- Expected shape: decision state, rationale, required actions, evidence/affected rules
- Account/fixture requirement: none

### Positive 4 — delayed start

- User prompt: `A Skilled Worker will start 29 days later than planned. What sponsor action is triggered?`
- Expected tool: `assess_change_impact`
- Reproducible payload: `{"event_type":"worker_start_delay","route":"skilled_worker","delay_days":29}`
- Expected result: `status=AFFECTED`, `decision_code=EW-START-LATE`
- Expected shape: decision state, rationale, required actions, evidence/affected rules
- Account/fixture requirement: none

### Positive 5 — TUPE to licensed sponsor

- User prompt: `Sponsored workers are transferring under TUPE, their duties and occupation code are unchanged, and the new sponsor has the relevant licence. Check the sponsor impact.`
- Expected tool: `assess_change_impact`
- Reproducible payload: `{"event_type":"tupe_transfer","route":"skilled_worker","duties_unchanged":true,"same_occupation_code":true,"new_sponsor_has_relevant_licence":true}`
- Expected result: `status=AFFECTED`, `decision_code=EW-TUPE-LICENSED`
- Expected shape: decision state, rationale, required actions, evidence/affected rules
- Account/fixture requirement: none

### Negative 1 — missing salary facts

- User prompt: `Our Skilled Worker employee's salary is being reduced. Tell me the final sponsor action.`
- Scenario detail: no fact is supplied about whether the same salary option remains met or whether a revised salary meets the Skilled Worker requirements.
- Expected behavior: call `assess_change_impact` only with facts actually supplied; fail closed or ask for clarification.
- Reproducible payload: `{"event_type":"salary_change","route":"skilled_worker","direction":"decrease"}`
- Expected result: `status=INSUFFICIENT_INPUT`, `decision_code=EW-SALARY-OPTION-MISSING`
- Why it should not complete a definitive determination: a required fact is missing.

### Negative 2 — conflicting location facts

- User prompt: `This is hybrid-only working, but it is also a permanent remote-work change. Give me a definitive answer.`
- Expected behavior: do not guess which fact is correct; return safe review state.
- Reproducible payload: `{"event_type":"work_location_change","route":"skilled_worker","hybrid_only":true,"permanent_remote":true}`
- Expected result: `status=REVIEW_REQUIRED`, `decision_code=EW-LOC-CONFLICT`
- Why it should not complete a definitive determination: the supplied facts conflict.

### Negative 3 — unsupported immigration route

- User prompt: `Check a salary reduction for a Global Business Mobility worker using the same tool.`
- Expected behavior: do not silently generalise Skilled Worker rules to another route.
- Reproducible payload: `{"event_type":"salary_change","route":"global_business_mobility","direction":"decrease"}`
- Expected result: `status=REVIEW_REQUIRED`, `decision_code=EW-SCOPE-001`
- Why it should not complete a definitive determination: V1 is explicitly scoped to Skilled Worker sponsor duties.

## Availability

Initial public availability target:

- United Kingdom
- Canada
- United States
- Ireland
- Australia
- New Zealand

The regulatory subject matter remains UK Skilled Worker sponsor duties regardless of the user's location.

## Release notes

**Initial public submission.** UK Sponsor Change Checker exposes a dedicated no-auth, read-only MCP surface for deterministic Skilled Worker sponsor-change preflight. It includes four read-only tools, official-source evidence status, explicit fail-closed decision states, and no custom UI. The submitted endpoint does not expose the separate commercial x402/payment tools.

## Pre-submit evidence already completed

- Production MCP `initialize`: PASS
- Production `tools/list`: PASS
- Exactly four directory tools: PASS
- Read-only/non-destructive annotations: PASS
- Production `assess_change_impact` tool call: PASS
- Existing commercial `/mcp` x402 gate after directory deployment: PASS
- Permanent GitHub Actions directory production protocol gate: installed

## Portal-only actions that cannot be completed from source code

1. Confirm the submitting OpenAI Platform organization has **Apps Management: Write**.
2. Complete **verified developer or business identity** and select it in the submission.
3. Upload a production-ready square logo.
4. Create **With MCP** draft in the plugin submission portal.
5. Enter the Universal MCP URL and select **Scan Tools**.
6. If prompted for domain verification, copy the portal token into Railway `OPENAI_APPS_CHALLENGE`, then retry verification.
7. Enter the starter prompts and eight reviewer test cases above.
8. Select availability and complete policy attestations.
9. Submit for review only after the scanned tool metadata matches this document.
