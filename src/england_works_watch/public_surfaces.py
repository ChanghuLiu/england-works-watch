"""Public policy/distribution copy for the sponsor-compliance product."""
from __future__ import annotations

from html import escape

from .keyword_taxonomy import TAXONOMY_VERSION, taxonomy_terms

PUBLIC_PATHS = {"pricing": "/pricing", "privacy": "/privacy", "terms": "/terms", "support": "/support"}
POLICY_OWNER_REVIEW_NOTE = "Draft public copy requires owner/legal review before external publication, including operator identity, refunds, governing law, retention and support commitments."


def public_links(origin: str) -> dict[str, str]:
    return {name: origin.rstrip("/") + path for name, path in PUBLIC_PATHS.items()}


def policy_copy(kind: str, *, origin: str) -> tuple[str, str, tuple[tuple[str, tuple[str, ...]], ...]]:
    common = (("Product boundary", (
        "England Works Watch provides evidence-first UK Skilled Worker sponsor-compliance and change-impact intelligence for employers, HR/People Ops workflows, structured HRIS/payroll/recruitment workflows, and regulated advisers.",
        "It is not immigration legal advice, a Home Office decision, an immigration application service, employee surveillance, or a guarantee of compliance.",
    )), ("Review status", (POLICY_OWNER_REVIEW_NOTE,)))
    if kind == "privacy":
        return ("Privacy — England Works Watch", "Current information handling for the implemented service.", common + (("Information submitted", (
            "Decision tools accept structured sponsor-change facts. The monitoring/report entry accepts only source IDs and opaque source checkpoints; it does not require or retain worker names, addresses, contact details, HR notes, or full case payloads.",
            "Commercial checkout receives only an opaque principal, product ID, callback URLs, bounded source channel, and aggregate milestone metadata. Stripe secrets remain in the shared commercial platform.",
        )), ("Attribution and telemetry", (
            "OpenAI, Claude, and Grok attribution is accepted only from explicit bounded source tokens; arbitrary user-agent or raw source values remain unknown. Optional telemetry is best effort.",
        )), ("Questions", (f"For privacy questions, use {escape(origin.rstrip('/'))}/support and do not send confidential worker or employer material, payment credentials, private keys, or seed phrases.",))))
    if kind == "terms":
        return ("Terms — England Works Watch", "Draft terms describing the current sponsor-compliance product boundary.", common + (("Use", (
            "Use free source-status and supported-event tools before a paid decision. Use monitoring checkpoints only for the official source lifecycle; do not submit employee or employer case payloads to the monitoring entry flow.",
            "The service does not submit Sponsor Management System reports, connect to HRIS/payroll/recruitment systems, monitor employees, or replace Home Office or regulated-adviser judgment.",
        )), ("Results", ("Results are deterministic and evidence-linked. Missing facts, unsupported routes, changed or stale sources, and unavailable evidence remain REVIEW_REQUIRED or INSUFFICIENT_INPUT and must never be treated as clearance.",)), ("Payment", ("x402 agent/API payment is separate from the optional human monitoring/report offer. A success URL or arbitrary query parameter never unlocks a report; an active shared-platform entitlement is verified first." ,))))
    if kind == "support":
        return ("Support — England Works Watch", "Integration, evidence, monitoring and product-boundary support.", common + (("Contact", ("Open a non-sensitive repository issue for integration or listing questions. Include route, approximate time, response status and non-sensitive error text only.",)), ("Useful links", (f"MCP endpoint: {origin.rstrip('/')}/mcp", f"OpenAPI: {origin.rstrip('/')}/openapi.json", f"Source status: {origin.rstrip('/')}/status", f"Monitoring entry: {origin.rstrip('/')}/monitoring-report", f"Security reporting: {origin.rstrip('/')}/security")), ("Monitoring limits", ("Monitoring compares official GOV.UK source fingerprints and versions. It does not infer which employee is affected, deliver alerts, or provide legal clearance.",))))
    raise ValueError(f"unknown policy surface: {kind}")


