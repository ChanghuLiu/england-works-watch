import json
from pathlib import Path
from england_works_watch.policy import assess_change_impact
ROOT=Path(__file__).resolve().parents[1]
CASES=json.loads((ROOT/'data/acceptance_cases.json').read_text())['cases']
def test_acceptance_casebook():
    for case in CASES:
        r=assess_change_impact(case['request']); assert r['status']==case['expected_status'],case['id']; assert r['decision_code']==case['expected_code'],case['id']
        if r['affected_rules']:
            assert all(x['url'].startswith('https://www.gov.uk/') for x in r['affected_rules']); assert all(x['valid_from'] for x in r['affected_rules'])
def test_acceptance_gate_counts():
    c=[x['category'] for x in CASES]; assert len(CASES)>=20; assert c.count('negative_control')>=5; assert c.count('sponsor_event')>=5; assert c.count('independent')>=10
