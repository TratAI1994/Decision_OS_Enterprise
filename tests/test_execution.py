"""R4: tenant, FK, human+agent, finance gates, conflict, source-based cost, proposal approvals."""
import os,json
from datetime import date,timedelta
from fastapi.testclient import TestClient
from backend.api import app,configure

def test_etes_end_to_end():
    os.environ['DECISION_OS_IDENTITIES']=json.dumps({
      'leadA':{'user':'lead-a','tenant':'A','role':'lead'},
      'reviewA':{'user':'review-a','tenant':'A','role':'reviewer'},
      'leadB':{'user':'lead-b','tenant':'B','role':'lead'}})
    configure('sqlite:///:memory:')
    c=TestClient(app)
    def req(method,path,key='leadA',**kw):return c.request(method,path,headers={'Authorization':'Bearer '+key},**kw)
    a=req('POST','/v1/initiatives',json={'name':'Claims Transform','owner':'VP Operations','description':''}).json()['id']
    b=req('POST','/v1/initiatives',key='leadB',json={'name':'Private initiative','owner':'Other','description':''}).json()['id']
    d=req('POST','/v1/intelligence/decisions',json={'initiative_id':a,'title':'Fund AI pilot','option_chosen':'Pilot','rationale':'Reduce error and improve response','assumptions':['value after validation'],'alternatives':[],'evidence_refs':[]}).json()['id']
    db=req('POST','/v1/intelligence/decisions',key='leadB',json={'initiative_id':b,'title':'Private board decision','option_chosen':'Pilot','rationale':'other','assumptions':[],'alternatives':[],'evidence_refs':[]}).json()['id']
    assert req('POST','/v1/execution/tasks',json={'initiative_id':a,'decision_id':db,'title':'Illegal cross tenant','assignee_kind':'human','assignee_ref':'VP Operations','cost_model_source':'board'}).status_code==422
    assignees=req('GET','/v1/execution/assignees').json()
    assert any(x['ref']=='VP Operations' for x in assignees)
    agent=req('POST','/v1/intelligence/records',json={'kind':'agent','name':'QA Agent','owner':'VP Operations','payload':{'initiative_id':a,'risk_tier':'medium'},'request_id':'agenttest001'})
    assert agent.status_code==201,agent.text
    agent_id=agent.json()['id']
    assert any(x['kind']=='agent' and x['ref']==agent_id for x in req('GET','/v1/execution/assignees').json())
    payload={'initiative_id':a,'decision_id':d,'title':'Evaluate model quality','description':'review real golden dataset','assignee_kind':'agent','assignee_ref':agent_id,'business_stage':'Funded','technical_stage':'Evaluate','daily_value_at_risk':250,'cost_model_source':'executive hypothesis draft v1'}
    created=req('POST','/v1/execution/tasks',json=payload)
    assert created.status_code==201,created.text
    tid=created.json()['id'];assert created.json()['impact']['modeled_deferred_value']==0
    assert req('GET','/v1/execution/tasks',key='leadB').json()==[]
    assert req('GET',f'/v1/execution/thread/{tid}',key='leadB').status_code==404
    thread=req('GET',f'/v1/execution/thread/{tid}').json()
    assert thread['funding_decision']['id']==d
    since=(date.today()-timedelta(days=10)).isoformat()
    update={'expected_version':1,'status':'blocked','business_stage':'Delivering','technical_stage':'Secure','blocked_since':since}
    changed=req('PATCH',f'/v1/execution/tasks/{tid}',json=update)
    assert changed.status_code==200,changed.text
    assert changed.json()['impact']['modeled_deferred_value']==2500
    assert req('PATCH',f'/v1/execution/tasks/{tid}',json=update).status_code==409
    assert req('PATCH',f'/v1/execution/tasks/{tid}',json={**update,'expected_version':2,'business_stage':'Value Realized'}).status_code==409
    assert req('PATCH',f'/v1/execution/tasks/{tid}',json={**update,'expected_version':2,'technical_stage':'Release','status':'completed','blocked_since':None}).status_code==409
    brief=req('GET','/v1/execution/brief').json()
    assert brief['blocked_count']==1 and brief['total_modeled_deferred_value']==2500
    proposal=req('POST','/v1/execution/proposals',json={'task_id':tid,'recommendation':'Schedule independent security review','evidence_basis':'security gate not complete'})
    assert proposal.status_code==201,proposal.text
    pid=proposal.json()['id']
    assert req('POST',f'/v1/execution/proposals/{pid}/review',json={'approved':True}).status_code==403
    approved=req('POST',f'/v1/execution/proposals/{pid}/review',key='reviewA',json={'approved':True})
    assert approved.status_code==200 and approved.json()['executed'] is False
    assert req('POST',f'/v1/execution/proposals/{pid}/review',key='reviewA',json={'approved':True}).status_code==409
    assert req('GET','/v1/execution/proposals',key='leadB').json()==[]
