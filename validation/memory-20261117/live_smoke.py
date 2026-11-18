import json,time
from pathlib import Path
import httpx
origin='https://works.regevidencehub.com';out=[]
with httpx.Client(timeout=40,follow_redirects=True,headers={'User-Agent':'works-memory-release-validation','X-Mcp-Commercial-Actor':'owned_ci'}) as client:
 for path in ['/health','/status','/metrics','/analytics/summary','/openapi.json','/version','/monitoring-report']:
  start=time.monotonic();r=client.get(origin+path);assert r.status_code==200,(path,r.status_code);item={'path':path,'status':r.status_code,'seconds':round(time.monotonic()-start,3)}
  if path=='/health':item['health']=r.json();assert item['health']['payment_enforced'];assert item['health']['source_baselines']=='4/4';assert item['health']['production_ready']
  out.append(item)
 for endpoint in ['/mcp','/mcp-directory/','/ai/mcp','/openai/mcp']:
  headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
  r=client.post(origin+endpoint,headers=headers,json={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'england-works-watch-owned-smoke','version':'memory-release'}}});assert r.status_code==200,(endpoint,r.status_code)
  if r.headers.get('mcp-session-id'):headers['mcp-session-id']=r.headers['mcp-session-id']
  headers['MCP-Protocol-Version']='2025-06-18'
  client.post(origin+endpoint,headers=headers,json={'jsonrpc':'2.0','method':'notifications/initialized'})
  r=client.post(origin+endpoint,headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}});assert r.status_code==200
  text=r.text
  if text.startswith(('data:','event:')):text=next(l[5:].strip() for l in text.splitlines() if l.startswith('data:'))
  result=json.loads(text)['result'];out.append({'path':endpoint,'status':200,'tool_count':len(result['tools']),'tools_called':False})
  if 'mcp-session-id' in headers:client.delete(origin+endpoint,headers=headers)
 r=client.post(origin+'/api/v1/assess-change-impact',json={'event_type':'unauthorised_absence','route':'skilled_worker','consecutive_working_days':11});assert r.status_code==402,r.status_code
 assert 'EW-ABS-REPORT' not in r.text
 out.append({'path':'/api/v1/assess-change-impact','status':402,'payment_proof_supplied':False,'decision_leaked':False})
 for _ in range(4):
  r=client.get(origin+'/health');assert r.status_code==200;assert r.json()['production_ready']
Path('validation/memory-20261117/live-smoke.json').write_text(json.dumps(out,indent=2))
print('LIVE_CHECKS_PASS',len(out),'plus4repeatedhealth',json.dumps(out[-5:]))
