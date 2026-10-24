"""R9.7 optional audited, append-only observation intake. No privileged verification endpoint.

Hook `build_router` into existing backend/api.py and import model before migration.
"""
from __future__ import annotations
import hashlib
import json
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON
from .db import Base
from .intelligence import DecisionRecord
from .trust_foundation import TrustSnapshot, verify_snapshot
from .kill_window import Observation, as_decimal, evaluate_window

class KillWindowSample(Base):
    __tablename__='di_kill_window_samples'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    snapshot_id=Column(String(48),ForeignKey('di_trust_snapshots.id'),nullable=False)
    metric=Column(String(160),nullable=False)
    observed_at=Column(DateTime(timezone=True),nullable=False)
    received_at=Column(DateTime(timezone=True),nullable=False)
    source_ref=Column(String(500),nullable=False)
    source_identity=Column(String(200),nullable=False,default='')
    value=Column(String(90),nullable=False)
    verification=Column(String(40),nullable=False,default='SUBMITTED_UNVERIFIED')
    submitted_by=Column(String(120),nullable=False)
    request_id=Column(String(100),nullable=False)
    payload_digest=Column(String(64),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','request_id',name='uq_di_kw_request'),)

class SubmitSample(BaseModel):
    snapshot_id:str=Field(min_length=6,max_length=48)
    metric:str=Field(min_length=1,max_length=160)
    value:str=Field(min_length=1,max_length=90)
    observed_at:datetime
    source_ref:str=Field(min_length=5,max_length=500)
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

def normalized_payload(tenant, did, actor, body:SubmitSample):
    if body.observed_at.tzinfo is None:
        raise ValueError('Observed timestamp must include timezone')
    obs=body.observed_at.astimezone(timezone.utc)
    if obs > datetime.now(timezone.utc):
        raise ValueError('Future observations are not allowed')
    return {'tenant':tenant,'decision':did,'snapshot':body.snapshot_id,'metric':body.metric,
            'value':str(as_decimal(body.value)), 'observed_at':obs.isoformat(),
            'source_ref':body.source_ref,'submitted_by':actor}

def build_router(identity, session, require):
    router=APIRouter(prefix='/v1/kill-windows',tags=['R9.7 Kill Windows'])
    def lookup(db, actor, did, sid):
        decision=db.scalar(select(DecisionRecord).where(DecisionRecord.id==did,DecisionRecord.tenant_id==actor.tenant))
        if decision is None:raise HTTPException(404,'Decision not found')
        snap=db.scalar(select(TrustSnapshot).where(TrustSnapshot.id==sid,TrustSnapshot.tenant_id==actor.tenant,TrustSnapshot.decision_id==did))
        if snap is None:raise HTTPException(404,'Trust snapshot not found')
        if not verify_snapshot(snap)['valid']:raise HTTPException(409,'Snapshot integrity failure')
        return snap
    @router.post('/{did}/observations',status_code=201)
    def append(did:str, body:SubmitSample, actor=Depends(identity),db:Session=Depends(session)):
        require(actor, {'admin','lead','editor','risk'})
        snap=lookup(db,actor,did,body.snapshot_id)
        criteria=snap.snapshot.get('baseline',{}).get('kill_criteria',[])
        if not any(c.get('metric')==body.metric for c in criteria):raise HTTPException(422,'Metric is not in frozen criteria')
        try: payload=normalized_payload(actor.tenant,did,actor.user,body)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        existing=db.scalar(select(KillWindowSample).where(KillWindowSample.tenant_id==actor.tenant,KillWindowSample.request_id==body.request_id))
        if existing:
            if existing.payload_digest!=digest:raise HTTPException(409,'Idempotency key reused for different payload')
            return {'id':existing.id,'verification':existing.verification,'source_identity':existing.source_identity,'idempotent_replay':True}
        sample=KillWindowSample(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=did,
            snapshot_id=body.snapshot_id,metric=body.metric,value=payload['value'],observed_at=body.observed_at,
            received_at=datetime.now(timezone.utc),source_ref=body.source_ref,source_identity='',
            verification='SUBMITTED_UNVERIFIED',submitted_by=actor.user,request_id=body.request_id,payload_digest=digest)
        db.add(sample)
        try:db.commit()
        except Exception as exc:
            db.rollback()
            raise HTTPException(409,'Concurrent or duplicate append conflict') from exc
        return {'id':sample.id,'verification':sample.verification,'source_identity':'','idempotent_replay':False}
    @router.get('/{did}/assessment/{snapshot_id}')
    def assess(did:str,snapshot_id:str,actor=Depends(identity),db:Session=Depends(session)):
        snap=lookup(db,actor,did,snapshot_id)
        criteria=snap.snapshot.get('baseline',{}).get('kill_criteria',[])
        rows=list(db.scalars(select(KillWindowSample).where(KillWindowSample.tenant_id==actor.tenant,
            KillWindowSample.decision_id==did,KillWindowSample.snapshot_id==snapshot_id)
            .order_by(KillWindowSample.observed_at)).all())
        result=[]
        for criterion in criteria:
            items=[Observation(r.observed_at if r.observed_at.tzinfo else r.observed_at.replace(tzinfo=timezone.utc),
                   Decimal(r.value),r.source_ref,r.verification,r.source_identity) for r in rows if r.metric==criterion.get('metric')]
            try:
                verdict=evaluate_window(criterion,items,evaluated_at=datetime.now(timezone.utc),verified_source_ids=frozenset())
            except (ValueError,KeyError) as exc:
                verdict={'metric':criterion.get('metric'),'status':'INVALID_FROZEN_RULE','reason':str(exc),'candidate_only':True}
            result.append(verdict)
        return {'decision_id':did,'snapshot_id':snapshot_id,'observations':len(rows),'assessments':result,
                'note':'No live source verifier is connected. All submitted observations remain unverified; no automatic action or execution authorized.'}
    return router
