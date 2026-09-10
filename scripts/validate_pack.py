from england_works_watch.policy import RULES,SOURCES,RULE_BY_ID,SOURCE_BY_ID,source_status
assert RULES['scope'].startswith('UK Skilled Worker'); assert len(RULE_BY_ID)==len(RULES['rules']); assert len(SOURCE_BY_ID)==len(SOURCES['sources'])
for r in RULES['rules']: assert r['source_id'] in SOURCE_BY_ID and r['locator'] and r['proposition']
s=source_status(); print({'rules':len(RULE_BY_ID),'sources':len(SOURCE_BY_ID),'coverage_complete':s['coverage_complete'],'blocking_sources':s['blocking_sources']})
