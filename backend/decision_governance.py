"""R5.2–R5.4: decision snapshots, bounded recommendations, Action Center and replay.
LLM-free by default. No side-effect executor: approvals create accountable actions only.
"""
from __future__ import annotations
import hashlib, json, secrets
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, select, update, UniqueConstraint
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON
from .db import Base
from .intelligence import DecisionRecord
from .execution import ExecutionTask
from .models import AIRiskAssessment, RedTeamFinding

def utc(): return datetime.now(timezone.utc)
def digest(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str).encode()).hexdigest()

class DecisionSnapshot(Base):
    __tablename__='di_decision_snapshots'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    decision_version=Column(Integer,nullable=False)
    snapshot=Column(JSON,nullable=False)
    snapshot_hash=Column(String(64),nullable=False)
    recorded_by=Column(String(120),nullable=False)
    recorded_at=Column(DateTime(timezone=True),nullable=False,default=utc)

class ActionPacket(Base):
    __tablename__='di_action_packets'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    created_by=Column(String(120),nullable=False)
    title=Column(String(180),nullable=False)
    action_kind=Column(String(48),nullable=False)
    expected_spend=Column(Integer,nullable=False,default=0) # cents, no floats
    rationale=Column(String(3000),nullable=False)
    evidence_refs=Column(JSON,nullable=False)
    snapshot_id=Column(String(48),ForeignKey('di_decision_snapshots.id'),nullable=False)
    status=Column(String(36),nullable=False,default='draft')
    version=Column(Integer,nullable=False,default=1)
    request_id=Column(String(100),nullable=False)
    policy_draft=Column(JSON,nullable=False)
    policy_approval=Column(JSON,nullable=True)
    approval_by=Column(String(120),nullable=True)
    approved_at=Column(DateTime(timezone=True),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,default=utc)
    __table_args__=(UniqueConstraint('tenant_id','request_id',name='uq_packet_tenant_retry'),)

class AccountableAction(Base):
    __tablename__='di_accountable_actions'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    packet_id=Column(String(48),ForeignKey('di_action_packets.id'),nullable=False,unique=True)
    owner=Column(String(120),nullable=False)
    status=Column(String(28),nullable=False,default='open')
    outcome=Column(String(2000),nullable=False,default='')
    evidence_reference=Column(String(500),nullable=False,default='')
    created_at=Column(DateTime(timezone=True),nullable=False,default=utc)

ALLOWED={'request_review','assign_reviewer','create_remediation','propose_budget_change','pause_initiative'}
POLICY_VERSION='r5.2-rules-1'
# Every action still requires human authorization, even below the budget threshold.
def policy(kind, cents, findings, role):
    blocks=[]
    if kind not in ALLOWED: blocks.append('Unsupported action')
    if cents<0 or cents>100_000_000_00: blocks.append('Amount outside permitted range')
    if kind=='propose_budget_change' and cents>1_000_000: blocks.append('Budget change exceeds $10,000 advisory ceiling; finance authority needed')
    if kind=='pause_initiative' and role not in ('admin','lead'): blocks.append('Only leadership may propose an initiative pause')
    if findings and kind=='propose_budget_change': blocks.append('Open severe trust findings must be addressed before budget-change recommendations')
    return {'version':POLICY_VERSION,'result':'deny' if blocks else 'requires_human_approval','reasons':blocks,'severe_findings':findings,'checked_at':utc().isoformat()}

class NewPacket(BaseModel):
    decision_id:str
    title:str=Field(min_length=5,max_length=180)
    action_kind:Literal['request_review','assign_reviewer','create_remediation','propose_budget_change','pause_initiative']
    expected_spend_cents:int=Field(ge=0,le=100_000_000_00)
    rationale:str=Field(min_length=20,max_length=3000)
    evidence_refs:list[str]=Field(min_length=1,max_length=30)
    request_id:str=Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class ReviewPacket(BaseModel):
    expected_version:int=Field(ge=1)
    decision:Literal['approve','reject']
    assigned_owner:str=Field(min_length=2,max_length=120)

class CloseAction(BaseModel):
    outcome:str=Field(min_length=10,max_length=2000)
    evidence_reference:str=Field(min_length=3,max_length=500)

def packet_json(x):
    return {'id':x.id,'decision_id':x.decision_id,'initiative_id':x.initiative_id,'title':x.title,'action_kind':x.action_kind,'expected_spend_cents':x.expected_spend,'rationale':x.rationale,'evidence_refs':x.evidence_refs,'status':x.status,'version':x.version,'snapshot_id':x.snapshot_id,'policy_draft':x.policy_draft,'policy_approval':x.policy_approval,'created_by':x.created_by,'approval_by':x.approval_by}

