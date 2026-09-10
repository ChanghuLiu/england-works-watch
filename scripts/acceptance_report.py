import json
from collections import Counter
from pathlib import Path
from england_works_watch.policy import assess_change_impact
ROOT=Path(__file__).resolve().parents[1]; data=json.loads((ROOT/'data/acceptance_cases.json').read_text()); rows=[]
for case in data['cases']:
    r=assess_change_impact(case['request']); rows.append({'id':case['id'],'category':case['category'],'expected_status':case['expected_status'],'actual_status':r['status'],'expected_code':case['expected_code'],'actual_code':r['decision_code'],'passed':r['status']==case['expected_status'] and r['decision_code']==case['expected_code'],'evidence_count':len(r['affected_rules'])})
counts=Counter(x['category'] for x in data['cases']); report={'gate':data['acceptance_gate'],'counts':dict(counts),'total':len(rows),'passed':sum(x['passed'] for x in rows),'failed':[x for x in rows if not x['passed']],'cases':rows}; (ROOT/'data/acceptance_report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps({k:report[k] for k in ('counts','total','passed','failed')},indent=2)); raise SystemExit(1 if report['failed'] else 0)
