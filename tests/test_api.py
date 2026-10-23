import json
import os

from fastapi.testclient import TestClient

from backend.api import app, configure
from backend.core import REQUIRED, STAGES, optimize

TOKENS={'lead':('lead-user','lead'),'reviewer':('review-user','reviewer'),'approver':('approve-user','approver'),'other':('other-user','lead')}

def setup_module(_):
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({k:{'user':v[0],'role':v[1],'tenant':'other' if k=='other' else 'tenant-a'} for k,v in TOKENS.items()})
    configure('sqlite:///:memory:')

def call(client,method,path,role='lead',**kwargs):return client.request(method,path,headers={'Authorization':'Bearer '+role},**kwargs)

def test_security_and_approval_flow():
    client=TestClient(app)
    assert client.get('/v1/initiatives').status_code==401
    create=call(client,'POST','/v1/initiatives',json={'name':'Claims copilot','owner':'Product'},role='lead')
    assert create.status_code==201,create.text
    iid=create.json()['id'];version=1
    assert call(client,'GET',f'/v1/initiatives/{iid}',role='other').status_code==404
    assert call(client,'POST',f'/v1/initiatives/{iid}/release-approval',role='approver',json={'expected_version':version}).status_code==409
    for stage in STAGES:
        for artifact in REQUIRED[stage]:
            x=call(client,'POST',f'/v1/initiatives/{iid}/evidence',json={'stage':stage,'key':artifact,'reference':'artifact:'+artifact,'expected_version':version})
            assert x.status_code==201,(stage,artifact,x.text)
            version+=1
            full=call(client,'GET',f'/v1/initiatives/{iid}').json()
            eid=next(e['id'] for e in full['evidence'] if e['stage']==stage and e['key']==artifact)
            assert call(client,'POST',f'/v1/initiatives/{iid}/evidence/{eid}/verify',role='lead',json={'expected_version':version}).status_code==403
            y=call(client,'POST',f'/v1/initiatives/{iid}/evidence/{eid}/verify',role='reviewer',json={'expected_version':version})
            assert y.status_code==200,(stage,artifact,y.text)
            version+=1
        if stage=='release':
            blocked=call(client,'GET',f'/v1/initiatives/{iid}').json()
            assert blocked['stages']['release']['status']=='awaiting_approval'
            res=call(client,'POST',f'/v1/initiatives/{iid}/release-approval',role='approver',json={'expected_version':version})
            assert res.status_code==200,res.text
            version+=1
    assert call(client,'GET',f'/v1/initiatives/{iid}').json()['stages']['operate']['status']=='complete'
    assert call(client,'PUT',f'/v1/initiatives/{iid}',json={'name':'Claims copilot','owner':'Product','expected_version':1}).status_code==409
    benefit=call(client,'POST',f'/v1/initiatives/{iid}/benefits',json={'period':'2026-10','planned':100,'reported':80,'run_cost':10,'evidence_reference':'ERP self-report'})
    assert benefit.status_code==201,benefit.text
    assert call(client,'GET','/v1/value-tower').json()['net_reported']==70
    # change earlier evidence invalidates downstream and approval
    first=call(client,'POST',f'/v1/initiatives/{iid}/evidence',json={'stage':'discover','key':'problem','reference':'Changed problem reference','expected_version':version})
    assert first.status_code==201,first.text
    now=call(client,'GET',f'/v1/initiatives/{iid}').json()
    assert now['stages']['release']['status']=='blocked'
    assert not now['approvals']

def test_solver():
    result=optimize({'items':[{'id':'a','cost':5,'impact':9,'secondary':2},{'id':'b','cost':4,'impact':8,'secondary':3},{'id':'c','cost':2,'impact':6,'secondary':7}], 'budget':6})
    assert result['status']=='optimal' and set(result['selected'])=={'b','c'} and result['impact']==14
