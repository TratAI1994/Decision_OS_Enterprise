"""Executable isolated R7 tests against real FastAPI endpoints and SQLite ORM.
SQLite tests do not claim PostgreSQL trigger/WORM guarantees.
"""
import uuid
import pytest
from fastapi import FastAPI, HTTPException, Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db import Base, Initiative
from backend.intelligence import DecisionRecord
from backend.decision_events import build_router, DecisionEvent, replay, verify_chain, digest, material

@pytest.fixture
def env():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as db:
        for tenant in ['A','B']:
            iid='i'+tenant;did='d'+tenant
            db.add(Initiative(id=iid,tenant_id=tenant,name='Initiative '+tenant,owner='owner'))
            db.flush()
            db.add(DecisionRecord(id=did,tenant_id=tenant,initiative_id=iid,title='Cloud investment',option_chosen='Expand',rationale='test rationale',owner='owner',state='proposed'))
        db.commit()
    app=FastAPI()
    def identity(authorization: str | None=Header(default=None)):
        if not authorization:raise HTTPException(401,'Missing')
        tenant,user,role=authorization.replace('Bearer ','').split(':')
        return type('Actor',(),{'tenant':tenant,'user':user,'role':role})()
    def session():
        with Session() as db:yield db
    def require(actor,roles):
        if actor.role not in roles:raise HTTPException(403,'Role denied')
    app.include_router(build_router(identity,session,require))
    yield TestClient(app),Session
    engine.dispose()

def auth(who='A:writer:editor'):
    return {'Authorization':'Bearer '+who}

def payload():
    return {'decision_id':'dA','owner_id':'business_owner','recommendation':'Reduce capacity for trial only',
      'rationale':'Measured pilot, reviewed cost and risk','expected_outcome':'Cut spend 10% without SLA regression',
      'evidence_refs':['evidence:pilot-run-1'],'assumptions':['Usage remains below ceiling'],
      'kill_criteria':[{'metric':'latency_p95','operator':'gt','threshold':2500,'window_days':7,'required_action':'review'}],
      'review_due':'2026-12-01','policy_version':'policy-1','request_id':'fixed_request_0001'}

def make_baseline(client):
    r=client.post('/v1/decision-events/begin',json=payload(),headers=auth())
    assert r.status_code==201,r.text
    return r

def test_begin_and_replay_and_hash(env):
    c,_=env;make_baseline(c)
    r=c.get('/v1/decision-events/dA',headers=auth());assert r.status_code==200
    obj=r.json();assert obj['state']['status']=='draft';assert obj['verification']['valid'];assert obj['events'][0]['seq']==1
    assert obj['state']['snapshot']['kill_criteria'][0]['threshold']==2500

def test_self_approval_blocked(env):
    c,_=env;make_baseline(c)
    data={'expected_seq':1,'confirmation':'I independently reviewed this decision snapshot and its evidence limitations.','request_id':'approve_request_001'}
    r=c.post('/v1/decision-events/dA/attest',json=data,headers=auth('A:writer:reviewer'))
    assert r.status_code==403 and 'Separation of Duties' in str(r.json())
    r=c.post('/v1/decision-events/dA/attest',json=data,headers=auth('A:business_owner:reviewer'))
    assert r.status_code==403

def test_independent_attest_and_duplicate_stale(env):
    c,_=env;make_baseline(c)
    data={'expected_seq':1,'confirmation':'I independently reviewed this decision snapshot and its evidence limitations.','request_id':'approve_request_002'}
    r=c.post('/v1/decision-events/dA/attest',json=data,headers=auth('A:reviewer:reviewer'));assert r.status_code==201,r.text
    assert c.get('/v1/decision-events/dA',headers=auth()).json()['state']['status']=='approved'
    assert c.post('/v1/decision-events/dA/attest',json={**data,'request_id':'approve_request_003'},headers=auth('A:another:reviewer')).status_code==409
    assert c.post('/v1/decision-events/dA/attest',json=data,headers=auth('A:reviewer:reviewer')).status_code==201

def test_tenant_and_role_isolation(env):
    c,_=env;make_baseline(c)
    assert c.get('/v1/decision-events/dA',headers=auth('B:auditor:viewer')).status_code==404
    assert c.post('/v1/decision-events/begin',json={**payload(),'request_id':'another_req_090'},headers=auth('A:viewer:viewer')).status_code==403
    assert c.get('/v1/decision-events/dA').status_code==401

def test_amendment_preserves_history(env):
    c,_=env;make_baseline(c)
    data={'expected_seq':1,'rationale':'New pilot results changed assumptions','assumptions':['Use below ceiling','Pricing revised'],
          'evidence_refs':['evidence:new-1'],'request_id':'amend_request_001'}
    r=c.post('/v1/decision-events/dA/amend',json=data,headers=auth());assert r.status_code==201,r.text
    history=c.get('/v1/decision-events/dA',headers=auth()).json()
    assert history['state']['version']==2
    assert len(history['events'])==2
    assert history['events'][0]['payload']['assumptions']==['Usage remains below ceiling']
    assert history['events'][1]['prev_hash']==history['events'][0]['event_hash']
    assert history['verification']['valid']

def test_stale_revision_conflict(env):
    c,_=env;make_baseline(c)
    data={'expected_seq':2,'rationale':'New pilot results changed assumptions','request_id':'amend_request_002'}
    assert c.post('/v1/decision-events/dA/amend',json=data,headers=auth()).status_code==409

def test_idempotency_conflicting_payload(env):
    c,_=env;make_baseline(c)
    assert c.post('/v1/decision-events/begin',json=payload(),headers=auth()).status_code==201
    bad={**payload(),'recommendation':'Run entirely different strategy'}
    assert c.post('/v1/decision-events/begin',json=bad,headers=auth()).status_code==409

def test_tamper_detects_modified_payload(env):
    c,Session=env;make_baseline(c)
    with Session() as db:
        row=db.scalar(select(DecisionEvent).where(DecisionEvent.decision_id=='dA'))
        row.payload={**row.payload,'expected_outcome':'Tampered outcome'}
        db.commit()
    r=c.get('/v1/decision-events/dA',headers=auth());assert r.status_code==409

def test_tamper_detects_missing_sequence(env):
    c,Session=env;make_baseline(c)
    with Session() as db:
        row=db.scalar(select(DecisionEvent).where(DecisionEvent.decision_id=='dA'))
        row.seq=4;db.commit()
    assert c.get('/v1/decision-events/dA',headers=auth()).status_code==409

def test_unknown_decision_no_forged_record(env):
    c,_=env
    assert c.post('/v1/decision-events/begin',json={**payload(),'decision_id':'nonexistent'},headers=auth()).status_code==404

def test_r7_ui_route():
    from pathlib import Path
    s=(Path(__file__).resolve().parents[1]/'ui'/'app.py').read_text()
    assert "'Decision Infrastructure':['Decision Event Ledger','Decision Ledger']" in s
    assert "elif page=='Decision Event Ledger':" in s
    assert 'form_submit_button' in (Path(__file__).resolve().parents[1]/'ui'/'decision_event_console.py').read_text()
