from datetime import datetime, timezone, timedelta
from hashlib import sha256
from types import SimpleNamespace
import hmac
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from backend.db import Base
from backend.authenticated_ingestion import (KeyRegistry,AuthenticatedEvidence,signature_message,
    verify_collector,check_stored,build_router)

KEY='a1'*32
REG=KeyRegistry({'tenantA':{'jenkins':{'build-key':KEY}},'tenantB':{'jenkins':{'build-key':'b2'*32}}})

def headers(payload=b'{"result":"passed"}',tenant='tenantA',source='jenkins',key_id='build-key',nonce='randomnonce123',timestamp=None,source_record='build-100'):
    timestamp=timestamp or datetime.now(timezone.utc).isoformat()
    digest=sha256(payload).hexdigest()
    signature=hmac.new(bytes.fromhex(KEY),signature_message(timestamp,nonce,tenant,source,source_record,digest),'sha256').hexdigest()
    return {'x-tenant':tenant,'x-source':source,'x-key-id':key_id,'x-source-record':source_record,
            'x-timestamp':timestamp,'x-nonce':nonce,'x-content-sha256':digest,'x-signature':signature}

@pytest.fixture
def setup():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine)
    def session():
        with factory() as db:yield db
    def identity():return SimpleNamespace(tenant='tenantA',user='auditor',role='auditor')
    def require(actor,allowed):
        if actor.role not in allowed:raise HTTPException(403,'Forbidden')
    app=FastAPI()
    app.include_router(build_router(identity,session,require,REG))
    with TestClient(app) as client: yield client, factory
    engine.dispose()

def test_happy_path_and_integrity(setup):
    client,dbfactory=setup
    data=b'\x00real bytes\xff'
    r=client.post('/v1/source-evidence/ingest',content=data,headers=headers(data))
    assert r.status_code==201,r.text
    result=r.json()
    assert result['business_validated'] is False
    assert result['external_anchor_verified'] is False
    fetched=client.get('/v1/source-evidence/'+result['id'])
    assert fetched.status_code==200 and fetched.json()['integrity_valid'] is True
    with dbfactory() as db:
        item=db.scalar(select(AuthenticatedEvidence))
        assert bytes(item.payload_bytes)==data
        assert check_stored(item)

def test_replay_rejected(setup):
    client,_=setup
    head=headers()
    assert client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=head).status_code==201
    assert client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=head).status_code==409

def test_forged_signature_rejected(setup):
    client,_=setup
    head=headers();head['x-signature']='0'*64
    assert client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=head).status_code==401

def test_wrong_tenant_key_rejected(setup):
    client,_=setup
    assert client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=headers(tenant='tenantB')).status_code==401

def test_modified_body_rejected(setup):
    client,_=setup
    assert client.post('/v1/source-evidence/ingest',content=b'changed bytes',headers=headers()).status_code==422

def test_expired_signature_rejected(setup):
    client,_=setup
    ts=(datetime.now(timezone.utc)-timedelta(minutes=7)).isoformat()
    assert client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=headers(timestamp=ts)).status_code==422

def test_nonce_only_unique_per_tenant_source_key(setup):
    client,_=setup
    data=b'{"result":"passed"}'
    assert client.post('/v1/source-evidence/ingest',content=data,headers=headers(nonce='another-nonce-000')).status_code==201
    # Nonce cannot be reused to sign a different source record
    assert client.post('/v1/source-evidence/ingest',content=data,headers=headers(nonce='another-nonce-000',source_record='build-101')).status_code==409

def test_tamper_detection(setup):
    client,factory=setup
    r=client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=headers())
    evidence_id=r.json()['id']
    with factory() as db:
        entry=db.get(AuthenticatedEvidence,evidence_id)
        entry.payload_bytes=b'forged'
        db.commit()
    assert client.get('/v1/source-evidence/'+evidence_id).json()['integrity_valid'] is False

def test_cross_tenant_read_denied(setup):
    client,_=setup
    r=client.post('/v1/source-evidence/ingest',content=b'{"result":"passed"}',headers=headers())
    # Simulate a tenant B authenticated app request with a separately mounted router
    from fastapi import FastAPI
    from sqlalchemy.orm import Session
    _,factory=setup
    def session():
        with factory() as db: yield db
    def identity(): return SimpleNamespace(tenant='tenantB',role='auditor')
    def require(actor,roles): assert actor.role in roles
    app=FastAPI();app.include_router(build_router(identity,session,require,REG))
    with TestClient(app) as other:
        assert other.get('/v1/source-evidence/'+r.json()['id']).status_code==404

def test_short_key_refused():
    with pytest.raises(ValueError):KeyRegistry({'t':{'s':{'key':'ff'*3}}})

def test_nan_or_unexpected_verification_flag_not_accepted(setup):
    client,_=setup
    payload=b'{"verification_status":"verified"}'
    head=headers(payload,nonce='signeddataflag123')
    response=client.post('/v1/source-evidence/ingest',content=payload,headers=head)
    assert response.status_code==201
    assert response.json()['business_validated'] is False

def test_unsigned_payload_rejected(setup):
    client,_=setup
    response=client.post('/v1/source-evidence/ingest',content=b'abc',headers={'x-tenant':'tenantA'})
    assert response.status_code==422

def test_migration_check_does_not_mutate():
    from backend.migration_r99 import run
    engine=create_engine('sqlite://')
    assert run(engine,apply=False)['table_present'] is False
    with pytest.raises(RuntimeError,match='requires PostgreSQL'):run(engine,apply=True)

def test_successive_distinct_nonces(setup):
    client,factory=setup
    data=b'{"result":"passed"}'
    for n in range(5):
        assert client.post('/v1/source-evidence/ingest',content=data,headers=headers(nonce=f'unique-request-{n}')).status_code==201
    with factory() as db:
        assert len(list(db.scalars(select(AuthenticatedEvidence))))==5
