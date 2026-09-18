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
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pricing — England Works Watch</title><style>body{font-family:system-ui,sans-serif;max-width:860px;margin:0 auto;padding:32px 20px;line-height:1.55;color:#17202a}.price{background:#f5f8fa;border-left:4px solid #155eef;padding:12px 20px}a{color:#155eef}</style></head><body><main><p>England Works Watch — sponsor compliance/change intelligence</p><h1>Pricing</h1><p>Agent/API decisions use x402 Base mainnet USDC. The optional human/business monitoring report uses the shared commercial Stripe checkout.</p><div class="price"><ul>' + rows + '</ul></div><p>The human offer provides bounded repeated access during its configured entitlement period; it is not an auto-renewing subscription. Stripe payment is handled by the shared commercial platform; this product does not receive payment credentials.</p><p>Monitoring is official-source change detection, not legal advice or employee monitoring.</p><p><a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a href="/support">Support</a> · <a href="/monitoring-report">Monitoring report</a></p></main></body></html>'


def monitoring_page(*, origin: str, source_channel: str = "direct") -> str:
    source_channel = escape(source_channel)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sponsor compliance monitoring — England Works Watch</title>
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

  <h1>Sponsor compliance monitoring report</h1>

  <p class="lead">
    Monitor official GOV.UK sponsor-guidance sources for version and
    semantic-fingerprint changes. Use this when your compliance workflow
    needs evidence that key sponsor guidance has changed or remained stable.
  </p>

  <div class="badges">
    <span class="badge">Official-source monitoring</span>
    <span class="badge">Evidence-first</span>
    <span class="badge">No worker PII required</span>
    <span class="badge">Secure Stripe checkout</span>
  </div>

  <section class="offer">
    <div>
      <strong>Sponsor Monitoring Report</strong>
      <span>Repeated access during a 30-day entitlement period. No subscription.</span>
    </div>
    <div class="price">£49</div>
  </section>

  <section class="card">
    <h2>Select the guidance sources to monitor</h2>
    <p>
      The default scope covers the core sponsor-duty and Skilled Worker
      guidance used by England Works Watch.
    </p>

    <form method="post" action="/monitoring-report/checkout">
      <input type="hidden" name="source_channel" value="{source_channel}">
      <label for="source_ids">Source IDs</label>
      <input
        id="source_ids"
        name="source_ids"
        value="sponsor-part2,sponsor-part3,skilled-worker,appendix-d"
        autocomplete="off"
      >

      <button type="submit">Continue to checkout</button>
    </form>
  </section>

  <section class="boundary">
    <strong>Privacy boundary</strong><br>
    This monitoring flow accepts source IDs and opaque source checkpoints only.
    Do not submit worker names, employer case facts, HR notes, addresses,
    payment credentials, private keys, or seed phrases.
  </section>

  <p class="links">
    <a href="/pricing">Pricing</a> ·
    <a href="/privacy">Privacy</a> ·
    <a href="/terms">Terms</a> ·
    <a href="/support">Support</a>
  </p>
</main>
</body>
</html>""".replace("{source_channel}", source_channel)