def render_policy_page(kind: str, *, origin: str) -> str:
    title, intro, sections = policy_copy(kind, origin=origin)
    body = [f'<p class="muted">England Works Watch — sponsor compliance/change intelligence</p><h1>{escape(title)}</h1><p>{escape(intro)}</p>']
    for heading, paragraphs in sections:
        body.append(f"<h2>{escape(heading)}</h2>")
        body.extend(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    body.append('<p class="links"><a href="/pricing">Pricing</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a href="/support">Support</a> · <a href="/monitoring-report">Monitoring report</a></p>')
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(title) + '</title><style>body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:32px 20px;line-height:1.55;color:#17202a}.muted{color:#53636f}.links{margin-top:32px}a{color:#155eef}</style></head><body><main>' + "".join(body) + "</main></body></html>"


def render_pricing_page(*, origin: str, prices: dict[str, str]) -> str:
    rows = "".join(f"<li><strong>{escape(name)}:</strong> {escape(price)}</li>" for name, price in prices.items())
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Pricing — England Works Watch</title><style>'
        'body{font-family:system-ui,sans-serif;max-width:900px;margin:0 auto;padding:32px 20px;line-height:1.55;color:#17202a}'
        '.price,.compare{background:#f5f8fa;border-left:4px solid #155eef;padding:14px 20px;margin:18px 0}'
        '.compare{border-left-color:#137a4b}a{color:#155eef}h2{margin-top:30px}'
        '</style></head><body><main>'
        '<p>England Works Watch — sponsor compliance/change intelligence</p><h1>Pricing</h1>'
        '<p><strong>A one-off interactive sponsor-change preflight is available on the public AI edition.</strong> '
        'Paid products are designed for repeated business use, automation, batch processing, or continued evidence monitoring.</p>'
        '<div class="compare"><strong>Choose the paid path when the work is bigger than one interactive check.</strong>'
        '<ul><li><strong>Batch API:</strong> assess up to 25 structured sponsor changes in one x402 call and receive per-event results plus outcome counts.</li>'
        '<li><strong>30-day Sponsor Decision Evidence Check:</strong> create a dated checkpoint across four core GOV.UK sponsor-duty sources before a sponsor decision, keep a private reusable link, and re-check whether that evidence is unchanged, changed, or needs review for 30 days.</li>'
        '<li><strong>Single-event commercial API:</strong> retained for programmatic integrations that require metered execution of one event.</li></ul></div>'
        '<h2>Commercial prices</h2><div class="price"><ul>' + rows + '</ul></div>'
        '<p>Agent/API calls use x402 Base mainnet USDC. The 30-day human/business monitoring report uses the shared commercial Stripe checkout. '
        'The monitoring offer is not an auto-renewing subscription. Stripe payment is handled by the shared commercial platform; this product does not receive payment credentials.</p>'
        '<p>Monitoring detects official-source change state; it does not send alerts, monitor employees, or provide legal advice.</p>'
        '<p><a href="/monitoring-report"><strong>Create sponsor decision evidence checkpoint — £49</strong></a> · '
        '<a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a href="/support">Support</a></p>'
        '</main></body></html>'
    )


