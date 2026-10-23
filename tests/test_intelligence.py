"""Integration tests for R1.1–R3 across roles, tenants and analytical boundaries."""
import os,json
from fastapi.testclient import TestClient
from backend.api import app,configure

def test_complete_decision_intelligence_flow():
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({
        'local-lead':{'user':'project-lead','role':'lead','tenant':'acme'},
        'local-review':{'user':'independent-reviewer','role':'reviewer','tenant':'acme'},
        'other-lead':{'user':'other','role':'lead','tenant':'different'}})
    configure('sqlite:///:memory:')
    c=TestClient(app)
    def call(method,path,token='local-lead',**kwargs):
        return c.request(method,path,headers={'Authorization':'Bearer '+token},**kwargs)
    assert c.get('/v1/intelligence/decisions').status_code==401
    new=call('POST','/v1/initiatives',json={'name':'Claims Copilot','owner':'Operations','description':'demo'})
    assert new.status_code==201,new.text
    iid=new.json()['id']
    data={'initiative_id':iid,'title':'Launch controlled pilot','option_chosen':'90-day pilot','rationale':'Reduce triage errors before expanding','alternatives':['full rollout'],'assumptions':['Adoption > 50%'],'evidence_refs':['ADR-42']}
    created=call('POST','/v1/intelligence/decisions',json=data)
    assert created.status_code==201,created.text
    did=created.json()['id']
    assert call('GET','/v1/intelligence/decisions',token='other-lead').json()==[]
    assert call('POST','/v1/intelligence/decisions',token='other-lead',json=data).status_code==404
    assert call('POST',f'/v1/intelligence/decisions/{did}/outcome',token='other-lead',json={'expected_version':1,'outcome':'Reported faster resolution','source_ref':'report-1'}).status_code==404
    assert call('POST',f'/v1/intelligence/decisions/{did}/outcome',json={'expected_version':1,'outcome':'Pilot reduced handling time, self-reported','source_ref':'pilot-Q4'}).status_code==200
    assert call('POST',f'/v1/intelligence/decisions/{did}/outcome',json={'expected_version':1,'outcome':'Overwritten observation','source_ref':'pilot-Q4'}).status_code==409
    mem=call('GET','/v1/intelligence/memory?q=adoption').json()
    assert mem['count']==1 and mem['decisions'][0]['id']==did
    assert call('GET','/v1/intelligence/memory?q=adoption',token='other-lead').json()['count']==0
    risk={'kind':'risk','name':'Data quality risk','owner':'Risk office','payload':{'likelihood':0.4,'impact_usd':50000},'evidence_status':'modeled'}
    r=call('POST','/v1/intelligence/records',json=risk)
    assert r.status_code==201,r.text
    rid=r.json()['id']
    assert call('GET','/v1/intelligence/records?kind=risk',token='other-lead').json()==[]
    assert call('PUT',f'/v1/intelligence/records/{rid}',json={'expected_version':1,'payload':{'likelihood':0.25,'impact_usd':50000}}).status_code==200
    assert call('PUT',f'/v1/intelligence/records/{rid}',json={'expected_version':1,'payload':{}}).status_code==409
    assert call('POST','/v1/intelligence/records',json={**risk,'evidence_status':'finance_reconciled'}).status_code==422
    economics=call('POST','/v1/intelligence/records',json={'kind':'agent','name':'Claims agent','owner':'Ops','payload':{'task_count':100,'successful_tasks':80,'cost_usd':40}})
    assert economics.status_code==201,economics.text
    out=call('GET','/v1/intelligence/economics-summary').json()
    assert out['items'][0]['cost_per_task']==0.4
    scenario=call('POST','/v1/intelligence/scenario',json={'budget':5,'candidates':[{'name':'A','cost':3,'expected_value':8},{'name':'B','cost':2,'expected_value':6},{'name':'C','cost':5,'expected_value':10}],'max_items':3})
    assert scenario.status_code==200,scenario.text
    assert set(scenario.json()['selected'])=={'A','B'}
    assert call('GET','/v1/intelligence/executive').json()['verified_financial_value'] is None
    brief=call('POST','/v1/intelligence/executive-narrative',json={'audience':'board'}).json()
    assert 'DRAFT' in brief['status'] and 'source_refs' in brief
