"""Human recovery form; only the non-secret order reference may be prefilled."""
from html import escape

RECOVERY_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
}


def render_report_recovery(checkout_id: str = "") -> str:
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">
<title>Recover sponsor report · England Works Watch</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#172b43;font-family:system-ui,-apple-system,sans-serif;line-height:1.65}
main{max-width:720px;margin:0 auto;padding:56px 24px}.eyebrow{font-size:.78rem;color:#155eef;font-weight:750;letter-spacing:.09em;text-transform:uppercase}
h1{font-size:clamp(1.9rem,5vw,2.6rem);letter-spacing:-.035em;line-height:1.2;margin:12px 0 20px}p{color:#586a80}
.card{background:#fff;border:1px solid #dce4ef;border-top:4px solid #155eef;border-radius:18px;padding:30px;margin-top:28px;box-shadow:0 8px 30px #172b4308}
label{display:block;font-weight:650;margin-bottom:10px}.field+.field{margin-top:26px}
input{display:block;width:100%;min-width:0;font:inherit;color:inherit;padding:13px 16px;border:1px solid #aabacf;border-radius:8px;background:#fff}
.hint{font-size:.85rem;margin:8px 0 0}button{width:100%;font:inherit;font-weight:700;border:0;border-radius:9px;background:#155eef;color:#fff;padding:14px 20px;margin-top:30px;cursor:pointer}
button:hover{background:#124ac0}button:disabled{opacity:.65;cursor:wait}:focus-visible{outline:3px solid #94b9ff;outline-offset:3px}
#status{margin-top:22px;padding:18px 20px;border:1px solid #c5d5f8;border-radius:10px;background:#edf3ff;color:#17325c;overflow-wrap:anywhere}#status:empty{display:none}
#status[data-state="success"]{background:#ecfdf3;color:#14532d;border-color:#86d8a1}#status[data-state="error"]{background:#fef2f2;color:#991b1b;border-color:#fca5a5}
#status strong{display:block;margin-bottom:6px}#status p{color:inherit;margin:0}.next-step{display:block;font-weight:750;margin-top:12px;padding-top:12px;border-top:1px solid #a7dcbc}
footer{margin-top:28px;font-size:.85rem}nav{display:flex;flex-wrap:wrap;gap:20px;margin-top:20px}a{color:#155eef;text-underline-offset:3px}
@media(max-width:600px){main{padding:28px 16px}.card{padding:24px 18px}}
</style></head><body><main><p class="eyebrow">England Works Watch · Report access</p>
<h1>Recover your sponsor report</h1><p>Use your saved order reference and the email you used at checkout. No further payment is needed.</p>
<section class="card"><form id="recovery-form">
<div class="field"><label for="checkout-id">Order reference</label>
<input id="checkout-id" name="checkout_id" minlength="32" maxlength="64" autocomplete="off" spellcheck="false" required value="__ORDER_REFERENCE__">
<p class="hint">You can find this on your paid report.</p></div>
<div class="field"><label for="contact-email">Email used at checkout</label>
<input id="contact-email" name="contact_email" type="email" maxlength="254" autocomplete="email" placeholder="you@example.com" required></div>
<button type="submit">Send recovery link</button></form>
<div id="status" role="status" aria-live="polite" aria-atomic="true"></div>
<noscript><p>Enable JavaScript to request a recovery link.</p></noscript></section>
<footer><a href="/monitoring-report/checkout-success">Return to your report</a>
<p>Recovery links are private. Use the newest link from your email.</p>
<nav aria-label="Service information"><a href="/privacy">Privacy</a><a href="/terms">Terms</a><a href="/support">Support</a></nav></footer>
</main><script>
const form=document.getElementById('recovery-form'),status=document.getElementById('status'),button=form.querySelector('button');
function showStatus(state,title,message,action){
  status.dataset.state=state;status.replaceChildren();
  const heading=document.createElement('strong');heading.textContent=title;status.append(heading);
  const detail=document.createElement('p');detail.textContent=message;status.append(detail);
  if(action){const next=document.createElement('span');next.className='next-step';next.textContent=action;status.append(next);}
}
form.addEventListener('submit',async event=>{
  event.preventDefault();if(button.disabled||!form.reportValidity())return;
  button.disabled=true;button.textContent='Sending…';form.setAttribute('aria-busy','true');
  showStatus('pending','Sending your request','Please wait a moment.');
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
  try{
    const response=await fetch('/api/v1/report-access/recovery',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
      body:JSON.stringify({checkout_id:form.elements.checkout_id.value.trim(),contact_email:form.elements.contact_email.value.trim()})});
    if(response.ok){showStatus('success','Recovery request received','If a paid report matches those details, a recovery link will be sent.','Open your email to continue. Use the newest recovery link.');}
    else if(response.status===422){showStatus('error','Check your details','Enter the full order reference and a valid checkout email.');}
    else{showStatus('error','Recovery temporarily unavailable','Please try again shortly. No further payment is needed.');}
  }catch(error){
    showStatus('error',error.name==='AbortError'?'Request timed out':'Could not send the request',
      error.name==='AbortError'?'Check your email for a recovery link before trying again.':'Please check your connection and try again.');
  }finally{clearTimeout(timer);button.disabled=false;button.textContent='Send recovery link';form.removeAttribute('aria-busy');}
});
</script></body></html>""".replace("__ORDER_REFERENCE__", escape(checkout_id, quote=True))
