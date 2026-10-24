import uuid
import pytest
from fastapi import FastAPI,HTTPException,Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.db import Base,Initiative
from backend.intelligence import DecisionRecord
from backend.decision_events import build_router as r7router,DecisionEvent
from backend.trust_foundation import build_router,TrustSnapshot,document_hash,verify_snapshot,compare_criterion

@pytest.fixture
def setup():
    en=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(en)
    Session=sessionmaker(bind=en,expire_on_commit=False)
    with Session() as db:
        for t in ('A','B'):
            db.add(Initiative(id='i'+t,tenant_id=t,name='Demo',owner='owner'));db.flush()
            db.add(DecisionRecord(id='d'+t,tenant_id=t,initiative_id='i'+t,title='AI Spend',option_chosen='Pause',rationale='test',owner='owner',state='proposed'))
        db.commit()
    app=FastAPI()
    def identity(authorization:str|None=Header(default=None)):
        if not authorization:raise HTTPException(401)
        t,u,r=authorization.replace('Bearer ','').split(':')
        return type('Actor',(),dict(tenant=t,user=u,role=r))()
    def session():
        with Session() as db:yield db
    def require(a,roles):
        if a.role not in roles:raise HTTPException(403)
    app.include_router(r7router(identity,session,require))
    app.include_router(build_router(identity,session,require))
    yield TestClient(app),Session
    en.dispose()

def h(actor='A:writer:editor'):return {'Authorization':'Bearer '+actor}

def recorded(c):
    r=c.post('/v1/decision-events/begin',headers=h(),json={
        'decision_id':'dA','owner_id':'owner','recommendation':'Reduce capacity for a safe trial',
        'rationale':'Controlled comparison and cost review','expected_outcome':'10 percent savings with no incident',
        'evidence_refs':['pilot:123'],'assumptions':['Usage stays below cap'],
        'kill_criteria':[{'metric':'latency_p95','operator':'gt','threshold':2500,'window_days':7,'required_action':'review'}],
        'review_due':'2026-12-01','policy_version':'v1','request_id':'create_request_0001'})
    assert r.status_code==201,r.text
    return r.json()

def attested(c):
    recorded(c)
    r=c.post('/v1/decision-events/dA/attest',headers=h('A:reviewer:reviewer'),json={
        'expected_seq':1,'confirmation':'I independently reviewed this decision snapshot and its evidence limitations.',
        'request_id':'review_request_0001'})
    assert r.status_code==201,r.text
    return r.json()

def frozen(c):
    a=attested(c)
    r=c.post('/v1/trust-foundation/dA/freeze',headers=h('A:reviewer:reviewer'),json={
        'expected_seq':2,'attestation_event_id':a['id'],'request_id':'freeze_request_001'})
    assert r.status_code==201,r.text
    return r.json()

def test_snapshot_matches_baseline(setup):
    c,_=setup;s=frozen(c)
    assert s['integrity']['valid']
    assert s['integrity']['assurance']=='HASH_ONLY_NOT_SIGNED'
    assert s['snapshot']['baseline']['assumptions']==['Usage stays below cap']
    assert s['snapshot']['baseline']['kill_criteria'][0]['threshold']==2500

def test_freeze_requires_review(setup):
    c,_=setup;a=recorded(c)
    r=c.post('/v1/trust-foundation/dA/freeze',headers=h('A:reviewer:reviewer'),json={'expected_seq':1,'attestation_event_id':a['id'],'request_id':'freeze_request_002'})
    assert r.status_code==422 # schema requires seq>=2

def test_self_freeze_denied(setup):
    c,_=setup;a=attested(c)
    r=c.post('/v1/trust-foundation/dA/freeze',headers=h('A:writer:reviewer'),json={'expected_seq':2,'attestation_event_id':a['id'],'request_id':'freeze_request_003'})
    assert r.status_code==403

def test_cross_tenant_isolation(setup):
    c,_=setup;frozen(c)
    assert c.get('/v1/trust-foundation/dA/snapshots',headers=h('B:auditor:viewer')).status_code==404
    assert c.get('/v1/trust-foundation/dA/certification',headers=h('B:auditor:viewer')).status_code==404

def test_tamper_detection(setup):
    c,Session=setup;frozen(c)
    with Session() as db:
        s=db.scalar(select(TrustSnapshot).where(TrustSnapshot.decision_id=='dA'))
        s.snapshot={**s.snapshot,'baseline':{**s.snapshot['baseline'],'recommendation':'tampered'}}
        db.commit()
    got=c.get('/v1/trust-foundation/dA/snapshots',headers=h()).json()['snapshots'][0]
    assert got['integrity']['assurance']=='FAILED_DIGEST'

def test_signal_is_only_candidate(setup):
    c,_=setup;s=frozen(c)
    r=c.post('/v1/trust-foundation/dA/kill-signal',headers=h(),json={
        'snapshot_id':s['id'],'metric':'latency_p95','value':3100,'source_ref':'telemetry:claimed-123',
        'request_id':'signal_request_001'})
    assert r.status_code==201,r.text
    assert r.json()['assessment']['matches'][0]['status']=='REVIEW_CANDIDATE'
    assert not r.json()['assessment']['matches'][0]['window_verified']

def test_invalid_metric_blocked(setup):
    c,_=setup;s=frozen(c)
    r=c.post('/v1/trust-foundation/dA/kill-signal',headers=h(),json={
        'snapshot_id':s['id'],'metric':'made_up','value':3100,'source_ref':'telemetry:claimed-123',
        'request_id':'signal_request_002'})
    assert r.status_code==422

def test_not_certified_without_operational_proof(setup):
    c,_=setup;frozen(c)
    x=c.get('/v1/trust-foundation/dA/certification',headers=h()).json()
    assert x['certified'] is False
    assert x['checks']['production_devsecops_deployment']=='NOT_TESTED'

def test_duplicate_freeze_idempotent(setup):
    c,_=setup;s=frozen(c)
    a=s['snapshot']['attestation_event_id']
    r=c.post('/v1/trust-foundation/dA/freeze',headers=h('A:reviewer:reviewer'),json={'expected_seq':2,'attestation_event_id':a,'request_id':'freeze_request_001'})
    assert r.status_code==201 and r.json()['id']==s['id']

def test_status_cannot_infer_causality():
    assert compare_criterion([{'metric':'m','operator':'gt','threshold':2,'window_days':30,'required_action':'review'}],'m',3)[0]['window_verified'] is False
