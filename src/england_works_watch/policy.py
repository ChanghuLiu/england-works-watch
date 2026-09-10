from __future__ import annotations
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
import hashlib, json

ROOT=Path(__file__).resolve().parents[2]; DATA=ROOT/'data'
def _load(n): return json.loads((DATA/n).read_text())
SOURCES=_load('source_registry.json'); RULES=_load('rule_pack.json')
SOURCE_BY_ID={x['source_id']:x for x in SOURCES['sources']}; RULE_BY_ID={x['rule_id']:x for x in RULES['rules']}
VALID={'AFFECTED','NOT_AFFECTED','REVIEW_REQUIRED','INSUFFICIENT_INPUT'}

def _digest(s):
    keys=('source_id','url','version','valid_from','locators')
    return hashlib.sha256(json.dumps({k:s[k] for k in keys},sort_keys=True,separators=(',',':')).encode()).hexdigest()

def source_status(as_of:str|None=None)->dict[str,Any]:
    today=date.fromisoformat(as_of) if as_of else datetime.now(timezone.utc).date(); items=[]; blocking=[]
    for s in SOURCES['sources']:
        age=(today-date.fromisoformat(s['last_reviewed'])).days; state=s['state']
        effective='REVIEW_REQUIRED' if state=='CURRENT' and age>int(s.get('review_after_days',30)) else state
        items.append({**s,'review_age_days':age,'effective_state':effective,'metadata_fingerprint':_digest(s)})
        if effective!='CURRENT': blocking.append(s['source_id'])
    return {'product':'England Works Watch','scope':RULES['scope'],'rule_pack_version':RULES['rule_pack_version'],'coverage_complete':not blocking,'blocking_sources':blocking,'sources':items}

def evidence(ids):
    out=[]
    for rid in ids:
        r=RULE_BY_ID[rid]; s=SOURCE_BY_ID[r['source_id']]
        out.append({'rule_id':rid,'source_id':s['source_id'],'source_title':s['title'],'url':s['url'],'version':s['version'],'valid_from':s['valid_from'],'locator':r['locator'],'proposition':r['proposition'],'last_reviewed':s['last_reviewed']})
    return out

def _r(event,status,code,rules,why,actions=None,missing=None,review=None,deadline=None):
    assert status in VALID
    return {'status':status,'decision_code':code,'event_type':event,'scope':RULES['scope'],'rule_pack_version':RULES['rule_pack_version'],'effective_date':RULES['effective_date'],'rationale':why,'required_actions':actions or [],'deadline':deadline,'missing_inputs':missing or [],'review_reasons':review or [],'affected_rules':evidence(rules),'disclaimer':'Evidence-first sponsor compliance preflight. Not legal advice and not a substitute for Home Office or regulated adviser review.'}

def _missing(q,*names): return [n for n in names if q.get(n) is None]
def _gate(event,rules):
    bad=sorted({RULE_BY_ID[r]['source_id'] for r in rules if SOURCE_BY_ID[RULE_BY_ID[r]['source_id']]['state']!='CURRENT'})
    return _r(event,'REVIEW_REQUIRED','EW-SOURCE-GATE',rules,['A required official source is not in CURRENT reviewed state.'],review=[f'source_not_current:{x}' for x in bad]) if bad else None

