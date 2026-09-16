"""Public, human-readable pages required for plugin submission.

These routes describe only the read-only UK Sponsor Change Checker directory
edition. They do not change the commercial /mcp surface, decision rules, or
payment behavior.
"""
from __future__ import annotations

import os
from html import escape

from starlette.responses import HTMLResponse, PlainTextResponse, Response

from . import server

SUPPORT_EMAIL = os.getenv("EWW_SUPPORT_EMAIL", "launchcircle.server@gmail.com").strip()


def _page(title: str, body: str) -> HTMLResponse:
    email = escape(SUPPORT_EMAIL)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="index,follow">
  <title>{escape(title)} — UK Sponsor Change Checker</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 780px; margin: 48px auto; padding: 0 20px; line-height: 1.6; color: #171717; }}
    h1,h2 {{ line-height: 1.25; }}
    code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 4px; }}
    .muted {{ color: #666; }}
    nav a {{ margin-right: 14px; }}
  </style>
</head>
<body>
  <nav><a href="/uk-sponsor-change-checker">Product</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/support">Support</a></nav>
  {body}
  <hr>
  <p class="muted">Support: <a href="mailto:{email}">{email}</a></p>
</body>
</html>"""
    return HTMLResponse(html)


@server.mcp.custom_route("/uk-sponsor-change-checker", methods=["GET"])
async def plugin_product_page(_request):
    return _page(
        "UK Sponsor Change Checker",
        """
<h1>UK Sponsor Change Checker</h1>
<p>UK Sponsor Change Checker is a read-only compliance preflight for employers and advisers working with Skilled Worker sponsor duties.</p>
<p>It checks how defined employee or organisation changes — including salary, role, work location, absence, delayed start, stopping sponsorship, TUPE, merger or takeover events — affect sponsor duties.</p>
<p>Results use one of four explicit states: <strong>AFFECTED</strong>, <strong>NOT_AFFECTED</strong>, <strong>REVIEW_REQUIRED</strong>, or <strong>INSUFFICIENT_INPUT</strong>, with supporting GOV.UK evidence and next-action information where available.</p>
<h2>Scope</h2>
<p>The current release covers Skilled Worker sponsor duties only. It is an evidence-first preflight, not legal advice and not a Home Office decision.</p>
<h2>ChatGPT / plugin endpoint</h2>
<p>The public directory edition uses a dedicated read-only MCP endpoint. It does not require sign-in and does not request or process payment.</p>
<p class="muted">Powered by England Works Watch. England Works Watch is not affiliated with or endorsed by the UK Home Office or GOV.UK.</p>
""",
    )


@server.mcp.custom_route("/privacy", methods=["GET"])
async def privacy_page(_request):
    return _page(
        "Privacy Policy",
        """
<h1>Privacy Policy</h1>
<p><strong>Effective date:</strong> 16 September 2026</p>
<p>This policy covers the public read-only <strong>UK Sponsor Change Checker</strong> plugin edition operated through England Works Watch.</p>
<h2>Information processed</h2>
<p>When you ask the plugin to assess a sponsor-related change, the service processes the task-specific facts supplied in that tool call in order to return a result. The directory edition does not require a user account and does not ask for passwords, payment credentials, cryptocurrency keys, precise location, contact lists, or full conversation history.</p>
<h2>Operational telemetry</h2>
<p>The service records privacy-minimal operational telemetry used for reliability, abuse prevention, attribution, and product measurement. This can include timestamp, tool name, success or error outcome, latency, declared client or integration name when supplied by the client, coarse source attribution, request or correlation identifier when supplied, and deployment revision.</p>
<p>The application analytics database does <strong>not</strong> persist the substantive sponsor-change scenario payload supplied to the decision tool.</p>
<h2>Official-source evidence</h2>
<p>The service uses publicly available GOV.UK sponsor guidance as evidence. Source fingerprints and review status are monitored so changed or stale evidence can fail closed rather than silently producing a decision.</p>
<h2>How information is used</h2>
<p>Information is used to provide the requested decision preflight, maintain service reliability and security, diagnose errors, measure aggregate usage, and improve tool selection and product quality.</p>
<h2>Sharing and service providers</h2>
<p>Information may be processed by infrastructure providers that host or operate the service. We do not sell user data. We do not use the plugin to build advertising profiles.</p>
<h2>Retention</h2>
<p>Operational telemetry may be retained for service operations, reliability analysis, security, and aggregate product measurement. We do not promise a fixed automatic deletion period. You may contact support to request deletion of information that can reasonably be identified as relating to your use.</p>
<h2>Security</h2>
<p>We use reasonable technical and operational safeguards, including a read-only public plugin surface, minimal tool inputs, fail-closed evidence handling, and separation from the commercial payment-enabled MCP surface.</p>
<h2>International processing</h2>
<p>Service infrastructure may process information in countries other than your own. By using the plugin, you acknowledge that cross-border processing may occur subject to applicable law and provider safeguards.</p>
<h2>Children</h2>
<p>This plugin is intended for professional compliance use and is not directed to children.</p>
<h2>Changes and contact</h2>
<p>We may update this policy as the service changes. Material changes will be reflected on this page with a revised effective date. Privacy questions or requests can be sent to the support address below.</p>
""",
    )


@server.mcp.custom_route("/terms", methods=["GET"])
async def terms_page(_request):
    return _page(
        "Terms of Use",
        """
<h1>Terms of Use</h1>
<p><strong>Effective date:</strong> 16 September 2026</p>
<p>These terms apply to the public read-only UK Sponsor Change Checker plugin edition.</p>
<h2>Purpose</h2>
<p>The plugin provides an evidence-linked compliance preflight for defined UK Skilled Worker sponsor-change scenarios. It is an informational decision-support tool.</p>
<h2>Not legal advice</h2>
<p>The plugin does not provide legal advice, immigration representation, or a Home Office decision. Users remain responsible for verifying facts, reviewing official guidance, obtaining professional advice where appropriate, and meeting all legal or reporting obligations.</p>
<h2>Scope and fail-closed behavior</h2>
<p>The current release covers Skilled Worker sponsor duties only. Unsupported routes, missing facts, conflicting inputs, or blocked official-source evidence may produce <strong>REVIEW_REQUIRED</strong> or <strong>INSUFFICIENT_INPUT</strong> rather than a substantive determination.</p>
<h2>Acceptable use</h2>
<p>Do not use the service to submit secrets, passwords, private keys, payment credentials, or unrelated personal data. Do not attempt to disrupt, overload, reverse engineer, or misuse the service.</p>
<h2>No payment on the plugin edition</h2>
<p>The public directory endpoint is read-only and does not request, initiate, or process payments or cryptocurrency transfers.</p>
<h2>Availability and changes</h2>
<p>The service may be changed, suspended, rate-limited, or discontinued. Tool definitions and evidence sources may evolve as official guidance changes.</p>
<h2>Accuracy and warranties</h2>
<p>We aim to provide accurate, source-backed results, but the service is provided on an "as is" and "as available" basis to the extent permitted by law. No warranty is made that every result will be complete, current, or suitable for a particular legal or business decision.</p>
<h2>Limitation</h2>
<p>To the extent permitted by applicable law, the operator is not liable for indirect, incidental, special, consequential, or business-interruption losses arising from use of or reliance on the plugin.</p>
<h2>Third-party sources</h2>
<p>GOV.UK and UK Home Office materials remain the property of their respective rights holders. References to official sources do not imply endorsement or affiliation.</p>
<h2>Contact</h2>
<p>Questions about these terms can be sent to the support address below.</p>
""",
    )


@server.mcp.custom_route("/support", methods=["GET"])
async def support_page(_request):
    email = escape(SUPPORT_EMAIL)
    return _page(
        "Support",
        f"""
<h1>Support</h1>
<p>For UK Sponsor Change Checker support, report the issue by email:</p>
<p><strong><a href="mailto:{email}">{email}</a></strong></p>
<h2>Include</h2>
<ul>
  <li>the approximate time of the request,</li>
  <li>which type of sponsor change you were checking,</li>
  <li>the decision state or error you received, and</li>
  <li>a short description of what you expected.</li>
</ul>
<p>Do not send passwords, private keys, payment credentials, or unnecessary personal information.</p>
<h2>Service status</h2>
<p>Machine-readable service health is available at <a href="/health"><code>/health</code></a>.</p>
""",
    )


@server.mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def openai_apps_challenge(_request):
    """Serve the exact OpenAI portal domain-verification token when configured."""
    token = os.getenv("OPENAI_APPS_CHALLENGE", "").strip()
    if not token:
        return Response(status_code=404)
    return PlainTextResponse(token, media_type="text/plain")
