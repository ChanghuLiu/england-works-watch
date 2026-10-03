"""Presentation helpers for purchase forms and browser notices."""
from functools import wraps
from html import escape
import re

PRODUCT = "Sponsor monitoring report"
RETURN_ROUTE = "/monitoring-report"

FORM_STYLE = """
*{box-sizing:border-box}body{color:#18324b;font-family:system-ui,-apple-system,sans-serif;line-height:1.65;background:#f3f6fb}
a{color:#1b56c4;text-underline-offset:3px}p{margin-top:0}h1{font-size:clamp(28px,5vw,40px);line-height:1.2}h2{line-height:1.3}
label{display:block}input,select,textarea{font:inherit;color:inherit;max-width:100%;min-height:48px;border:1px solid #b3c3d6;border-radius:9px;padding:11px 13px;background:white}
input:not([type=checkbox]):not([type=radio]),select,textarea{width:100%}input[type=checkbox],input[type=radio]{width:auto;min-height:auto}
button{min-height:48px;border:0;border-radius:9px;padding:12px 20px;background:#215cdb;color:white;font:inherit;font-weight:700;cursor:pointer}
button:disabled{opacity:.65;cursor:not-allowed}button:hover:not(:disabled){background:#1748b2}
input:focus-visible,select:focus-visible,textarea:focus-visible,button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #92b8ff;outline-offset:3px}
fieldset{min-width:0;background:white;border:1px solid #dce5ef;border-radius:14px;padding:24px;margin:24px 0}legend{padding:0 8px}
.field{min-width:0;padding:14px 0}.field>*{min-width:0}.preview,.result,.errors{border-radius:12px;padding:22px 24px;margin:24px 0}
details{margin-top:24px}summary{cursor:pointer;padding:8px 0;font-weight:700}pre{white-space:pre-wrap;overflow-wrap:anywhere}code{overflow-wrap:anywhere}
.purchase-brand{color:#215cdb;font-size:13px;font-weight:800;letter-spacing:.08em;margin-bottom:24px}
.purchase-nav{margin-top:28px;padding-top:22px;border-top:1px solid #e4ebf3;font-size:14px}
@media(max-width:640px){body{padding:24px 16px}.field{grid-template-columns:minmax(0,1fr)!important;gap:7px;align-items:start}
fieldset{padding:18px}button{width:100%}.preview,.result,.errors{padding:18px}dt{float:none;clear:none;width:auto}dd{margin-left:0}}
"""
NOTICE_STYLE = """
body{max-width:760px;margin:0 auto;padding:48px 24px}main{background:white;border:1px solid #dce5ef;border-top:4px solid #215cdb;border-radius:18px;padding:34px;box-shadow:0 10px 32px #18324b10}
#status{padding:16px;background:#edf4ff;border-radius:10px;overflow-wrap:anywhere}main>button{margin-top:12px}
@media(max-width:640px){body{padding:24px 16px}main{padding:24px}}
"""


def polish_page(markup):
    if 'data-purchase-ui="v1"' in markup:
        return markup
    naked = "<style" not in markup
    style = '<style data-purchase-ui="v1">' + FORM_STYLE + (NOTICE_STYLE if naked else "") + "</style>"
    viewport = "" if re.search(r'name=[\"\']?viewport', markup) else '<meta name="viewport" content="width=device-width,initial-scale=1">'
    extra = viewport + style
    if "</head>" in markup:
        markup = markup.replace("</head>", extra + "</head>", 1)
    elif "<main" in markup:
        pos = markup.index("<main")
        markup = markup[:pos] + extra + markup[pos:]
    else:
        markup = '<!doctype html><html lang="en"><head><meta charset="utf-8">' + extra + '</head><body><main>' + markup + '</main></body></html>'
    if naked:
        markup = re.sub(r'(<main[^>]*>)', r'\1<header class="purchase-brand">' + escape(PRODUCT) + '</header>', markup, count=1)
        navigation = '<nav class="purchase-nav"><a href="' + escape(RETURN_ROUTE, quote=True) + '">Return to ' + escape(PRODUCT) + '</a></nav>'
        markup = markup.replace("</main>", navigation + "</main>", 1)
    return markup


def purchase_page(fn):
    @wraps(fn)
    def render(*args, **kwargs):
        return polish_page(fn(*args, **kwargs))
    return render


def browser_report_response(request, payload, status_code=200, headers=None):
    from starlette.responses import JSONResponse, HTMLResponse
    if "text/html" not in request.headers.get("accept", "").lower():
        return JSONResponse(payload, status_code=status_code, headers=headers)
    status = payload.get("status", "Report unavailable")
    messages = {
        "CHECKOUT_CANCELLED": ("Checkout cancelled", "No report purchase was completed. Return to the form when you are ready."),
        "INVALID_REQUEST": ("Check your report details", "Review the selected sources and enter a valid checkout email, then try again."),
        "COMMERCIAL_UNAVAILABLE": ("Checkout temporarily unavailable", "We could not start checkout. Please try again shortly."),
        "PAYMENT_PENDING_OR_REPORT_UNAVAILABLE": ("Payment pending", "Your payment may still be processing. Refresh shortly or use verified-email recovery."),
        "REPORT_ACCESS_UNAVAILABLE": ("Report access unavailable", "We could not verify access. Use verified-email recovery or try again shortly."),
        "REPORT_UNAVAILABLE": ("Report unavailable", "Use your paid order reference and checkout email to recover access."),
    }
    title, detail = messages.get(status, ("Report unavailable", "Return to the report form or use email recovery."))
    page = '<h1>' + escape(title) + '</h1><p>' + escape(detail) + '</p><p><a href="/monitoring-report/recover">Recover your paid report</a></p>'
    return HTMLResponse(polish_page(page), status_code=status_code, headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
    })
