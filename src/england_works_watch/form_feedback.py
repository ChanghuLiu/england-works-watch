"""Accessible feedback for human forms; submitted values stay in the response only."""
from functools import wraps
from html import escape, unescape
import re


STYLE = """
.form-error-summary,.errors{background:#fff1f2!important;color:#881337!important;border:2px solid #be123c!important;border-left-width:6px!important;border-radius:12px;padding:20px 24px!important;margin:24px 0!important;overflow-wrap:anywhere}
.form-error-summary[hidden]{display:none!important}.form-error-summary h2,.errors h2{color:inherit;font-size:1.2rem;margin:0 0 10px!important}.form-error-summary p{color:inherit;margin:0 0 10px}.form-error-summary a,.errors a{color:#9f1239;font-weight:700;text-underline-offset:3px}.form-error-summary li,.errors li{margin:7px 0}
input[aria-invalid=true],select[aria-invalid=true],textarea[aria-invalid=true]{border:2px solid #be123c!important;background:#fff8f8!important;box-shadow:0 0 0 1px #be123c}
.form-field-error{display:block;grid-column:1/-1;color:#9f1239!important;font-size:.95rem;font-weight:650;margin:8px 0 16px!important;line-height:1.5}.form-field-error[hidden]{display:none!important}
[data-state=error][role=status],[data-state=error][aria-live]{background:#fff1f2!important;color:#881337!important;border:2px solid #be123c!important;border-radius:10px;padding:16px!important}
@media(max-width:640px){.form-error-summary,.errors{padding:16px!important}}
"""

