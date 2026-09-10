from england_works_watch.policy import RULES,SOURCE_BY_ID,source_status
def test_every_rule_has_official_source():
    for r in RULES['rules']:
        s=SOURCE_BY_ID[r['source_id']]; assert s['url'].startswith('https://www.gov.uk/'); assert s['last_reviewed']; assert s['valid_from']; assert r['locator']
def test_source_registry_current_today():
    s=source_status('2026-09-08'); assert s['coverage_complete'] is True; assert s['blocking_sources']==[]
