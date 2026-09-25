# Sponsor Offer V3 Conversion Experiment

Started: 2026-09-25

## Production release

- Runtime commit: `317307dd28655837bc7544ef086681cf16fc5eb9`
- Railway deployment: `bd7c669a-3cdb-4598-91fe-c6b975d8a79c`
- Production container started: `2026-09-25T14:21:58Z`
- Clean experiment cohort starts: `2026-09-25T14:23:05Z`
- Production page: `https://works.regevidencehub.com/monitoring-report`
- Price remains: **£49**
- Access remains: **30 days**
- Default monitored evidence remains: **4 core GOV.UK sponsor sources**

The clean cohort starts after production smoke. One operator verification request immediately after deployment created a direct/unknown landing and is intentionally outside the V3 cohort.

## Why V3 exists

The prior offer emphasized the implementation artifact — a four-source guidance baseline. The conversion hypothesis is that buyers care more about the business outcome:

> Before a sponsor change, confirm that the Home Office guidance relied on is still current and retain a dated evidence checkpoint.

V3 therefore leads with sponsor decisions and the evidence outcome rather than source-monitoring terminology.

## V3 primary positioning

Headline:

> Before a sponsor change, check that the Home Office guidance you rely on is still current

Primary paid offer:

> 30-day Sponsor Decision Evidence Check

Primary CTA:

> Create sponsor decision evidence checkpoint — £49

Representative use cases remain bounded to supported sponsor-change workflows such as salary, role, work-location, long absence, delayed start, stopping sponsorship, TUPE, merger and takeover.

## What did not change

- no price change
- no Stripe change
- no x402 change
- no regulatory rule change
- no monitored-source scope expansion
- no legal-advice claim
- no alerting claim
- no worker PII requirement

## Release gates

Production build passed:

- pytest: **75 passed**
- acceptance fixtures: **25/25**
- effective tool-selection benchmark: **25/25**
- MCP transport smoke: **PASS**
- x402 unpaid/non-leak smoke: **PASS**
- production health: **ready**
- production sources: **4/4 ready**
- payment state: **ready**

## Clean cohort baseline

At `2026-09-25T14:23:05Z`, all measured human/business source channels begin at:

| Stage | Included |
|---|---:|
| Landing | 0 |
| Qualified commercial intent | 0 |
| Checkout requested | 0 |
| Payment succeeded | 0 |

Channels tracked: direct, RegEvidenceHub, LinkedIn, OpenAI, Claude, Grok, organic, directory, unknown.

Owner/test, synthetic and automated-external traffic remain excluded. Unknown traffic is raw evidence only and is not a confirmed customer.

## Decision rules

1. **Any confirmed external payment**: P0 succeeds. Preserve the acquisition path and investigate repeatability before changing the offer.
2. **Confirmed external paid intent / checkout but no payment**: inspect checkout/payment friction before price.
3. **15 clean included V3 landings with 0 qualified intent**: V3 value proposition has not converted enough; revise the offer itself before changing price.
4. **Qualified intent appears before 15 landings**: do not change copy; allow the funnel to progress and inspect checkout/payment stages.
5. **Material confirmed external free-tool activity without paid intent**: prioritize mapping the free-use case to the paid evidence-check outcome.
6. Do not self-pay, run synthetic purchase traffic, or classify unattributed activity as customer demand.

## Current commercial objective

Move the first real external buyer through:

`landing -> qualified commercial intent -> checkout -> payment -> entitlement -> fulfilled evidence check`

The experiment is not complete merely because the page receives discovery traffic.
