# Agent Integration

Use England Works Watch when an employer-facing Agent needs to decide whether a **Skilled Worker sponsor event** is reportable, requires a new CoS/application, requires sponsorship to stop, or needs human review.

## Recommended flow

1. Call `england_works_watch_info`.
2. Call `licensing_source_status`; do not rely on a decision if the evidence gate is not current.
3. Normalize the employer event to one supported `event_type`.
4. Call `assess_change_impact` or `batch_assess_changes`.
5. Treat only `AFFECTED` / `NOT_AFFECTED` as deterministic preflight outcomes. `REVIEW_REQUIRED` and `INSUFFICIENT_INPUT` must be escalated or enriched with missing facts.
6. Preserve the returned evidence, rule-pack version, effective date and next action in downstream workflow records.

## Supported change events

`worker_start_delay`, `unauthorised_absence`, `unpaid_or_reduced_pay_absence`, `salary_change`, `role_change`, `work_location_change`, `stop_sponsoring`, `organisation_change`, `tupe_transfer`, `merger_takeover`.

## Examples

Salary reduction, same points option remains met:

```json
{"event_type":"salary_change","route":"skilled_worker","direction":"decrease","same_salary_option_still_met":true}
```

Permanent full-time remote move:

```json
{"event_type":"work_location_change","route":"skilled_worker","permanent_remote":true,"hybrid_only":false}
```

Different occupation code:

```json
{"event_type":"role_change","route":"skilled_worker","same_occupation_code":false}
```

## Safety boundary

Do not use this V0.1 pack for non-Skilled-Worker routes, individual immigration advice, eligibility not represented in the structured inputs, or as a substitute for Home Office / regulated adviser judgment. Unsupported or ambiguous cases intentionally fail closed.