SCRIPT = r"""
(()=>{
if(window.regheFormFeedback)return;window.regheFormFeedback=true;
let sequence=0;
const controls=form=>Array.from(form.querySelectorAll('input:not([type=hidden]),select,textarea')).filter(f=>!f.disabled&&f.type!=='submit'&&f.type!=='button');
const label=f=>{const l=f.labels&&f.labels[0];return (l?l.textContent:f.getAttribute('aria-label')||f.name||'This field').trim().replace(/\s+/g,' ');};
const normal=s=>s.toLowerCase().replace(/[_-]/g,' ').replace(/[^a-z0-9 ]/g,'').replace(/\s+/g,' ').trim();
function fieldError(f,message){
 if(!f.id)f.id='form-field-'+(++sequence);
 const id=f.id+'-error';let p=document.getElementById(id);
 if(!p){p=document.createElement('p');p.id=id;p.className='form-field-error';(f.closest('label')||f).insertAdjacentElement('afterend',p);}
 p.textContent=message;p.hidden=false;f.setAttribute('aria-invalid','true');
 const ids=new Set((f.getAttribute('aria-describedby')||'').split(' ').filter(Boolean));ids.add(id);f.setAttribute('aria-describedby',Array.from(ids).join(' '));
}
function clear(f){f.removeAttribute('aria-invalid');const p=document.getElementById(f.id+'-error');if(p)p.hidden=true;}
function problem(f){
 const name=label(f),v=f.validity;
 if(f.name==='checkout_id'&&(f.value.trim().length<32||f.value.trim().length>64))return 'Enter the complete order reference saved with your purchase (32–64 characters).';
 if(v.valueMissing)return f.type==='checkbox'?'Tick “'+name+'” to continue.':f.tagName==='SELECT'?'Choose an option for '+name+'.':'Enter '+name+'.';
 if(v.typeMismatch&&f.type==='email')return 'Enter a valid email address, for example you@example.com.';
 if(v.badInput)return 'Enter a number for '+name+'.';
 if(v.rangeUnderflow||v.rangeOverflow)return 'Enter '+name+' '+(f.min!==''&&f.max!==''?'between '+f.min+' and '+f.max:f.min!==''?'of '+f.min+' or more':'of '+f.max+' or less')+'.';
 if(v.stepMismatch)return 'Enter '+name+' '+(f.step==='1'?'as a whole number.':'using the allowed number increments.');
 if(v.tooShort)return 'Enter at least '+f.minLength+' characters for '+name+'.';
 if(v.tooLong)return 'Use no more than '+f.maxLength+' characters for '+name+'.';
 if(v.patternMismatch)return f.dataset.formatHint||'Check the format of '+name+'.';
 if(f.dataset.validateJson==='object'&&f.value.trim()){
  try{const x=JSON.parse(f.value);if(!x||typeof x!=='object'||Array.isArray(x))return 'Scenario details must be a JSON object, for example {"nation":"England","role":"receiver","activities":["receive_waste"]}.';}
  catch{return 'Scenario details must be valid JSON. Use double quotes around field names and text, and remove trailing commas.';}
 }
 return v.valid?'':'Check '+name+' and try again.';
}
function summary(form,problems){
 let box=form.querySelector(':scope > .form-error-summary');
 if(!box){box=document.createElement('section');box.className='form-error-summary';box.tabIndex=-1;box.setAttribute('role','alert');form.prepend(box);}
 box.replaceChildren();box.hidden=false;
 const h=document.createElement('h2');h.textContent='Please correct '+(problems.length===1?'this field':problems.length+' fields')+' to continue';
 const p=document.createElement('p');p.textContent='Your entries are still here. Select an error below to go to the field.';
 const ul=document.createElement('ul');for(const [f,message] of problems){fieldError(f,message);const li=document.createElement('li'),a=document.createElement('a');a.href='#'+f.id;a.textContent=message;a.addEventListener('click',e=>{e.preventDefault();f.focus();f.scrollIntoView({block:'center'});});li.append(a);ul.append(li);}
 box.append(h,p,ul);box.focus();box.scrollIntoView({block:'center'});
}
function enhance(form){
 if(form.dataset.formFeedback)return;form.dataset.formFeedback='true';form.noValidate=true;
 for(const f of controls(form)){
  if(!f.id)f.id='form-field-'+(++sequence);
  if(f.name==='checkout_id'){f.minLength=32;f.maxLength=64;}
  if(f.name==='payload'&&f.tagName==='TEXTAREA')f.dataset.validateJson='object';
  const update=()=>{clear(f);const message=problem(f);if(message&&form.dataset.validationAttempted)fieldError(f,message);const box=form.querySelector(':scope > .form-error-summary');if(box)box.hidden=true;};
  f.addEventListener('input',update);f.addEventListener('change',update);
 }
 form.addEventListener('submit',event=>{
  const problems=controls(form).map(f=>[f,problem(f)]).filter(x=>x[1]);
  if(form.dataset.requireActivity==='true'&&!form.querySelector('input[name^=activity_]:checked')){const f=form.querySelector('input[name^=activity_]');if(f)problems.push([f,'Waste activities: select at least one activity.']);}
  if(form.dataset.requireSources==='true'&&!form.querySelector('input[name=source_ids]:checked')){const f=form.querySelector('input[name=source_ids]');if(f)problems.push([f,'Monitoring sources: select at least one source.']);}
  form.dataset.validationAttempted='true';
  if(problems.length){event.preventDefault();event.stopImmediatePropagation();summary(form,problems);}
 },true);
}
function serverErrors(){
 document.querySelectorAll('.errors:not([data-feedback-ready]),[data-form-errors]:not([data-feedback-ready])').forEach(box=>{
  box.dataset.feedbackReady='true';box.setAttribute('role','alert');box.tabIndex=-1;
  const fields=Array.from(document.querySelectorAll('form')).flatMap(controls);
  box.querySelectorAll('li').forEach(li=>{
   const explicit=li.dataset.field;
   let field=explicit?fields.find(f=>f.id===explicit||f.name===explicit):null;
   if(!field){const text=normal(li.textContent);let best=0;for(const f of fields){const n=normal(f.name),l=normal(label(f));const score=(n&&text.includes(n)?n.length:0)+(l&&text.includes(l)?l.length:0);if(score>best){best=score;field=f;}}}
   if(field){const message=li.textContent;fieldError(field,message);const a=document.createElement('a');a.href='#'+field.id;a.textContent=message;a.addEventListener('click',e=>{e.preventDefault();field.focus();field.scrollIntoView({block:'center'});});li.replaceChildren(a);}
  });
  box.focus();box.scrollIntoView({block:'center'});
 });
}
function scan(){document.querySelectorAll('form').forEach(enhance);serverErrors();document.querySelectorAll('[role=status],[aria-live]').forEach(p=>{if(/^(check |could not|we couldn|recovery is temporarily|the request could not|this recovery link could not|request timed out)/i.test(p.textContent.trim()))p.dataset.state='error';});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',scan);else scan();
new MutationObserver(records=>{document.querySelectorAll('[role=status],[aria-live]').forEach(p=>{if(/^(check |could not|we couldn|recovery is temporarily|the request could not|this recovery link could not|request timed out)/i.test(p.textContent.trim()))p.dataset.state='error';});if(records.some(r=>Array.from(r.addedNodes).some(n=>n.nodeType===1&&(n.matches('form,input,select,textarea')||n.querySelector('form')))))scan();}).observe(document.documentElement,{childList:true,subtree:true});
})();
"""