def monitoring_page(*, origin: str, source_channel: str = "direct", owner_test: bool = False) -> str:
    source_channel = escape(source_channel)
    if owner_test:
        verification_control = (
            '<input type="hidden" name="run_class" value="owner_test">'
            '<div class="verification-note"><strong>Operator/test run</strong><br>'
            'This checkout is explicitly marked owner/test and is excluded from customer and revenue evidence.</div>'
        )
    else:
        verification_control = (
            '<label class="source-option verification-option">'
            '<input type="checkbox" name="independent_customer_confirmation" value="yes" required>'
            '<span><strong>Real purchase — not an operator/test run</strong>'
            '<small>Tick to continue. This only separates real customer conversions from our own test traffic; '
            'it is not used to identify you or linked to Stripe payment details.</small></span></label>'
        )
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sponsor decision evidence check — England Works Watch</title>
<meta name="eww-offer-experiment" content="sponsor-offer-v3-2026-09-25">
<style>
:root{
  color-scheme:light;
  --ink:#17202a;
  --muted:#5d6b78;
  --blue:#155eef;
  --blue-soft:#eef4ff;
  --line:#dfe6ec;
  --panel:#f7f9fb;
  --green:#137a4b;
}
*{box-sizing:border-box}
body{
  margin:0;
  font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  color:var(--ink);
  background:#fff;
  line-height:1.55;
}
main{
  max-width:920px;
  margin:0 auto;
  padding:56px 24px 72px;
}
.eyebrow{
  color:var(--blue);
  font-weight:700;
  font-size:.9rem;
  letter-spacing:.04em;
  text-transform:uppercase;
}
h1{
  font-size:2.45rem;
  line-height:1.12;
  margin:10px 0 18px;
  letter-spacing:-.025em;
}
.lead{
  max-width:760px;
  font-size:1.12rem;
  color:var(--muted);
  margin-bottom:28px;
}
.badges{
  display:flex;
  flex-wrap:wrap;
  gap:9px;
  margin:0 0 30px;
}
.badge{
  border:1px solid var(--line);
  border-radius:999px;
  padding:6px 11px;
  font-size:.88rem;
  background:#fff;
}
.offer{
  display:grid;
  grid-template-columns:1fr auto;
  gap:20px;
  align-items:center;
  background:var(--blue-soft);
  border:1px solid #cddcff;
  border-radius:14px;
  padding:22px 24px;
  margin:26px 0;
}
.offer strong{
  display:block;
  font-size:1.15rem;
}
.quick-buy{
  border:1px solid #cddcff;
  border-radius:14px;
  padding:22px 24px;
  margin:0 0 26px;
  background:#fff;
}
.quick-buy h2{
  margin:0 0 6px;
  font-size:1.2rem;
}
.quick-buy p{
  margin:6px 0;
  color:var(--muted);
}
.quick-buy .verification-option{
  margin-top:16px;
}
.quick-buy button{
  width:100%;
  padding:14px 18px;
  font-size:1.02rem;
}
.price{
  font-size:1.7rem;
  font-weight:800;
  white-space:nowrap;
}
.card{
  border:1px solid var(--line);
  border-radius:14px;
  padding:26px;
  margin-top:24px;
  box-shadow:0 8px 28px rgba(23,32,42,.05);
}
.card h2{
  margin:0 0 8px;
  font-size:1.35rem;
}
.card p{
  color:var(--muted);
  margin-top:6px;
}
label{
  display:block;
  font-weight:700;
  margin:22px 0 8px;
}
input{
  width:100%;
  border:1px solid #aeb9c4;
  border-radius:8px;
  padding:12px 13px;
  font:inherit;
}
input:focus{
  outline:3px solid rgba(21,94,239,.15);
  border-color:var(--blue);
}
.source-list{border:0;padding:0;margin:22px 0 0}
.source-list legend{font-weight:700;padding:0}
.source-option{
  display:flex;
  align-items:flex-start;
  gap:12px;
  margin:10px 0;
  padding:12px;
  border:1px solid var(--line);
  border-radius:8px;
  font-weight:400;
}
.source-option input{
  width:auto;
  flex:0 0 auto;
  margin:5px 0 0;
  accent-color:var(--blue);
}
.source-option strong,.source-option small{display:block}
.source-option small{color:var(--muted)}
.verification-option{margin-top:22px;background:#f7fbf9;border-color:#b7dccb}
.verification-note{margin-top:22px;padding:14px 16px;background:#fff7e6;border:1px solid #ead3a0;border-radius:8px;color:#654b13}
button{
  margin-top:18px;
  border:0;
  border-radius:8px;
  background:var(--blue);
  color:#fff;
  padding:12px 18px;
  font:inherit;
  font-weight:750;
  cursor:pointer;
}
button:hover{filter:brightness(.96)}
.boundary{
  margin-top:28px;
  padding:18px 20px;
  background:var(--panel);
  border-radius:10px;
}
.boundary strong{color:var(--green)}
.links{
  margin-top:34px;
  padding-top:22px;
  border-top:1px solid var(--line);
}
a{color:var(--blue)}
@media(max-width:650px){
  main{padding-top:34px}
  h1{font-size:2rem}
  .offer{grid-template-columns:1fr}
  .price{font-size:1.45rem}
}
</style>
</head>
<body>
<main>
  <div class="eyebrow">England Works Watch</div>

  <h1>Before a sponsor change, check that the Home Office guidance you rely on is still current</h1>

  <p class="lead">
    Use this before salary, role, work-location, long-absence, delayed-start,
    stopping-sponsorship, TUPE, merger or takeover decisions. Create a dated
    evidence checkpoint across four core GOV.UK sponsor sources, then re-check
    the same official guidance for 30 days. If the evidence changes or cannot
    be safely compared, the report flags it for review before you act.
  </p>

  <div class="badges">
    <span class="badge">Built for sponsor decisions</span>
    <span class="badge">Dated GOV.UK evidence checkpoint</span>
    <span class="badge">30-day reusable private link</span>
    <span class="badge">No worker PII required</span>
  </div>

  <section class="offer">
    <div>
      <strong>30-day Sponsor Decision Evidence Check</strong>
      <span>Create a dated evidence checkpoint now, then re-check the same four official sources before later sponsor decisions this month.</span>
    </div>
    <div class="price">£49</div>
  </section>

  <section class="quick-buy" id="checkout">
    <h2>Create the evidence checkpoint before your next sponsor decision</h2>
    <p>
      Useful when HR, compliance or an adviser needs a dated record of which
      official guidance was current while reviewing a salary, role, location,
      absence or organisation change. No worker details are required. Checkout
      creates the checkpoint and gives you a private link for repeated checks.
    </p>
    <form method="post" action="/monitoring-report/checkout">
      <input type="hidden" name="source_channel" value="{source_channel}">
      <input type="hidden" name="source_ids" value="sponsor-part2">
      <input type="hidden" name="source_ids" value="sponsor-part3">
      <input type="hidden" name="source_ids" value="skilled-worker">
      <input type="hidden" name="source_ids" value="appendix-d">
      {verification_control}
      <button type="submit">Create sponsor decision evidence checkpoint — £49</button>
    </form>
    <p><small>One payment · 30-day access · no worker names or case facts required · Secure Stripe checkout.</small></p>
  </section>

  <section class="card">
    <h2>Use it when the sponsor decision has consequences</h2>
    <p>
      Re-open the private link before salary or role changes, permanent work-location
      changes, long absences, delayed starts, stopping sponsorship, or organisation
      changes such as TUPE, merger or takeover. The report does not decide those cases;
      it tells you whether the official evidence baseline you are relying on is still
      unchanged or needs review first.
    </p>
    <p>
      Each check shows the source version, observation time, change/review state,
      and direct GOV.UK evidence link. If you need to assess many structured sponsor
      changes in one run, use the separate paid batch API for up to 25 events.
    </p>
  </section>

  <section class="card">
    <h2>What the £49 evidence check gives you</h2>
    <p><strong>Illustrative report fields — this is not a current source result.</strong></p>
    <p>
      <strong>Source:</strong> Sponsor duties and compliance — Part 3<br>
      <strong>Baseline version:</strong> version captured when checkout starts<br>
      <strong>Current version:</strong> latest version observed by the service<br>
      <strong>Change state:</strong> UNCHANGED, CHANGED, or REVIEW REQUIRED<br>
      <strong>Checked at:</strong> timestamp of the latest source observation<br>
      <strong>Evidence:</strong> direct link back to the official GOV.UK guidance
    </p>
    <p>
      Your private return link re-runs the comparison during the 30-day access
      period. If a monitored source changes or cannot be safely compared, the
      report flags it for review instead of silently treating it as unchanged.
      This gives you a repeatable evidence checkpoint before acting on later
      sponsor-change decisions; it does not replace Home Office guidance or legal advice.
    </p>
  </section>

  <section class="card">
    <h2>The default evidence set</h2>
    <p>
      The £49 checkout above already includes all four core sponsor-duty sources,
      so there is no setup required for the standard check. If you need a narrower
      evidence set, you can customise the sources below before checkout.
    </p>

    <form method="post" action="/monitoring-report/checkout">
      <input type="hidden" name="source_channel" value="{source_channel}">
      <fieldset class="source-list">
        <legend>Official guidance to include</legend>
        <p>Choose one or more sources. All four are selected by default.</p>
        <label class="source-option"><input type="checkbox" name="source_ids" value="sponsor-part2" checked><span><strong>Sponsor a worker — Part 2</strong><small>Start dates, unpaid or reduced pay, and changes of employment.</small></span></label>
        <label class="source-option"><input type="checkbox" name="source_ids" value="sponsor-part3" checked><span><strong>Sponsor duties and compliance — Part 3</strong><small>Reporting duties and changes affecting workers or your organisation.</small></span></label>
        <label class="source-option"><input type="checkbox" name="source_ids" value="skilled-worker" checked><span><strong>Sponsor a Skilled Worker</strong><small>Skilled Worker route guidance, including salary changes.</small></span></label>
        <label class="source-option"><input type="checkbox" name="source_ids" value="appendix-d" checked><span><strong>Appendix D — keeping records</strong><small>Sponsorship record-keeping duties.</small></span></label>
      </fieldset>

      <p>Your first comparison starts with a source snapshot saved when you continue to checkout; it does not show changes from before that point. The report links to each selected GOV.UK source and shows its version, last observation and change or review state. Save the private return link to check again during the 30 days. Changes require your review; this service does not send alerts.</p>
      {verification_control}
      <button type="submit">Create customised evidence checkpoint — £49</button>
    </form>
  </section>

  <section class="boundary">
    <strong>Privacy boundary</strong><br>
    This monitoring flow accepts source IDs, opaque source checkpoints, and a
    boolean independent-customer attribution confirmation only. RegEvidenceHub
    does not use payment email, address, card details, or other Stripe PII for
    customer attribution. Do not submit worker names, employer case facts, HR
    notes, addresses, payment credentials, private keys, or seed phrases.
  </section>

  <p class="links">
    <a href="/pricing">Pricing</a> ·
    <a href="/privacy">Privacy</a> ·
    <a href="/terms">Terms</a> ·
    <a href="/support">Support</a>
  </p>
</main>
</body>
</html>""".replace("{source_channel}", source_channel).replace("{verification_control}", verification_control)