def assess_change_impact(q:dict[str,Any])->dict[str,Any]:
    e=str(q.get('event_type','')).strip().lower(); route=str(q.get('route','skilled_worker')).strip().lower()
    if route!='skilled_worker': return _r(e or 'unknown','REVIEW_REQUIRED','EW-SCOPE-001',[],['This rule pack is limited to Skilled Worker sponsor duties.'],review=['unsupported_route'])
    supported={'worker_start_delay','unauthorised_absence','unpaid_or_reduced_pay_absence','salary_change','role_change','work_location_change','stop_sponsoring','organisation_change','tupe_transfer','merger_takeover'}
    if e not in supported: return _r(e or 'unknown','INSUFFICIENT_INPUT','EW-EVENT-001',[],['A supported sponsor change event_type is required.'],missing=['event_type'])

    if e=='worker_start_delay':
        rules=['SW-START-28','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'delay_days')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-START-MISSING',rules,['delay_days is required.'],missing=m)
        d=q['delay_days']
        if not isinstance(d,(int,float)) or isinstance(d,bool) or d<0:return _r(e,'REVIEW_REQUIRED','EW-START-INVALID',rules,['delay_days is invalid.'],review=['invalid_delay_days'])
        if d<=28:return _r(e,'NOT_AFFECTED','EW-START-OK',rules,['The worker is not more than 28 days late on the supplied facts.'])
        return _r(e,'AFFECTED','EW-START-LATE',rules,['The worker is more than 28 days late.'],['Report the new start date and reason, or stop sponsoring if the worker will not start.'],deadline={'working_days':10,'trigger':'end of the 28-day permitted start window'})

    if e=='unauthorised_absence':
        rules=['SPONSOR-ABSENCE-10','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'consecutive_working_days')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-ABS-MISSING',rules,['consecutive_working_days is required.'],missing=m)
        d=q['consecutive_working_days']
        if not isinstance(d,int) or isinstance(d,bool) or d<0:return _r(e,'REVIEW_REQUIRED','EW-ABS-INVALID',rules,['consecutive_working_days is invalid.'],review=['invalid_absence_days'])
        if d<=10:return _r(e,'NOT_AFFECTED','EW-ABS-OK',rules,['The absence does not exceed 10 consecutive working days.'])
        return _r(e,'AFFECTED','EW-ABS-REPORT',rules,['The absence exceeds 10 consecutive working days.'],['Report the unauthorised absence and relevant circumstances in SMS.'],deadline={'working_days':10,'trigger':'after the 10th consecutive working day'})

    if e=='unpaid_or_reduced_pay_absence':
        rules=['SW-UNPAID-4W','SW-UNPAID-EXCEPTIONS','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'total_weeks','valid_exception')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-UNPAID-MISSING',rules,['Duration and exception status are required.'],missing=m)
        w=q['total_weeks']
        if not isinstance(w,(int,float)) or isinstance(w,bool) or w<0:return _r(e,'REVIEW_REQUIRED','EW-UNPAID-INVALID',rules,['total_weeks is invalid.'],review=['invalid_total_weeks'])
        if w<=4:return _r(e,'NOT_AFFECTED','EW-UNPAID-OK',rules,['The absence does not exceed 4 weeks in total.'])
        if q['valid_exception'] is True:return _r(e,'AFFECTED','EW-UNPAID-EXEMPT',rules,['A listed permitted exception is supplied.'],['Report the extended absence and retain evidence supporting the exception.'],deadline={'working_days':10,'trigger':'reportable worker circumstance'})
        if q['valid_exception'] is False:
            if q.get('compelling_reason') is True:return _r(e,'REVIEW_REQUIRED','EW-UNPAID-COMPELLING',rules,['A compelling reason is asserted outside the listed exceptions.'],['Escalate for sponsor/regulated-adviser review.'],review=['compelling_reason_requires_case_review'])
            return _r(e,'AFFECTED','EW-UNPAID-STOP',rules,['The absence exceeds 4 weeks and no listed permitted exception is supplied.'],['Stop sponsoring unless another Home Office-permitted basis is established, and report the change.'],deadline={'working_days':10,'trigger':'reportable worker circumstance'})
        return _r(e,'REVIEW_REQUIRED','EW-UNPAID-CONFLICT',rules,['valid_exception must be boolean.'],review=['invalid_exception_flag'])

    if e=='salary_change':
        rules=['SW-SALARY-CHANGE','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'direction')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-SALARY-MISSING',rules,['direction is required.'],missing=m)
        d=str(q['direction']).lower()
        if d=='increase':
            if q.get('pre_registration_nurse_or_midwife') is True:return _r(e,'REVIEW_REQUIRED','EW-SALARY-INCREASE-SPECIAL',rules,['A pre-registration nurse/midwife special reporting case is supplied.'],review=['route_specific_salary_increase_exception'])
            return _r(e,'NOT_AFFECTED','EW-SALARY-INCREASE',rules,['An ordinary Skilled Worker salary increase is not a reportable reduction trigger.'])
        if d!='decrease':return _r(e,'REVIEW_REQUIRED','EW-SALARY-DIRECTION',rules,['direction must be increase or decrease.'],review=['invalid_direction'])
        m=_missing(q,'same_salary_option_still_met')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-SALARY-OPTION-MISSING',rules,['Confirm whether the same salary points option remains met.'],missing=m)
        if q['same_salary_option_still_met'] is True:return _r(e,'AFFECTED','EW-SALARY-REPORT',rules,['The same salary points option remains met.'],['Report the salary reduction via SMS.'],deadline={'working_days':10,'trigger':'salary reduction'})
        if q['same_salary_option_still_met'] is not False:return _r(e,'REVIEW_REQUIRED','EW-SALARY-OPTION-CONFLICT',rules,['same_salary_option_still_met must be boolean.'],review=['invalid_salary_option_flag'])
        m=_missing(q,'revised_salary_meets_skilled_worker')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-SALARY-ELIGIBILITY-MISSING',rules,['Revised Skilled Worker salary eligibility is required.'],missing=m)
        if q['revised_salary_meets_skilled_worker'] is True:return _r(e,'AFFECTED','EW-SALARY-NEW-COS',rules,['The same salary option is lost but revised salary remains eligible.'],['Assign a new CoS and obtain the required successful change application before reduced pay begins.'],deadline={'trigger':'before reduced pay begins'})
        if q['revised_salary_meets_skilled_worker'] is False:return _r(e,'AFFECTED','EW-SALARY-STOP',rules,['The revised salary does not meet Skilled Worker salary requirements.'],['Stop sponsoring and report the change.'],deadline={'working_days':10,'trigger':'sponsorship-ending circumstance'})
        return _r(e,'REVIEW_REQUIRED','EW-SALARY-ELIGIBILITY-CONFLICT',rules,['revised_salary_meets_skilled_worker must be boolean.'],review=['invalid_revised_salary_flag'])

    if e=='role_change':
        rules=['SW-ROLE-CHANGE','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'same_occupation_code')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-ROLE-MISSING',rules,['Occupation-code comparison is required.'],missing=m)
        if q['same_occupation_code'] is False:return _r(e,'AFFECTED','EW-ROLE-NEW-COS',rules,['The new role uses a different occupation code.'],['Assign a new CoS and obtain change-of-employment approval before the new role starts.'],deadline={'trigger':'before starting the new role'})
        if q['same_occupation_code'] is not True:return _r(e,'REVIEW_REQUIRED','EW-ROLE-CONFLICT',rules,['same_occupation_code must be boolean.'],review=['invalid_occupation_code_flag'])
        m=_missing(q,'role_eligible','salary_requirements_met')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-ROLE-ELIGIBILITY-MISSING',rules,['Same-code changes still require eligibility and salary facts.'],missing=m)
        if not q['role_eligible'] or not q['salary_requirements_met']:return _r(e,'REVIEW_REQUIRED','EW-ROLE-ELIGIBILITY-FAIL',rules,['An eligibility or salary condition is flagged unmet.'],review=['eligibility_or_salary_condition_unmet'])
        return _r(e,'AFFECTED','EW-ROLE-REPORT',rules,['The role remains in the same occupation code and supplied conditions are met.'],['Report the significant role/title/core-duty change via SMS.'],deadline={'working_days':10,'trigger':'significant employment change'})

    if e=='work_location_change':
        rules=['SPONSOR-WORK-LOCATION','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        keys=('new_main_office','new_client_site','permanent_remote','hybrid_only','occasional_only'); f={k:q.get(k) for k in keys}
        if all(v is None for v in f.values()):return _r(e,'INSUFFICIENT_INPUT','EW-LOC-MISSING',rules,['At least one location-change fact is required.'],missing=list(keys))
        report=any(f[k] is True for k in ('new_main_office','new_client_site','permanent_remote'))
        if report and (f['hybrid_only'] is True or f['occasional_only'] is True):return _r(e,'REVIEW_REQUIRED','EW-LOC-CONFLICT',rules,['Reportable permanent/new location conflicts with hybrid-only or occasional-only facts.'],review=['conflicting_location_facts'])
        if report:return _r(e,'AFFECTED','EW-LOC-REPORT',rules,['A new main office/client site or permanent/full-time remote location is supplied.'],['Report the normal work-location change via SMS.'],deadline={'working_days':10,'trigger':'work-location change'})
        if f['hybrid_only'] is True or f['occasional_only'] is True:return _r(e,'NOT_AFFECTED','EW-LOC-NO-REPORT',rules,['Only a hybrid-pattern shift with unchanged main office or an occasional/day-to-day variation is supplied.'])
        return _r(e,'INSUFFICIENT_INPUT','EW-LOC-AMBIG',rules,['The supplied facts do not establish whether the change is reportable.'],missing=['reportable_location_or_hybrid/occasional_fact'])

    if e=='stop_sponsoring':
        rules=['SPONSOR-STOP-SPONSORING','SPONSOR-REPORT-10']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'reason')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-STOP-MISSING',rules,['A sponsorship-ending reason is required.'],missing=m)
        reason=str(q['reason']).lower(); known={'resignation','dismissal','redundancy','early_contract_end','lost_professional_registration','settlement','other_non_sponsored_route'}
        if reason not in known:return _r(e,'REVIEW_REQUIRED','EW-STOP-OTHER',rules,['The reason is outside the V0.1 enumerated ending reasons.'],review=['unclassified_stop_reason'])
        return _r(e,'AFFECTED','EW-STOP-REPORT',rules,[f'The supplied circumstance ({reason}) ends or removes the need for sponsorship.'],['Report that sponsorship has ended and record the reason.'],deadline={'working_days':10,'trigger':'sponsorship-ending circumstance'})

    if e=='organisation_change':
        rules=['SPONSOR-ORG-20']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'change_kind')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-ORG-MISSING',rules,['change_kind is required.'],missing=m)
        kind=str(q['change_kind']).lower()
        if kind in {'merger','takeover','ownership_change'}:return _r(e,'REVIEW_REQUIRED','EW-ORG-STRUCTURAL',['SPONSOR-ORG-20','SPONSOR-TUPE-MERGER'],['Structural ownership/merger changes need the specialised workflow.'],['Use merger_takeover or tupe_transfer with the required structural facts.'],review=['structural_change_requires_specialised_event'])
        if kind in {'name','address','contact','head_office','branches','sites','linked_entities','registration','accreditation','stop_trading','insolvency'}:return _r(e,'AFFECTED','EW-ORG-REPORT',rules,[f'The supplied organisation change ({kind}) is reportable.'],['Report the organisation change and supply supporting evidence if requested.'],deadline={'working_days':20,'trigger':'becoming aware of the organisation change'})
        return _r(e,'REVIEW_REQUIRED','EW-ORG-OTHER',rules,['The organisation change is not classified in V0.1.'],review=['unclassified_organisation_change'])

    if e=='tupe_transfer':
        rules=['SPONSOR-TUPE-MERGER']; g=_gate(e,rules)
        if g:return g
        m=_missing(q,'duties_unchanged','same_occupation_code','new_sponsor_has_relevant_licence')
        if m:return _r(e,'INSUFFICIENT_INPUT','EW-TUPE-MISSING',rules,['Duties, occupation-code and receiving-sponsor licence facts are required.'],missing=m)
        if q['duties_unchanged'] is not True or q['same_occupation_code'] is not True:return _r(e,'REVIEW_REQUIRED','EW-TUPE-DUTY-CHANGE',rules,['This is not a clean same-duties/same-occupation transfer.'],review=['possible_change_of_employment_requirements'])
        if q['new_sponsor_has_relevant_licence'] is True:return _r(e,'AFFECTED','EW-TUPE-LICENSED',rules,['The receiving sponsor already has the relevant licence.'],['Receiving sponsor accepts sponsorship responsibility and reports transferred workers; no new CoS/change application is required solely for this transfer on the supplied facts.'],deadline={'working_days':20,'trigger':'takeover/TUPE change'})
        if q['new_sponsor_has_relevant_licence'] is False:return _r(e,'AFFECTED','EW-TUPE-NO-LICENCE',rules,['The receiving sponsor does not have the relevant licence.'],['Apply for or extend the sponsor licence to the relevant route and report the structural change.'],deadline={'working_days':20,'trigger':'takeover/TUPE change'})
        return _r(e,'REVIEW_REQUIRED','EW-TUPE-LICENCE-CONFLICT',rules,['new_sponsor_has_relevant_licence must be boolean.'],review=['invalid_licence_flag'])

    rules=['SPONSOR-ORG-20','SPONSOR-TUPE-MERGER']; g=_gate(e,rules)
    if g:return g
    m=_missing(q,'change_type','old_entity_continues_trading','new_entity_has_relevant_licence')
    if m:return _r(e,'INSUFFICIENT_INPUT','EW-MERGER-MISSING',rules,['Structural continuity and licence facts are required.'],missing=m)
    if str(q['change_type']).lower() not in {'complete_takeover','partial_takeover','merger','ownership_change'}:return _r(e,'REVIEW_REQUIRED','EW-MERGER-TYPE',rules,['The transaction type is not recognised by V0.1.'],review=['unclassified_transaction'])
    return _r(e,'AFFECTED','EW-MERGER-REPORT',rules,['A merger/takeover/ownership transaction is reportable and may affect sponsor-licence continuity.'],['Report the structural change.','Review whether the continuing/receiving entity must apply for or extend a sponsor licence.'],deadline={'working_days':20,'trigger':'merger/takeover/ownership change'})
