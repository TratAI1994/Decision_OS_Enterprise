import os,json
from fastapi.testclient import TestClient
from backend.api import app,configure

def test_packets_isolation_policy_review_replay():
 os.environ['DECISION_OS_IDENTITIES']=json.dumps({'lead':{'user':'lead','tenant':'A','role':'lead'},'reviewer':{'user':'reviewer','tenant':'A','role':'reviewer'},'other':{'user':'other','tenant':'B','role':'lead'},'finance':{'user':'fin','tenant':'A','role':'finance'}})
 configure('sqlite:///:memory:');c=TestClient(app)
 def req(m,p,as_='lead',**kw):return c.request(m,p,headers={'Authorization':'Bearer '+as_},**kw)
 iid=req('POST','/v1/initiatives',json={'name':'Claims Copilot','owner':'Risk Lead','description':''}).json()['id']
 d=req('POST','/v1/intelligence/decisions',json={'initiative_id':iid,'title':'Expand claims operations','option_chosen':'Approve pilot','rationale':'Measure impact before scale','assumptions':[],'evidence_refs':['FIN-01']}).json()['id']
 assert req('GET',f'/v1/decisions-governed/context/{d}',as_='other').status_code==404
 payload={'decision_id':d,'title':'Assign additional risk reviewer','action_kind':'assign_reviewer','expected_spend_cents':0,'rationale':'The independent risk assessment requires a dedicated reviewer.','evidence_refs':['FIN-01'],'request_id':'unique_request_abcdefghijk'}
 a=req('POST','/v1/decisions-governed/packets',json=payload);assert a.status_code==201,a.text
 b=req('POST','/v1/decisions-governed/packets',json=payload);assert b.json()['id']==a.json()['id']
 pid=a.json()['id']
 assert req('POST',f'/v1/decisions-governed/packets/{pid}/review',json={'expected_version':1,'decision':'approve','assigned_owner':'Risk Lead'}).status_code==403
 assert req('GET','/v1/decisions-governed/packets',as_='other').json()==[]
 reviewed=req('POST',f'/v1/decisions-governed/packets/{pid}/review',as_='reviewer',json={'expected_version':1,'decision':'approve','assigned_owner':'Risk Lead'});assert reviewed.status_code==200,reviewed.text
 assert len(req('GET','/v1/decisions-governed/actions').json())==1
 assert req('POST',f'/v1/decisions-governed/packets/{pid}/review',as_='reviewer',json={'expected_version':1,'decision':'approve','assigned_owner':'Risk Lead'}).status_code==409
 replay=req('GET',f'/v1/decisions-governed/replay/{d}').json();assert len(replay['historical_snapshots'])==1 and replay['historical_snapshots'][0]['hash_valid']
 assert req('GET','/v1/decisions-governed/memory',as_='other').json()['items']==[]

def test_policy_budget_ceiling():
 os.environ['DECISION_OS_IDENTITIES']=json.dumps({'lead':{'user':'lead','tenant':'A','role':'lead'}})
 configure('sqlite:///:memory:');c=TestClient(app);H={'Authorization':'Bearer lead'}
 iid=c.post('/v1/initiatives',headers=H,json={'name':'Another','owner':'Owner','description':''}).json()['id']
 d=c.post('/v1/intelligence/decisions',headers=H,json={'initiative_id':iid,'title':'Board mandate','option_chosen':'Pilot','rationale':'Valid rationale','assumptions':[],'evidence_refs':[]}).json()['id']
 p={'decision_id':d,'title':'Increase pilot allocation','action_kind':'propose_budget_change','expected_spend_cents':1_000_001,'rationale':'We need extra funding for reviewed work and qualified contractors.','evidence_refs':['BUDGET-01'],'request_id':'budget_retry_0000000000001'}
 r=c.post('/v1/decisions-governed/packets',headers=H,json=p);assert r.status_code==403,r.text