def build_router(identity,session,require,events,find_initiative):
    router=APIRouter(prefix='/v1/decisions-governed',tags=['R5.2–R5.4 Governed Decisions'])
    def own(db,actor,decision_id):
        d=db.scalar(select(DecisionRecord).where(DecisionRecord.id==decision_id,DecisionRecord.tenant_id==actor.tenant))
        if not d: raise HTTPException(404,'Decision not found')
        return d
    def packet(db,actor,pid):
        r=db.scalar(select(ActionPacket).where(ActionPacket.id==pid,ActionPacket.tenant_id==actor.tenant))
        if not r:raise HTTPException(404,'Action packet not found')
        return r
    def severe(db,actor,decision_id):
        return len(db.scalars(select(RedTeamFinding).where(RedTeamFinding.tenant_id==actor.tenant,RedTeamFinding.decision_id==decision_id,RedTeamFinding.severity.in_(['high','critical']),RedTeamFinding.status.notin_(['false_positive','remediated_pending_retest']))).all())
    def snap(db,actor,d):
        risk=db.scalars(select(AIRiskAssessment).where(AIRiskAssessment.tenant_id==actor.tenant,AIRiskAssessment.decision_id==d.id)).all()
        data={'decision_id':d.id,'initiative_id':d.initiative_id,'decision_version':d.version,'title':d.title,'rationale':d.rationale,'assumptions':d.assumptions,'evidence_refs':d.evidence_refs,'option_chosen':d.option_chosen,'confidence_basis':d.confidence_basis or 'unknown','risk_tier':d.risk_tier or 'unassessed','risk_snapshots':[{'id':r.id,'version':r.version,'classification':r.classification,'review_status':r.review_status} for r in risk], 'policy_version':POLICY_VERSION,'captured_at':utc().isoformat()}
        row=DecisionSnapshot(id=secrets.token_hex(12),tenant_id=actor.tenant,decision_id=d.id,decision_version=d.version,snapshot=data,snapshot_hash=digest(data),recorded_by=actor.user)
        db.add(row)
        return row
    @router.get('/context/{decision_id}')
    def context(decision_id:str,actor=Depends(identity),db:Session=Depends(session)):
        d=own(db,actor,decision_id);tasks=db.scalars(select(ExecutionTask).where(ExecutionTask.tenant_id==actor.tenant,ExecutionTask.decision_id==d.id)).all()
        return {'decision_id':d.id,'initiative_id':d.initiative_id,'title':d.title,'rationale':d.rationale,'evidence_refs':d.evidence_refs,'assumptions':d.assumptions,'risk_tier':d.risk_tier or 'unassessed','confidence_basis':d.confidence_basis or 'unknown','tasks':[{'id':x.id,'title':x.title,'status':x.status} for x in tasks],'severe_open_findings':severe(db,actor,d.id)}
    @router.post('/packets',status_code=201)
    def draft(data:NewPacket,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor','finance'}); d=own(db,actor,data.decision_id);find_initiative(db,actor,d.initiative_id)
        prior=db.scalar(select(ActionPacket).where(ActionPacket.tenant_id==actor.tenant,ActionPacket.request_id==data.request_id))
        if prior:return packet_json(prior)
        checks=policy(data.action_kind,data.expected_spend_cents,severe(db,actor,d.id),actor.role)
        if checks['result']=='deny':raise HTTPException(403,{'policy':checks})
        snapshot=snap(db,actor,d)
        # Persist the FK parent *within the same transaction* before writing the child.
        # Event logging or ORM autoflush may otherwise INSERT ActionPacket first.
        # Do not commit here: both records must succeed or roll back together.
        db.flush([snapshot])
        row=ActionPacket(id=secrets.token_hex(12),tenant_id=actor.tenant,decision_id=d.id,initiative_id=d.initiative_id,created_by=actor.user,title=data.title,action_kind=data.action_kind,expected_spend=data.expected_spend_cents,rationale=data.rationale,evidence_refs=data.evidence_refs,snapshot_id=snapshot.id,request_id=data.request_id,policy_draft=checks)
        db.add(row);events(db,actor,'packet.drafted',row.id,{'decision':d.id,'policy_version':POLICY_VERSION,'snapshot_hash':snapshot.snapshot_hash});db.commit()
        return packet_json(row)
    @router.get('/packets')
    def list_packets(actor=Depends(identity),db:Session=Depends(session)):
        return [packet_json(x) for x in db.scalars(select(ActionPacket).where(ActionPacket.tenant_id==actor.tenant).order_by(ActionPacket.created_at.desc()).limit(200)).all()]
    @router.post('/packets/{pid}/review')
    def review(pid:str,data:ReviewPacket,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','lead','finance'});p=packet(db,actor,pid)
        if p.created_by==actor.user:raise HTTPException(403,'Independent reviewer required')
        if p.status!='draft' or p.version!=data.expected_version:raise HTTPException(409,'Packet changed; refresh')
        checks=policy(p.action_kind,p.expected_spend,severe(db,actor,p.decision_id),actor.role)
        if data.decision=='approve' and checks['result']=='deny':raise HTTPException(409,{'policy':'Changed risk/policy state blocks approval','checks':checks})
        newstatus='approved' if data.decision=='approve' else 'rejected'
        n=db.execute(update(ActionPacket).where(ActionPacket.id==pid,ActionPacket.tenant_id==actor.tenant,ActionPacket.version==data.expected_version,ActionPacket.status=='draft').values(status=newstatus,version=ActionPacket.version+1,policy_approval=checks,approval_by=actor.user,approved_at=utc())).rowcount
        if n!=1:raise HTTPException(409,'Concurrent review; refresh')
        if newstatus=='approved':
            db.add(AccountableAction(id=secrets.token_hex(12),tenant_id=actor.tenant,packet_id=pid,owner=data.assigned_owner))
        events(db,actor,'packet.reviewed',pid,{'disposition':newstatus,'policy':checks,'owner':data.assigned_owner});db.commit()
        return {'status':newstatus,'policy':checks,'note':'Approved action is assigned for human execution; nothing is automatically executed.'}
    @router.get('/actions')
    def actions(actor=Depends(identity),db:Session=Depends(session)):
        return [{'id':x.id,'packet_id':x.packet_id,'owner':x.owner,'status':x.status,'outcome':x.outcome,'evidence_reference':x.evidence_reference} for x in db.scalars(select(AccountableAction).where(AccountableAction.tenant_id==actor.tenant)).all()]
    @router.post('/actions/{aid}/complete')
    def complete(aid:str,data:CloseAction,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','lead'});a=db.scalar(select(AccountableAction).where(AccountableAction.id==aid,AccountableAction.tenant_id==actor.tenant))
        if not a:raise HTTPException(404,'Action not found')
        if a.status!='open':raise HTTPException(409,'Action already completed')
        a.status='reported_complete';a.outcome=data.outcome;a.evidence_reference=data.evidence_reference
        events(db,actor,'action.reported_complete',aid,{'evidence_reference':data.evidence_reference});db.commit()
        return {'status':a.status,'verification':'self_reported; independent evidence verification remains separate'}
    @router.get('/replay/{decision_id}')
    def replay(decision_id:str,actor=Depends(identity),db:Session=Depends(session)):
        d=own(db,actor,decision_id)
        snapshots=db.scalars(select(DecisionSnapshot).where(DecisionSnapshot.tenant_id==actor.tenant,DecisionSnapshot.decision_id==d.id).order_by(DecisionSnapshot.recorded_at)).all()
        packets=db.scalars(select(ActionPacket).where(ActionPacket.tenant_id==actor.tenant,ActionPacket.decision_id==d.id)).all()
        return {'decision_id':d.id,'historical_snapshots':[{'id':s.id,'data':s.snapshot,'hash':s.snapshot_hash,'hash_valid':s.snapshot_hash==digest(s.snapshot),'recorded_at':str(s.recorded_at)} for s in snapshots], 'action_packets':[packet_json(p) for p in packets], 'outcome':d.outcome,'outcome_source':d.outcome_source,'limitations':'Snapshots begin with R5.2; prior history cannot be retroactively reconstructed. Outcome is not automatically independently verified.'}
    @router.get('/memory')
    def memory(q:str='',actor=Depends(identity),db:Session=Depends(session)):
        matches=db.scalars(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant)).all(); term=q.strip().casefold()
        return {'method':'literal substring','items':[{'decision_id':d.id,'title':d.title,'outcome':d.outcome,'outcome_source':d.outcome_source,'evidence_quality':'unverified unless externally attested','confidence_basis':d.confidence_basis or 'unknown','sample_size':None,'elapsed_period':None,'limitations':'No statistical inference from anecdotal records'} for d in matches if not term or term in (d.title+' '+d.rationale+' '+d.outcome).casefold()][:100]}
    return router
