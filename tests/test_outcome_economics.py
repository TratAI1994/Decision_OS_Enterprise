import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db import Base,Initiative
from backend.intelligence import DecisionRecord
from backend.outcome_economics import OutcomeEvent,build_router,money_cents,verify_chain,replay,summarize

@pytest.fixture
def fixture():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(engine,expire_on_commit=False)
    with Session() as db:
        for ten in ('A','B'):
            db.add(Initiative(id='i'+ten,tenant_id=ten,name='Cloud',owner='owner'));db.flush()
            db.add(DecisionRecord(id='d'+ten,tenant_id=ten,initiative_id='i'+ten,title='Azure AI rollout',option_chosen='Pilot',rationale='baseline',owner='owner',state='proposed'))
        db.commit()
    api=FastAPI()
    def identity(authorization:str|None=Header(default=None)):
        if not authorization:raise HTTPException(401,'Missing')
        t,u,r=authorization.removeprefix('Bearer ').split(':')
        return type('Actor',(),dict(tenant=t,user=u,role=r))()
    def session():
        with Session() as db:yield db
    def require(actor,roles):
        if actor.role not in roles:raise HTTPException(403,'Forbidden')
    api.include_router(build_router(identity,session,require))
    yield TestClient(api),Session
    engine.dispose()

def auth(who='A:owner:editor'):return {'Authorization':'Bearer '+who}
def plan():return {'decision_id':'dA','expected_amount':'12000000.00','currency_code':'USD','period':'2026-10','methodology':'Annualized saving model based on controlled pilot','baseline_ref':'finance:forecast:101','request_id':'req_plan_unique_01'}
def claim():return {'period':'2026-10','reported_amount':'9500000.00','measurement_method':'General ledger cost center comparison','source_ref':'erp:claims:101','attribution_method':'correlational','attribution_notes':'Hiring and seasonal demand are confounders','expected_seq':1,'request_id':'req_claim_unique_01'}
def verify(claim_id):return {'claim_event_id':claim_id,'verified_amount':'8700000.00','reconciliation_method':'Controller reconciled to GL and cash invoices','financial_source_ref':'gl:posting:009','notes':'Adoption below forecast; causal explanation untested','expected_seq':2,'confirmation':'I independently reconciled this benefit against financial evidence.','request_id':'req_verify_unique_01'}
def prepare(client):
    assert client.post('/v1/outcome-economics/plan',json=plan(),headers=auth()).status_code==201
    c=client.post('/v1/outcome-economics/dA/report',json=claim(),headers=auth())
    assert c.status_code==201,c.text
    return c.json()['id']

def test_exact_money():
    assert money_cents('12000000.00')==1200000000
    for v in ('nan','inf','1.001','-infinity'):
        with pytest.raises(ValueError):money_cents(v)

def test_without_finance_variance_is_withheld(fixture):
    c,_=fixture;prepare(c)
    o=c.get('/v1/outcome-economics/dA',headers=auth()).json()
    assert o['summary']['status']=='self_reported' and o['summary']['variance'] is None
    assert o['summary']['finance_verified'] is None

def test_verified_variance_and_attribution(fixture):
    c,_=fixture;cid=prepare(c)
    resp=c.post('/v1/outcome-economics/dA/finance-attest',json=verify(cid),headers=auth('A:controller:finance'))
    assert resp.status_code==201,resp.text
    s=c.get('/v1/outcome-economics/dA',headers=auth()).json()['summary']
    assert s['finance_verified']=='8700000.00' and s['variance']=='-3300000.00'
    assert s['attribution']=='correlational' and s['finance_reviewer']=='controller'

def test_role_restriction_and_self_attestation(fixture):
    c,_=fixture;cid=prepare(c)
    assert c.post('/v1/outcome-economics/dA/finance-attest',json=verify(cid),headers=auth('A:manager:admin')).status_code==403
    assert c.post('/v1/outcome-economics/dA/finance-attest',json=verify(cid),headers=auth('A:owner:finance')).status_code==403
    assert c.get('/v1/outcome-economics/dA',headers=auth('B:reader:viewer')).status_code==404
    assert c.get('/v1/outcome-economics/dA').status_code==401

def test_sequence_and_idempotency(fixture):
    c,_=fixture;cid=prepare(c)
    assert c.post('/v1/outcome-economics/plan',json=plan(),headers=auth()).status_code==201
    bad={**verify(cid),'expected_seq':100,'request_id':'req_bad_sequence_01'}
    assert c.post('/v1/outcome-economics/dA/finance-attest',json=bad,headers=auth('A:controller:finance')).status_code==409
    good=verify(cid)
    assert c.post('/v1/outcome-economics/dA/finance-attest',json=good,headers=auth('A:controller:finance')).status_code==201
    assert c.post('/v1/outcome-economics/dA/finance-attest',json=good,headers=auth('A:controller:finance')).status_code==201
    again={**claim(),'expected_seq':3,'request_id':'req_new_claim_02'}
    assert c.post('/v1/outcome-economics/dA/report',json=again,headers=auth()).status_code==409

def test_tamper_detected(fixture):
    c,Session=fixture;prepare(c)
    with Session() as s:
        row=s.scalar(select(OutcomeEvent).where(OutcomeEvent.event_type=='outcome.benefit_reported'))
        row.payload={**row.payload,'reported_cents':123};s.commit()
    assert c.get('/v1/outcome-economics/dA',headers=auth()).status_code==409

def test_invalid_source_no_causal_inference(fixture):
    c,_=fixture;c.post('/v1/outcome-economics/plan',json=plan(),headers=auth())
    bad={**claim(),'attribution_method':'definitely_ai','request_id':'invalid_attr_01'}
    assert c.post('/v1/outcome-economics/dA/report',json=bad,headers=auth()).status_code==422
    bad={**claim(),'period':'2026-09','request_id':'invalid_period_01'}
    assert c.post('/v1/outcome-economics/dA/report',json=bad,headers=auth()).status_code==422

def test_ui_integration():
    from pathlib import Path
    base=Path(__file__).resolve().parents[1]
    s=(base/'ui'/'app.py').read_text()
    assert "'Decision Infrastructure':['Outcome Economics'" in s
    assert "elif page=='Outcome Economics':" in s
