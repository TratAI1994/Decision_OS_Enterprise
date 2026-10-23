"""R8 finance outcome records: append-only attestations, not autonomous ROI claims."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON

from .db import Base
from .intelligence import DecisionRecord

CENT=Decimal('0.01')
ATTRIBUTION={'experimental','quasi_experimental','correlational','estimated','unknown'}

def money_cents(raw:str)->int:
    try:
        value=Decimal(raw)
        if not value.is_finite() or abs(value)>Decimal(1000000000000) or value.as_tuple().exponent < -2:
            raise ValueError('Value must be finite, <= 1 trillion, and at most two decimal places')
        return int((value/CENT).to_integral_exact(rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,TypeError,ArithmeticError) as exc:
        raise ValueError('Invalid currency amount (decimal string; max two fractional digits)') from exc

def currency(cents:int)->str:
    return f'{Decimal(cents)/100:.2f}'

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def event_hash(prev,material):
    return hashlib.sha256((prev+'\n'+canonical(material)).encode()).hexdigest()

class OutcomeEvent(Base):
    __tablename__='di_outcome_events'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    seq=Column(Integer,nullable=False)
    event_type=Column(String(32),nullable=False)
    actor_id=Column(String(120),nullable=False)
    actor_role=Column(String(64),nullable=False)
    occurred_at=Column(DateTime(timezone=True),nullable=False)
    payload=Column(JSON,nullable=False)
    prev_hash=Column(String(64),nullable=False)
    event_hash=Column(String(64),nullable=False)
    request_id=Column(String(100),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','decision_id','seq',name='uq_di_outcome_seq'),
                    UniqueConstraint('tenant_id','request_id',name='uq_di_outcome_request'))

class PlanIn(BaseModel):
    decision_id:str
    expected_amount:str=Field(min_length=1,max_length=40)
    currency_code:str=Field(pattern=r'^[A-Z]{3}$')
    period:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    methodology:str=Field(min_length=12,max_length=1200)
    baseline_ref:str=Field(min_length=3,max_length=500)
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class ClaimIn(BaseModel):
    period:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    reported_amount:str=Field(min_length=1,max_length=40)
    measurement_method:str=Field(min_length=12,max_length=1200)
    source_ref:str=Field(min_length=3,max_length=500)
    attribution_method:str
    attribution_notes:str=Field(min_length=10,max_length=1200)
    expected_seq:int=Field(ge=1)
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class VerifyIn(BaseModel):
    claim_event_id:str
    verified_amount:str=Field(min_length=1,max_length=40)
    reconciliation_method:str=Field(min_length=12,max_length=1200)
    financial_source_ref:str=Field(min_length=3,max_length=500)
    notes:str=Field(min_length=10,max_length=1200)
    expected_seq:int=Field(ge=2)
    confirmation:str=Field(pattern=r'^I independently reconciled this benefit against financial evidence\.$')
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

def material(e):
    ts=e.occurred_at.isoformat()
    if ts.endswith('+00:00'):ts=ts[:-6]+'Z'
    elif '+' not in ts and not ts.endswith('Z'):ts+='Z'
    return dict(tenant_id=e.tenant_id,decision_id=e.decision_id,seq=e.seq,event_type=e.event_type,
                actor_id=e.actor_id,actor_role=e.actor_role,occurred_at=ts,payload=e.payload,request_id=e.request_id)

def serialize(e):return {**material(e),'id':e.id,'prev_hash':e.prev_hash,'event_hash':e.event_hash}

def verify_chain(events):
    prev='GENESIS'
    for i,e in enumerate(events,1):
        if e.seq!=i or e.prev_hash!=prev or e.event_hash!=event_hash(prev,material(e)):
            return {'consistent':False,'invalid_sequence':i}
        prev=e.event_hash
    return {'consistent':True,'head_hash':prev,'event_count':len(events),
            'caveat':'Hash-chain consistency is not digital signing, independent anchoring, or WORM retention.'}

def replay(events):
    result={'plan':None,'claims':[],'verifications':[],'verified_by_period':{},'pending_periods':[]}
    claims={}
    for e in events:
        p=e.payload
        if e.event_type=='outcome.plan_recorded':
            if result['plan']:raise ValueError('Duplicate plan')
            result['plan']={**p,'actor_id':e.actor_id,'recorded_at':material(e)['occurred_at']}
        elif e.event_type=='outcome.benefit_reported':
            if not result['plan']:raise ValueError('Missing plan')
            claim={**p,'event_id':e.id,'actor_id':e.actor_id,'recorded_at':material(e)['occurred_at']}
            result['claims'].append(claim);claims[e.id]=claim
        elif e.event_type=='outcome.finance_attested':
            c=claims.get(p['claim_event_id'])
            if c is None or c['actor_id']==e.actor_id:raise ValueError('Invalid finance attestation')
            v={**p,'period':c['period'],'actor_id':e.actor_id,'event_id':e.id,
               'verified_at':material(e)['occurred_at'],'claim_actor':c['actor_id']}
            result['verifications'].append(v);result['verified_by_period'][c['period']]=v
        else:raise ValueError('Unknown outcome event')
    result['pending_periods']=sorted({c['period'] for c in result['claims']}-set(result['verified_by_period']))
    return result

def summarize(state):
    plan=state['plan']
    if not plan:return {'status':'not_planned','variance':None}
    period=plan['period'];confirmed=state['verified_by_period'].get(period)
    latest=next((c for c in reversed(state['claims']) if c['period']==period),None)
    out={'status':'finance_attested' if confirmed else ('self_reported' if latest else 'awaiting_measurement'),
         'period':period,'currency':plan['currency_code'],'expected':currency(plan['expected_cents']),
         'self_reported':currency(latest['reported_cents']) if latest else None,
         'finance_verified':currency(confirmed['verified_cents']) if confirmed else None,
         'variance':currency(confirmed['verified_cents']-plan['expected_cents']) if confirmed else None,
         'attribution':latest['attribution_method'] if latest else 'unknown',
         'limitations':'Finance attestation validates a reconciled amount; it does not establish causation.'}
    if latest:out['source_ref']=latest['source_ref']
    if confirmed:out['finance_source_ref']=confirmed['financial_source_ref'];out['finance_reviewer']=confirmed['actor_id']
    return out

def build_router(identity,session,require):
    r=APIRouter(prefix='/v1/outcome-economics',tags=['R8 Verified Outcome Economics'])
    def own(db,actor,did):
        d=db.scalar(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did))
        if not d:raise HTTPException(404,'Decision not found in tenant')
        return d
    def lock(db,actor,did):
        if db.bind.dialect.name=='postgresql':
            db.execute(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did).with_for_update()).first()
    def ordered(db,actor,did):
        return list(db.scalars(select(OutcomeEvent).where(OutcomeEvent.tenant_id==actor.tenant,
                      OutcomeEvent.decision_id==did).order_by(OutcomeEvent.seq)).all())
    def existing(db,actor,key):
        return db.scalar(select(OutcomeEvent).where(OutcomeEvent.tenant_id==actor.tenant,OutcomeEvent.request_id==key))
    def append(db,actor,did,kind,payload,key,rows):
        e=OutcomeEvent(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=did,seq=len(rows)+1,
                       event_type=kind,actor_id=actor.user,actor_role=actor.role,occurred_at=datetime.now(UTC),
                       payload=payload,prev_hash=rows[-1].event_hash if rows else 'GENESIS',request_id=key)
        e.event_hash=event_hash(e.prev_hash,material(e));db.add(e)
        try:db.flush();db.commit()
        except Exception:
            db.rollback();raise HTTPException(409,'Concurrent write or duplicate request; refresh')
        return serialize(e)
    def amount(raw):
        try:return money_cents(raw)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    def fresh(rows):
        if not verify_chain(rows)['consistent']:raise HTTPException(409,'Outcome event integrity verification failed')
        try:return replay(rows)
        except ValueError:raise HTTPException(409,'Outcome event reconstruction failed')
    @r.post('/plan',status_code=201)
    def plan(body:PlanIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'});own(db,actor,body.decision_id)
        cents=amount(body.expected_amount)
        lock(db,actor,body.decision_id)
        payload=dict(expected_cents=cents,currency_code=body.currency_code,period=body.period,
                     methodology=body.methodology,baseline_ref=body.baseline_ref)
        old=existing(db,actor,body.request_id)
        if old:
            if old.event_type=='outcome.plan_recorded' and old.decision_id==body.decision_id and old.payload==payload:return serialize(old)
            raise HTTPException(409,'Idempotency key collision')
        rows=ordered(db,actor,body.decision_id)
        if rows:raise HTTPException(409,'Plan already recorded; amendments require a separately reviewed plan version')
        return append(db,actor,body.decision_id,'outcome.plan_recorded',payload,body.request_id,rows)
    @r.post('/{did}/report',status_code=201)
    def report(did:str,body:ClaimIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'});own(db,actor,did)
        if body.attribution_method not in ATTRIBUTION:raise HTTPException(422,'Invalid attribution label')
        cents=amount(body.reported_amount)
        lock(db,actor,did)
        payload=dict(period=body.period,reported_cents=cents,measurement_method=body.measurement_method,
                     source_ref=body.source_ref,attribution_method=body.attribution_method,
                     attribution_notes=body.attribution_notes)
        old=existing(db,actor,body.request_id)
        if old:
            if old.event_type=='outcome.benefit_reported' and old.decision_id==did and old.payload==payload:return serialize(old)
            raise HTTPException(409,'Idempotency key collision')
        rows=ordered(db,actor,did)
        if len(rows)!=body.expected_seq:raise HTTPException(409,'Sequence conflict; refresh')
        state=fresh(rows)
        if not state['plan']:raise HTTPException(409,'Decision-time plan required')
        if body.period!=state['plan']['period']:raise HTTPException(422,'Period mismatches plan')
        if body.period in state['verified_by_period']:raise HTTPException(409,'Period already finance-attested; corrections require new reconciliation release')
        return append(db,actor,did,'outcome.benefit_reported',payload,body.request_id,rows)
    @r.post('/{did}/finance-attest',status_code=201)
    def attest(did:str,body:VerifyIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'finance'});own(db,actor,did)
        cents=amount(body.verified_amount)
        lock(db,actor,did)
        payload=dict(claim_event_id=body.claim_event_id,verified_cents=cents,reconciliation_method=body.reconciliation_method,
                     financial_source_ref=body.financial_source_ref,notes=body.notes,
                     confirmation=body.confirmation)
        old=existing(db,actor,body.request_id)
        if old:
            if old.event_type=='outcome.finance_attested' and old.decision_id==did and old.payload==payload:return serialize(old)
            raise HTTPException(409,'Idempotency key collision')
        rows=ordered(db,actor,did)
        if len(rows)!=body.expected_seq:raise HTTPException(409,'Sequence conflict; refresh')
        state=fresh(rows)
        claim=next((c for c in state['claims'] if c['event_id']==body.claim_event_id),None)
        if not claim:raise HTTPException(404,'Reported claim not found')
        if claim['actor_id']==actor.user:raise HTTPException(403,'Separation of duties: reporter cannot finance-attest own claim')
        if claim['period'] in state['verified_by_period']:raise HTTPException(409,'Already finance-attested')
        if state['claims'][-1]['event_id']!=body.claim_event_id:raise HTTPException(409,'Latest submitted claim must be reviewed')
        return append(db,actor,did,'outcome.finance_attested',payload,body.request_id,rows)
    @r.get('/{did}')
    def details(did:str,actor=Depends(identity),db:Session=Depends(session)):
        own(db,actor,did);rows=ordered(db,actor,did)
        state=fresh(rows)
        return {'decision_id':did,'integrity':verify_chain(rows),'summary':summarize(state),
                'state':state,'events':[serialize(e) for e in rows],
                'disclosure':'Reconciled financial evidence is reviewer-attested, not independently retrieved or cryptographically signed.'}
    return r