def with_form_feedback(markup: str) -> str:
    if 'data-form-feedback="v1"' in markup:
        return markup
    style = '<style data-form-feedback="v1">' + STYLE + '</style>'
    if '</head>' in markup:
        markup = markup.replace('</head>', style + '</head>', 1)
    else:
        markup = markup.replace('<main', style + '<main', 1)
    script = '<script>' + SCRIPT + '</script>'
    marker = '</body>' if '</body>' in markup else '</html>'
    return markup.replace(marker, script + marker, 1) if marker in markup else markup + script


def feedback_page(fn):
    @wraps(fn)
    def render(*args, **kwargs):
        return with_form_feedback(fn(*args, **kwargs))
    return render


def error_summary(errors, fields=None):
    if not errors:
        return ''
    fields = fields or {}
    entries = ''.join('<li data-field="' + escape(fields.get(message, ''), quote=True) + '">' + escape(message) + '</li>' for message in errors)
    return '<section class="form-error-summary" data-form-errors role="alert" tabindex="-1"><h2>Please correct these details to continue</h2><p>Your entries are still here. Review the fields below.</p><ul>' + entries + '</ul></section>'


def bind_form_values(markup: str, values) -> str:
    """Restore only existing visible controls, escaping all untrusted values."""
    def attr(tag, name):
        match = re.search(r'\b' + name + r'=["\']([^"\']*)["\']', tag, re.I)
        return unescape(match.group(1)) if match else ''

    def text(value):
        return 'true' if value is True else 'false' if value is False else '' if value is None else str(value)

    input_ids = {}

    def input_value(match):
        tag = match.group(0)
        name, kind = attr(tag, 'name'), attr(tag, 'type').lower()
        if not name or kind == 'hidden':
            return tag
        if not attr(tag, 'id'):
            input_ids[name] = input_ids.get(name, 0) + 1
            identifier = name if input_ids[name] == 1 else name + '-' + str(input_ids[name])
            tag = tag[:-1] + ' id="' + escape(identifier, quote=True) + '">'
        if name not in values:
            return re.sub(r'\schecked(?:=["\'][^"\']*["\'])?', '', tag, flags=re.I) if kind == 'checkbox' and values else tag
        value = text(values[name])
        if kind in {'checkbox', 'radio'}:
            tag = re.sub(r'\schecked(?:=["\'][^"\']*["\'])?', '', tag, flags=re.I)
            selected = (attr(tag, 'value') in values[name] if isinstance(values[name], (list, tuple)) else value.strip().lower() in {'true', '1', 'yes', 'on'} or attr(tag, 'value') in value.split(',')) if kind == 'checkbox' else value == attr(tag, 'value')
            return tag[:-1] + (' checked' if selected else '') + '>'
        tag = re.sub(r'\svalue=["\'][^"\']*["\']', '', tag, flags=re.I)
        return tag[:-1] + ' value="' + escape(value, quote=True) + '">'

    markup = re.sub(r'<input\b[^>]*>', input_value, markup, flags=re.I)

    def select_value(match):
        tag, options = match.group(1), match.group(2)
        name = attr(tag, 'name')
        if name not in values:
            return match.group(0)
        wanted = text(values[name])
        options = re.sub(r'\sselected(?:=["\'][^"\']*["\'])?', '', options, flags=re.I)
        def choose(option):
            opening = option.group(0)
            return opening[:-1] + (' selected' if attr(opening, 'value') == wanted else '') + '>'
        options = re.sub(r'<option\b[^>]*>', choose, options, flags=re.I)
        return tag + options + '</select>'
    markup = re.sub(r'(<select\b[^>]*>)(.*?)</select>', select_value, markup, flags=re.I | re.S)
    markup = re.sub(r'(<textarea\b[^>]*>)(.*?)</textarea>', lambda m: m.group(1) + (escape(text(values[attr(m.group(1), 'name')])) if attr(m.group(1), 'name') in values else m.group(2)) + '</textarea>', markup, flags=re.I | re.S)
    return markup
