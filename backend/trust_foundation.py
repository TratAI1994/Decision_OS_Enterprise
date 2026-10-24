"""R9.5 trust foundation. Evaluation attestation != funding authorization.

Snapshots are append-only at application/DB-trigger level. Optional Ed25519 signatures
are authoritative only when an independently protected verification key is used.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON
from .db import Base
from .intelligence import DecisionRecord
from .decision_events import DecisionEvent, verify_chain, replay, canonical

class TrustSnapshot(Base):
    __tablename__='di_trust_snapshots'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    decision_version=Column(Integer,nullable=False)
    attestation_event_id=Column(String(48),nullable=False,unique=True)
    created_at=Column(DateTime(timezone=True),nullable=False)
    created_by=Column(String(120),nullable=False)
    snapshot=Column(JSON,nullable=False)
    digest=Column(String(64),nullable=False)
    signature=Column(String(256),nullable=True)
    key_fingerprint=Column(String(64),nullable=True)
    __table_args__=(UniqueConstraint('tenant_id','decision_id','decision_version',name='uq_di_trust_version'),)

class KillSignal(Base):
    __tablename__='di_kill_signal_events'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    snapshot_id=Column(String(48),ForeignKey('di_trust_snapshots.id'),nullable=False)
    observed_at=Column(DateTime(timezone=True),nullable=False)
    actor_id=Column(String(120),nullable=False)
    metric=Column(String(160),nullable=False)
    value=Column(String(80),nullable=False)
    source_ref=Column(String(500),nullable=False)
    assessment=Column(JSON,nullable=False)
    request_id=Column(String(100),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','request_id',name='uq_di_kill_req'),)

class FreezeRequest(BaseModel):
    expected_seq:int=Field(ge=2)
    attestation_event_id:str=Field(min_length=6,max_length=48)
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class SignalRequest(BaseModel):
    snapshot_id:str=Field(min_length=6,max_length=48)
    metric:str=Field(min_length=1,max_length=160)
    value:float=Field(allow_inf_nan=False)
    source_ref:str=Field(min_length=5,max_length=500)
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

def document_hash(doc:dict)->str:
    return hashlib.sha256(canonical(doc).encode('utf-8')).hexdigest()

def _read_signer():
    path=os.getenv('DECISION_OS_ED25519_PRIVATE_KEY_FILE')
    if not path:return None
    from cryptography.hazmat.primitives import serialization
    with open(path,'rb') as f:
        key=serialization.load_pem_private_key(f.read(),password=None)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if not isinstance(key,Ed25519PrivateKey):raise ValueError('Expected Ed25519 private key')
    return key

def _read_verifier():
    path=os.getenv('DECISION_OS_ED25519_PUBLIC_KEY_FILE')
    if not path:return None
    from cryptography.hazmat.primitives import serialization
    with open(path,'rb') as f:
        key=serialization.load_pem_public_key(f.read())
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if not isinstance(key,Ed25519PublicKey):raise ValueError('Expected Ed25519 public key')
    return key

def public_fingerprint(key):
    from cryptography.hazmat.primitives import serialization
    return hashlib.sha256(key.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)).hexdigest()

def sign_digest(digest:str)->tuple[str|None,str|None]:
    key=_read_signer()
    if key is None:return None,None
    return base64.b64encode(key.sign(bytes.fromhex(digest))).decode(),public_fingerprint(key.public_key())

def verify_snapshot(s:TrustSnapshot)->dict:
    if document_hash(s.snapshot)!=s.digest:return {'valid':False,'assurance':'FAILED_DIGEST'}
    if not s.signature:return {'valid':True,'assurance':'HASH_ONLY_NOT_SIGNED'}
    key=_read_verifier()
    if key is None:return {'valid':False,'assurance':'SIGNATURE_UNVERIFIABLE_NO_PUBLIC_KEY'}
    if public_fingerprint(key)!=s.key_fingerprint:return {'valid':False,'assurance':'SIGNING_KEY_MISMATCH'}
    try:key.verify(base64.b64decode(s.signature,validate=True),bytes.fromhex(s.digest))
    except Exception:
        # Includes cryptography.exceptions.InvalidSignature. No cryptographic errors leak to users.
        return {'valid':False,'assurance':'INVALID_SIGNATURE'}
    return {'valid':True,'assurance':'SIGNATURE_VERIFIED_LOCAL_KEY_NOT_EXTERNALLY_ANCHORED'}

def compare_criterion(criteria:dict,metric:str,value:float):
    matches=[]
    for c in criteria:
        if c.get('metric')!=metric:continue
        limit=c['threshold'];op=c['operator']
        breached={'lt':value<limit,'lte':value<=limit,'gt':value>limit,'gte':value>=limit}[op]
        matches.append({'metric':metric,'operator':op,'threshold':limit,'breached':breached,
                        'window_days':c['window_days'],'action':c['required_action'],
                        'status':'REVIEW_CANDIDATE' if breached else 'WITHIN_THRESHOLD',
                        'window_verified':False})
    return matches

def build_router(identity,session,require):
    router=APIRouter(prefix='/v1/trust-foundation',tags=['R9.5 Trust Foundation'])
    def owns(db,actor,did):
        d=db.scalar(select(DecisionRecord).where(DecisionRecord.id==did,DecisionRecord.tenant_id==actor.tenant))
        if d is None:raise HTTPException(404,'Decision not found')
        return d
    def ordered(db,actor,did):
        return list(db.scalars(select(DecisionEvent).where(DecisionEvent.decision_id==did,DecisionEvent.tenant_id==actor.tenant).order_by(DecisionEvent.seq)).all())
    def present(s):
        return {'id':s.id,'decision_id':s.decision_id,'decision_version':s.decision_version,
                'snapshot':s.snapshot,'digest':s.digest,'signature_present':bool(s.signature),
                'key_fingerprint':s.key_fingerprint,'integrity':verify_snapshot(s),
                'caveat':'Evaluation-attestation snapshot only. NOT an authoritative funding/deployment approval or external WORM anchor.'}
    @router.post('/{did}/freeze',status_code=201)
    def freeze(did:str,body:FreezeRequest,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','risk'});owns(db,actor,did)
        if db.bind.dialect.name=='postgresql':
            db.execute(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did).with_for_update()).first()
        rows=ordered(db,actor,did)
        if not verify_chain(rows)['valid']:raise HTTPException(409,'Upstream event chain invalid')
        if len(rows)!=body.expected_seq:raise HTTPException(409,'Event sequence changed')
        state=replay(rows)
        if state['status']!='approved' or rows[-1].id!=body.attestation_event_id or rows[-1].event_type!='decision.evaluation_attested':
            raise HTTPException(409,'Must freeze the latest independently attested evaluation version')
        if actor.user in (state['author_id'],state['owner_id']):raise HTTPException(403,'Separation of duties')
        existing=db.scalar(select(TrustSnapshot).where(TrustSnapshot.tenant_id==actor.tenant,
            TrustSnapshot.decision_id==did,TrustSnapshot.decision_version==state['version']))
        if existing:
            if existing.attestation_event_id==body.attestation_event_id and verify_snapshot(existing)['valid']:return present(existing)
            raise HTTPException(409,'Frozen version conflict or integrity failure')
        snap={'schema':'decision-os/trust-snapshot/v1','tenant':actor.tenant,'decision_id':did,
              'decision_version':state['version'],'evaluation_attested_by':state['approved_by'],
              'attestation_event_id':rows[-1].id,'attestation_event_hash':rows[-1].event_hash,
              'event_chain_head':rows[-1].event_hash,'baseline':state['snapshot'],
              'context_limitations':['Evidence IDs and policy version are captured as R7 assertions; external source bytes and authoritative funding approval are not included.'],
              'frozen_at':datetime.now(timezone.utc).isoformat()}
        dig=document_hash(snap)
        try:sig,fp=sign_digest(dig)
        except (OSError,ValueError) as exc:raise HTTPException(503,'Signing configuration unavailable') from exc
        s=TrustSnapshot(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=did,
                        decision_version=state['version'],attestation_event_id=rows[-1].id,
                        created_at=datetime.now(timezone.utc),created_by=actor.user,snapshot=snap,digest=dig,signature=sig,key_fingerprint=fp)
        db.add(s)
        try:db.flush();db.commit()
        except Exception as exc:
            db.rollback();raise HTTPException(409,'Concurrent snapshot append or database constraint failure') from exc
        return present(s)
    @router.get('/{did}/snapshots')
    def snapshots(did:str,actor=Depends(identity),db:Session=Depends(session)):
        owns(db,actor,did)
        data=list(db.scalars(select(TrustSnapshot).where(TrustSnapshot.tenant_id==actor.tenant,TrustSnapshot.decision_id==did).order_by(TrustSnapshot.decision_version)).all())
        return {'snapshots':[present(s) for s in data]}
    @router.post('/{did}/kill-signal',status_code=201)
    def signal(did:str,body:SignalRequest,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor','risk'});owns(db,actor,did)
        prior=db.scalar(select(KillSignal).where(KillSignal.tenant_id==actor.tenant,KillSignal.request_id==body.request_id))
        if prior:
            if prior.decision_id==did and prior.snapshot_id==body.snapshot_id and prior.metric==body.metric and float(prior.value)==body.value and prior.source_ref==body.source_ref:
                return {'id':prior.id,'assessment':prior.assessment}
            raise HTTPException(409,'Request ID collision')
        snap=db.scalar(select(TrustSnapshot).where(TrustSnapshot.id==body.snapshot_id,TrustSnapshot.tenant_id==actor.tenant,TrustSnapshot.decision_id==did))
        if snap is None:raise HTTPException(404,'Snapshot not found')
        if not verify_snapshot(snap)['valid']:raise HTTPException(409,'Snapshot integrity failed')
        matches=compare_criterion(snap.snapshot['baseline']['kill_criteria'],body.metric,body.value)
        if not matches:raise HTTPException(422,'Metric not in approval-time kill criteria')
        assessment={'matches':matches,'provenance_status':'USER_SUBMITTED_NOT_INDEPENDENTLY_VERIFIED',
                    'governance':'Advisory review candidate ONLY; no automatic halt, no sustained-window claim, and no policy bypass.'}
        row=KillSignal(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=did,snapshot_id=snap.id,
            observed_at=datetime.now(timezone.utc),actor_id=actor.user,metric=body.metric,value=str(body.value),
            source_ref=body.source_ref,assessment=assessment,request_id=body.request_id)
        db.add(row)
        try:db.commit()
        except Exception as exc:db.rollback();raise HTTPException(409,'Concurrent append error') from exc
        return {'id':row.id,'assessment':assessment}
    @router.get('/{did}/certification')
    def certify(did:str,actor=Depends(identity),db:Session=Depends(session)):
        owns(db,actor,did)
        rows=ordered(db,actor,did);chain=verify_chain(rows)
        shots=list(db.scalars(select(TrustSnapshot).where(TrustSnapshot.tenant_id==actor.tenant,TrustSnapshot.decision_id==did)).all())
        snaps_ok=bool(shots) and all(verify_snapshot(s)['valid'] for s in shots)
        checks={'r7_event_chain_consistent':chain['valid'],
                'r95_snapshot_exists_and_digest_valid':snaps_ok,
                'independent_signature_verified':bool(shots) and all(verify_snapshot(s)['assurance']=='SIGNATURE_VERIFIED_LOCAL_KEY_NOT_EXTERNALLY_ANCHORED' for s in shots),
                'approval_time_atomic_business_record':'NOT_IMPLEMENTED',
                'external_anchor_or_worm':'NOT_IMPLEMENTED',
                'automatic_kill_window_enforcement':'NOT_IMPLEMENTED',
                'production_devsecops_deployment':'NOT_TESTED',
                'aiops_live_observation':'NOT_TESTED',
                'independent_erp_gl_reconciliation':'NOT_TESTED',
                'governed_operator_execution_and_rollback':'NOT_IMPLEMENTED',
                'end_to_end_replay':'NOT_TESTED'}
        return {'decision_id':did,'certified':all(v is True for v in checks.values()),'checks':checks,
                'note':'A partial trust snapshot can never certify the 13-stage production scenario.'}
    return router
