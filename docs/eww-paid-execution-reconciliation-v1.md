# England Works Watch — First x402 Paid Execution Reconciliation V1

Internal runbook. The included fixture is
`FICTIONAL_SAMPLE — OFFLINE FIXTURE — NOT A REAL PAYMENT`. It does not call
production, sign a transaction, contact a buyer, or count as external revenue.

## Existing implementation

- `src/england_works_watch/x402_gate.py::_payment_state(result)` distinguishes
  `challenge`, `paid_executed`, and `payment_error`; a payment response takes
  precedence over a challenge-shaped payload.
- `src/england_works_watch/x402_gate.py::invoke(...)` classifies the result and
  records the payment state through `analytics.record`.
- `src/england_works_watch/analytics.py::record(...)` stores bounded event,
  source, actor, owner-test, and deployment-revision fields.
- `src/england_works_watch/analytics.py::summary()` exposes paid funnel and
  attribution summaries without raw payment credentials or fingerprints.
- `src/england_works_watch/attribution.py::external_classification(...)` keeps
  owner/test calls out of confirmed external counts.

## Reconciliation procedure

1. Capture the tool name, request correlation, result, and x402 metadata without
   retaining raw signatures, credentials, IPs, or full user agents.
2. Classify a response with `_payment_state`.
3. Treat an x402 challenge as `paid_challenge`, never as paid execution.
4. Require a successful settlement response and a successful non-error tool
   result for `paid_executed`.
5. Link the settlement reference to the same tool invocation. A missing,
   conflicting, or reused reference is `payment_error`/manual review.
6. Apply existing actor/client/source attribution. Owner markers, owned clients,
   test modes, and CI are `owner_test` and excluded.
7. Preserve failed settlement, execution, and mismatch records; never upgrade
   them to success.
8. Deduplicate on the bounded combination of provider settlement reference,
   tool, request correlation, and execution receipt. Duplicate payments are
   held for manual review and are not executed twice.
9. Count a genuine external paid execution only when the actor is not owner/test,
   settlement is successful, the same invocation completed successfully, and
   the receipt/reference is preserved.

## Failure matrix

| Situation | Classification |
|---|---|
| Payment challenge only | `challenge`; no paid execution. |
| Successful settlement and successful same-call result | `paid_executed`; eligible for external classification only after attribution checks. |
| Settlement failure | `payment_error`; preserve error reason and reference. |
| Tool error after settlement | mismatch/manual review; never claim successful business execution. |
| Owner/test marker or owned client | `owner_test`; exclude from genuine external count. |
| Ambiguous actor/source | `unknown`; do not upgrade. |
| Duplicate execution/payment | hold and link to original; do not re-execute. |

## Offline fixture

```bash
python3 scripts/v42_paid_execution_fixture.py fixture --output /tmp/eww-v42-fixture.json
python3 scripts/v42_paid_execution_fixture.py validate --input /tmp/eww-v42-fixture.json
```

The fixture verifies the existing classifier outputs `challenge`,
`paid_executed`, and `payment_error` for representative in-memory objects. It
explicitly sets `counts_as_genuine_external_paid_execution=false`.

## Readiness

`READY_FOR_FIRST_X402_PAID_EXECUTION`. The reconciliation path is implemented
and testable. The confirmed external paid-execution count remains zero until a
real buyer completes a real x402 flow.
