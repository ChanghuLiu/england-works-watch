import os,sys,json,hashlib,time,resource,importlib.util
from datetime import datetime,timezone,timedelta
from pathlib import Path
from england_works_watch import analytics
class FixedDateTime(datetime):
 @classmethod
 def now(cls,tz=None):return cls(2026,11,17,12,0,0,tzinfo=timezone.utc)
mode=sys.argv[1]
if mode=='before':
 spec=importlib.util.spec_from_file_location('england_works_watch._baseline_analytics','/tmp/works-memory-baseline-20261117/src/england_works_watch/analytics.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
else:mod=analytics
mod.datetime=FixedDateTime
if mode=='seed':
 with analytics._db() as db:
  db.execute('DELETE FROM events')
  tools=['__machine_discovery__',*sorted(analytics.FREE_TOOLS),*sorted(analytics.BUSINESS_TOOLS),'other']
  dates=['invalid','2026-11-16T12:00:00Z','2026-11-10T12:00:00Z','2026-11-17T13:00:00Z','2026-10-01T12:00:00Z','2026-11-17T10:00:00Z']
  clients=[None,'github-smoke','chatgpt-test','claude-client','arbitrary-client','owner-monitor']
  def rows():
   for i in range(143917):
    yield (dates[i%len(dates)],tools[i%len(tools)],'ok',int(i%3==0),[None,'challenge','paid_executed','payment_error'][i%4],['unattributed','unknown','declared_external','owned_ci'][i%4],clients[i%len(clients)],3.2,['unknown','free_business_call','paid_executed','discovery_observed'][i%4],['unknown','openai','glama'][i%3],'unknown',0,'synthetic',None,'unknown')
  db.executemany('INSERT INTO events(occurred_at,tool,outcome,billable,payment_state,actor_class,declared_client,latency_ms,event_type,source_bucket,external_classification,owner_test,deployment_revision,request_id,payment_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows())
 print('SEEDED143917');raise SystemExit
start=time.monotonic();data=mod.summary();elapsed=time.monotonic()-start
rss=int(next(l.split()[1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('VmRSS:')))
result={'seconds':round(elapsed,3),'rss_kib':rss,'peak_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'payload':data}
Path('validation/memory-20261117/'+mode+'.json').write_text(json.dumps(result,indent=2));print(mode,elapsed,'rssKiB',rss,'peakKiB',result['peak_kib'])
