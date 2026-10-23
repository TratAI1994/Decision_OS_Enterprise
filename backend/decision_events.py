"""R7 provable event-stream slice. No claims of WORM storage or signed approval.

Appended events capture the evaluation of a decision in this *slice*; the existing
funding/Action Packet approval engine remains authoritative for execution.
"""
from __future__ import annotations
import hashlib
import math
import json
import secrets
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, select, func
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .db import Base
from .intelligence import DecisionRecord

PREFIX = '/v1/decision-events'
VERSION = 'r7-slice-1'

class DecisionEvent(Base):
    __tablename__ = 'di_decision_events'
    id = Column(String(48), primary_key=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    decision_id = Column(String(48), ForeignKey('di_decisions.id'), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    event_type = Column(String(32), nullable=False)
    actor_id = Column(String(120), nullable=False)
    actor_role = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSON, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)
    request_id = Column(String(100), nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','decision_id','seq',name='uq_di_event_seq'),
        UniqueConstraint('tenant_id','request_id',name='uq_di_event_request'),
    )

class BeginIn(BaseModel):
    decision_id: str
    owner_id: str = Field(min_length=2,max_length=120)
    recommendation: str = Field(min_length=10,max_length=4000)
    rationale: str = Field(min_length=10,max_length=4000)
    expected_outcome: str = Field(min_length=5,max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list,max_length=40)
    assumptions: list[str] = Field(default_factory=list,max_length=40)
    kill_criteria: list[dict] = Field(min_length=1,max_length=20)
    review_due: str = Field(min_length=8,max_length=40)
    policy_version: str = Field(min_length=1,max_length=128)
    request_id: str = Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class ApproveIn(BaseModel):
    expected_seq: int = Field(ge=1)
    confirmation: str = Field(pattern=r'^I independently reviewed this decision snapshot and its evidence limitations\.$')
    request_id: str = Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class ReviseIn(BaseModel):
    expected_seq: int = Field(ge=1)
    rationale: str = Field(min_length=10,max_length=4000)
    assumptions: list[str] = Field(default_factory=list,max_length=40)
    evidence_refs: list[str] = Field(default_factory=list,max_length=40)
    request_id: str = Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')


def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def digest(prev,doc):
    return hashlib.sha256((prev+'\n'+canonical(doc)).encode('utf-8')).hexdigest()

def material(e):
    at=e.occurred_at.isoformat() if e.occurred_at else ''
    # PostgreSQL may return aware and SQLite naive datetimes; normalize to UTC.
    if at.endswith('+00:00'): at=at[:-6]+'Z'
    elif '+' not in at and not at.endswith('Z'): at+='Z'
    return dict(tenant_id=e.tenant_id,decision_id=e.decision_id,seq=e.seq,
                event_type=e.event_type,actor_id=e.actor_id,actor_role=e.actor_role,
                occurred_at=at,payload=e.payload,request_id=e.request_id)

def as_dict(e):
    return {**material(e),'id':e.id,'prev_hash':e.prev_hash,'event_hash':e.event_hash}

def verify_chain(records):
    previous='GENESIS'
    for idx,e in enumerate(records,1):
        if e.seq!=idx or e.prev_hash!=previous or digest(previous,material(e))!=e.event_hash:
            return {'valid':False,'first_invalid_seq':idx,'event_count':len(records),'meaning':'hash-chain inconsistency detected'}
        previous=e.event_hash
    return {'valid':True,'first_invalid_seq':None,'event_count':len(records),
            'head_hash':previous,'meaning':'locally consistent; not externally anchored or digitally signed'}

def replay(records):
    """Reconstruct authoritative *slice* state only from events, not DecisionRecord.status."""
    state={'status':'not_started','version':0,'owner_id':None,'author_id':None,'approved_by':None,'approved_at':None,
           'snapshot':None,'decision_id':records[0].decision_id if records else None,'history':[]}
    for e in records:
        if e.event_type=='decision.baseline_recorded':
            if state['status']!='not_started':raise ValueError('Unexpected baseline event')
            state.update(status='draft',version=1,owner_id=e.payload['owner_id'],author_id=e.actor_id,snapshot=e.payload)
        elif e.event_type=='decision.amendment_proposed':
            if state['status'] not in ('draft','approved'):raise ValueError('Unexpected amendment event')
            revised={**state['snapshot'],'assumptions':e.payload['assumptions'],'evidence_refs':e.payload['evidence_refs'],
                     'amendment_rationale':e.payload['rationale']}
            state.update(status='draft',version=state['version']+1,author_id=e.actor_id,approved_by=None,approved_at=None,snapshot=revised)
        elif e.event_type=='decision.evaluation_attested':
            if state['status']!='draft' or e.actor_id==state['author_id']:
                raise ValueError('Invalid independent assessment event')
            state.update(status='approved',approved_by=e.actor_id,approved_at=material(e)['occurred_at'])
        else:
            raise ValueError('Unknown event type')
        state['history'].append({'seq':e.seq,'event':e.event_type,'actor':e.actor_id,'hash':e.event_hash})
    return state

def validate_criteria(conditions):
    for c in conditions:
        if not isinstance(c,dict) or set(c)<{'metric','operator','threshold','window_days','required_action'}:
            raise HTTPException(422,'Every kill criterion needs metric/operator/threshold/window_days/required_action')
        if c['operator'] not in ('lt','lte','gt','gte') or c['required_action'] not in ('review','escalate','propose_pause'):
            raise HTTPException(422,'Invalid kill criterion operator/action')
        if (not isinstance(c['threshold'],(int,float)) or isinstance(c['threshold'],bool)
            or not math.isfinite(c['threshold'])
            or not isinstance(c['window_days'],int) or isinstance(c['window_days'],bool)
            or not 1<=c['window_days']<=365):
            raise HTTPException(422,'Invalid threshold/window')


def build_router(identity,session,require):
    router=APIRouter(prefix=PREFIX,tags=['R7 Decision Event Sourcing'])
    def own(db,actor,did):
        row=db.scalar(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did))
        if row is None:raise HTTPException(404,'Decision not found in tenant')
        return row
    def ordered(db,actor,did):
        return list(db.scalars(select(DecisionEvent).where(DecisionEvent.tenant_id==actor.tenant,
            DecisionEvent.decision_id==did).order_by(DecisionEvent.seq)).all())
    def make_event(db,actor,did,kind,payload,request_id,previous):
        now=datetime.now(timezone.utc)
        e=DecisionEvent(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=did,seq=len(previous)+1,
          event_type=kind,actor_id=actor.user,actor_role=actor.role,occurred_at=now,payload=payload,
          prev_hash=previous[-1].event_hash if previous else 'GENESIS',request_id=request_id)
        e.event_hash=digest(e.prev_hash,material(e));db.add(e)
        try:db.flush();db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(409,'Concurrent append or duplicate request; refresh and retry')
        return e
    def existing_request(db,actor,req):
        return db.scalar(select(DecisionEvent).where(DecisionEvent.tenant_id==actor.tenant,DecisionEvent.request_id==req))
    @router.post('/begin',status_code=201)
    def begin(data:BeginIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'})
        own(db,actor,data.decision_id)
        old=existing_request(db,actor,data.request_id)
        payload=data.model_dump(exclude={'decision_id','request_id'})
        validate_criteria(data.kill_criteria)
        if old:
            if old.event_type=='decision.baseline_recorded' and old.decision_id==data.decision_id and old.payload==payload:return as_dict(old)
            raise HTTPException(409,'Request ID collision')
        # PostgreSQL per-decision transaction lock serializes reads/append across workers.
        if db.bind.dialect.name=='postgresql':
            db.execute(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,
                DecisionRecord.id==data.decision_id).with_for_update()).first()
        rows=ordered(db,actor,data.decision_id)
        if rows:raise HTTPException(409,'Decision baseline exists; create an amendment instead')
        return as_dict(make_event(db,actor,data.decision_id,'decision.baseline_recorded',payload,data.request_id,rows))
    @router.post('/{did}/amend',status_code=201)
    def amend(did:str,data:ReviseIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'})
        own(db,actor,did)
        old=existing_request(db,actor,data.request_id)
        payload=data.model_dump(exclude={'expected_seq','request_id'})
        if old:
            if old.event_type=='decision.amendment_proposed' and old.decision_id==did and old.payload==payload:return as_dict(old)
            raise HTTPException(409,'Request ID collision')
        if db.bind.dialect.name=='postgresql':db.execute(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did).with_for_update()).first()
        rows=ordered(db,actor,did)
        if not rows or len(rows)!=data.expected_seq:raise HTTPException(409,'Event sequence conflict')
        if not verify_chain(rows)['valid']:raise HTTPException(409,'Event chain integrity failure')
        replay(rows)
        return as_dict(make_event(db,actor,did,'decision.amendment_proposed',payload,data.request_id,rows))
    @router.post('/{did}/attest',status_code=201)
    def attest(did:str,data:ApproveIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','risk'})
        own(db,actor,did)
        old=existing_request(db,actor,data.request_id)
        if old:
            if old.event_type=='decision.evaluation_attested' and old.decision_id==did:return as_dict(old)
            raise HTTPException(409,'Request ID collision')
        if db.bind.dialect.name=='postgresql':db.execute(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did).with_for_update()).first()
        rows=ordered(db,actor,did)
        if not rows or len(rows)!=data.expected_seq:raise HTTPException(409,'Event sequence conflict')
        if not verify_chain(rows)['valid']:raise HTTPException(409,'Event chain integrity failure')
        state=replay(rows)
        if state['status']!='draft':raise HTTPException(409,'Evaluation already attested; propose an amendment')
        if actor.user in (state['author_id'],state['owner_id']):
            raise HTTPException(403,'Governance Exception: Separation of Duties policy enforced. Author/owner cannot be Attester.')
        # Captures an assessment-only attestation, never a funding or execution approval.
        payload={'confirmation':data.confirmation,'assessed_snapshot_head':rows[-1].event_hash,
                 'authority':'evaluation_attestation_only','policy_version':VERSION}
        return as_dict(make_event(db,actor,did,'decision.evaluation_attested',payload,data.request_id,rows))
    @router.get('/{did}')
    def history(did:str,actor=Depends(identity),db:Session=Depends(session)):
        own(db,actor,did)
        rows=ordered(db,actor,did);check=verify_chain(rows)
        if not check['valid']:raise HTTPException(409,{'integrity':'FAILED','details':check})
        return {'decision_id':did,'verification':check,'state':replay(rows),'events':[as_dict(e) for e in rows],
                'authority':'Slice attestation is not actual funding or deployment approval.'}
    return router
