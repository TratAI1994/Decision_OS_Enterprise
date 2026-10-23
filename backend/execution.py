"""R4 ETES: financially linked work, dual business/technical states, policy-gated actions.
All business-impact numbers are hypothetical, never finance-reconciled.
"""
from __future__ import annotations

import secrets
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    select,
    update,
)
from sqlalchemy.orm import Session

from .db import Base, Initiative
from .intelligence import DecisionRecord, OfficeRecord

BUSINESS_STATES=('Idea','Validation','Funded','Delivering','Operational','Value Realized')
TECH_STATES=('Data','Build','Evaluate','Secure','Pilot','Release')
TASK_STATES=('open','in_progress','blocked','delayed','completed')

class ExecutionTask(Base):
    __tablename__='etes_tasks'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False)
    title=Column(String(180),nullable=False)
    description=Column(String(2000),nullable=False,default='')
    business_stage=Column(String(32),nullable=False,default='Funded')
    technical_stage=Column(String(24),nullable=False,default='Data')
    status=Column(String(24),nullable=False,default='open')
    assignee_kind=Column(String(16),nullable=False)
    assignee_ref=Column(String(100),nullable=False)
    planned_finish=Column(String(10),nullable=True)
    blocked_since=Column(String(10),nullable=True)
    daily_value_at_risk=Column(Float,nullable=False,default=0)
    cost_model_source=Column(String(600),nullable=False)
    version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(UTC))
    __table_args__=(CheckConstraint('daily_value_at_risk >= 0',name='ck_etes_nonnegative_value'),)

class ExecutionProposal(Base):
    __tablename__='etes_proposals'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    task_id=Column(String(48),ForeignKey('etes_tasks.id'),nullable=False)
    recommendation=Column(String(1200),nullable=False)
    evidence_basis=Column(String(1200),nullable=False)
    status=Column(String(32),nullable=False,default='proposed')
    proposed_by=Column(String(120),nullable=False)
    reviewed_by=Column(String(120),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(UTC))

class NewTask(BaseModel):
    initiative_id:str
    decision_id:str
    title:str=Field(min_length=3,max_length=180)
    description:str=Field(default='',max_length=2000)
    business_stage:str='Funded'
    technical_stage:str='Data'
    assignee_kind:str
    assignee_ref:str
    planned_finish:str|None=None
    daily_value_at_risk:float=Field(default=0,ge=0,allow_inf_nan=False)
    cost_model_source:str=Field(min_length=3,max_length=600)

class TaskChange(BaseModel):
    expected_version:int=Field(ge=1)
    status:str
    business_stage:str
    technical_stage:str
    blocked_since:str|None=None

class ProposalInput(BaseModel):
    task_id:str
    recommendation:str=Field(min_length=5,max_length=1200)
    evidence_basis:str=Field(min_length=5,max_length=1200)

class ProposalReview(BaseModel):
    approved:bool

def iso_day(text):
    if not text:return None
    try:return date.fromisoformat(text)
    except ValueError:raise HTTPException(422,'Expected ISO YYYY-MM-DD')

def cost_details(t:ExecutionTask,as_of:date|None=None):
    today=as_of or date.today()
    start=iso_day(t.blocked_since) if t.status in ('blocked','delayed') else None
    days=max(0,(today-start).days) if start else 0
    # Exposure is a scenario; sunk benefit is not asserted and no NPV is recomputed.
    return {'delay_days':days,'modeled_deferred_value':round(days*t.daily_value_at_risk,2),
            'daily_value_at_risk':t.daily_value_at_risk,'classification':'modeled_scenario',
            'method':'delay calendar days × user-defined daily expected value at risk',
            'source':t.cost_model_source}

def dump(t):
    return {'id':t.id,'initiative_id':t.initiative_id,'decision_id':t.decision_id,'title':t.title,
            'description':t.description,'business_stage':t.business_stage,'technical_stage':t.technical_stage,
            'status':t.status,'assignee_kind':t.assignee_kind,'assignee_ref':t.assignee_ref,
            'planned_finish':t.planned_finish,'blocked_since':t.blocked_since,'version':t.version,
            'impact':cost_details(t),'created_at':t.created_at.isoformat() if t.created_at else None}

def validate_states(business,technical,status=None):
    if business not in BUSINESS_STATES or technical not in TECH_STATES or (status is not None and status not in TASK_STATES):
        raise HTTPException(422,'Unknown execution state')

def build_router(identity,session,require,events,find_initiative):
    router=APIRouter(prefix='/v1/execution',tags=['R4 Value-Tethered Execution'])
    def own(db,actor,task_id):
        t=db.scalar(select(ExecutionTask).where(ExecutionTask.id==task_id,ExecutionTask.tenant_id==actor.tenant))
        if not t:raise HTTPException(404,'Task not found in tenant')
        return t
    def decision(db,actor,decision_id,initiative_id):
        d=db.scalar(select(DecisionRecord).where(DecisionRecord.id==decision_id,DecisionRecord.tenant_id==actor.tenant,DecisionRecord.initiative_id==initiative_id))
        if not d:raise HTTPException(422,'Decision must belong to this initiative and tenant')
        return d
    def agents(db,actor):
        return db.scalars(select(OfficeRecord).where(OfficeRecord.tenant_id==actor.tenant,OfficeRecord.kind=='agent')).all()
    @router.get('/methodology')
    def methodology(actor=Depends(identity)):
        # Method crosswalks are proprietary Decision OS guidance, NOT PMI or SAFe certifications.
        return {
          'Data':{'CPMAI':'Data Understanding & Preparation','PMP/PMBOK':'Plan quality, requirements, procurement and risk responses','SAFe':'Enabler stories / architectural runway','Lean':'Map current data flow, eliminate rework','Design Thinking':'Validate data reflects real user needs','next':'Document lineage, consent, quality and representative test cohorts'},
          'Build':{'CPMAI':'Modeling / engineering','PMP/PMBOK':'Direct and manage project work; control quality','SAFe':'Team iteration + continuous integration','Lean':'Limit WIP and shorten cycle time','Design Thinking':'Prototype with real user workflows','next':'Run reproducible CI, integration checks and design review'},
          'Evaluate':{'CPMAI':'Model Evaluation','PMP/PMBOK':'Validate scope and control quality','SAFe':'Built-in quality / acceptance evidence','Lean':'Measure defect escape and remove root causes','Design Thinking':'Test with representative users','next':'Attach actual dataset/model version, failure modes, latency and cost evidence'},
          'Secure':{'CPMAI':'Deployment readiness & monitoring controls','PMP/PMBOK':'Monitor risks, stakeholder approvals','SAFe':'Compliance and security built-in','Lean':'Prevent defect propagation','Design Thinking':'Protect vulnerable personas and sensitive information','next':'Complete threat model, penetration testing and privacy review'},
          'Pilot':{'CPMAI':'Deployment + iterative evaluation','PMP/PMBOK':'Monitor benefits and stakeholder feedback','SAFe':'System demo + inspect/adapt','Lean':'Measure value-stream lead time','Design Thinking':'Observe user adoption and friction','next':'Run controlled pilot, compare baseline outcomes and prepare rollback'},
          'Release':{'CPMAI':'Deployment, monitoring and iteration','PMP/PMBOK':'Change control, transition and lessons learned','SAFe':'Release on demand with governance','Lean':'Keep feedback loops and incident response','Design Thinking':'Verify usability and support journey','next':'Check initiative release approval, on-call owner, rollback and measured adoption'}
        }

    @router.get('/copilot-context')
    def copilot_context(page:str='Executive',actor=Depends(identity),db:Session=Depends(session)):
        rows=db.scalars(select(ExecutionTask).where(ExecutionTask.tenant_id==actor.tenant)).all()
        blockers=[t for t in rows if t.status in ('blocked','delayed')]
        blockers.sort(key=lambda t:cost_details(t)['modeled_deferred_value'],reverse=True)
        return {'page':page[:100], 'mode':'deterministic evidence advisor; no LLM invocation',
                'next_action':('Inspect '+blockers[0].title+' blocker and its linked board decision' if blockers else 'Review initiative decision, funding, delivery evidence and value baseline'),
                'blocked_items':len(blockers),'modeled_top_exposure':cost_details(blockers[0]) if blockers else None,
                'human_gate':'Agent proposals require independent human review; no autonomous execution in R4'}

    @router.get('/assignees')
    def assignees(actor=Depends(identity),db:Session=Depends(session)):
        # Until HR/Entra integration, human roster comes from tenant initiative owners + current user.
        owners=sorted({x.owner for x in db.scalars(select(Initiative).where(Initiative.tenant_id==actor.tenant))}|{actor.user})
        return [{'kind':'human','ref':u,'label':u} for u in owners]+[{'kind':'agent','ref':a.id,'label':a.name} for a in agents(db,actor)]
    @router.get('/tasks')
    def tasks(initiative_id:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
        q=select(ExecutionTask).where(ExecutionTask.tenant_id==actor.tenant)
        if initiative_id:
            find_initiative(db,actor,initiative_id)
            q=q.where(ExecutionTask.initiative_id==initiative_id)
        return [dump(t) for t in db.scalars(q.order_by(ExecutionTask.created_at.desc())).all()]
    @router.post('/tasks',status_code=201)
    def create(data:NewTask,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'});find_initiative(db,actor,data.initiative_id)
        decision(db,actor,data.decision_id,data.initiative_id)
        validate_states(data.business_stage,data.technical_stage)
        iso_day(data.planned_finish)
        allowed={(x['kind'],x['ref']) for x in assignees(actor,db)}
        if (data.assignee_kind,data.assignee_ref) not in allowed:raise HTTPException(422,'Assignee not registered in tenant')
        t=ExecutionTask(id=secrets.token_hex(12),tenant_id=actor.tenant,**data.model_dump())
        db.add(t);events(db,actor,'etes.task_created',t.id,{'decision_id':t.decision_id,'initiative_id':t.initiative_id});db.commit()
        return dump(t)
    @router.patch('/tasks/{task_id}')
    def change(task_id:str,data:TaskChange,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'});t=own(db,actor,task_id)
        validate_states(data.business_stage,data.technical_stage,data.status)
        if data.business_stage=='Value Realized':
            raise HTTPException(409,'Value Realized requires independent financial evidence; use finance reconciliation workflow')
        if data.technical_stage=='Release' and data.status=='completed':
            raise HTTPException(409,'Technical release completion requires existing initiative governance approval')
        blocked_since=iso_day(data.blocked_since)
        if data.status in ('blocked','delayed'):
            if not blocked_since:raise HTTPException(422,'blocked_since required for blocked/delayed tasks')
            if blocked_since>date.today():raise HTTPException(422,'blocked_since cannot be future')
        else:blocked_since=None
        count=db.execute(update(ExecutionTask).where(ExecutionTask.id==task_id,ExecutionTask.tenant_id==actor.tenant,ExecutionTask.version==data.expected_version).values(status=data.status,business_stage=data.business_stage,technical_stage=data.technical_stage,blocked_since=blocked_since.isoformat() if blocked_since else None,version=ExecutionTask.version+1)).rowcount
        if count!=1:raise HTTPException(409,'Version conflict; refresh task')
        events(db,actor,'etes.task_updated',task_id,{'status':data.status,'version':data.expected_version+1});db.commit()
        return dump(own(db,actor,task_id))
    @router.get('/thread/{task_id}')
    def thread(task_id:str,actor=Depends(identity),db:Session=Depends(session)):
        t=own(db,actor,task_id);d=decision(db,actor,t.decision_id,t.initiative_id)
        initiative=find_initiative(db,actor,t.initiative_id)
        return {'task':dump(t),'funding_decision':{'id':d.id,'title':d.title,'rationale':d.rationale,'assumptions':d.assumptions,'evidence_refs':d.evidence_refs,'state':d.state},'initiative':{'id':initiative.id,'name':initiative.name,'owner':initiative.owner}}
    @router.get('/brief')
    def brief(actor=Depends(identity),db:Session=Depends(session)):
        rows=db.scalars(select(ExecutionTask).where(ExecutionTask.tenant_id==actor.tenant)).all()
        blocked=[t for t in rows if t.status in ('blocked','delayed')]
        blocked.sort(key=lambda t:cost_details(t)['modeled_deferred_value'],reverse=True)
        findings=[{'task_id':t.id,'title':t.title,'status':t.status,'technical_stage':t.technical_stage,
                   'impact':cost_details(t),'recommendation':f'Review blocker with {t.assignee_ref}; verify dependencies and unblock or rescope.'} for t in blocked]
        return {'generated_at':datetime.now(UTC).isoformat(),'source':'stored execution records; deterministic; not an autonomous monitor',
                'total_tasks':len(rows),'blocked_count':len(blocked),'total_modeled_deferred_value':round(sum(x['impact']['modeled_deferred_value'] for x in findings),2),
                'findings':findings,'warning':'Modeled deferred value, not an audited loss. Overlap between tasks can double count; do not sum as realized loss.'}
    @router.post('/proposals',status_code=201)
    def propose(data:ProposalInput,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'});t=own(db,actor,data.task_id)
        row=ExecutionProposal(id=secrets.token_hex(12),tenant_id=actor.tenant,task_id=t.id,recommendation=data.recommendation,evidence_basis=data.evidence_basis,proposed_by=actor.user)
        db.add(row);events(db,actor,'etes.action_proposed',row.id,{'task_id':t.id});db.commit()
        return {'id':row.id,'status':'proposed'}
    @router.get('/proposals')
    def proposals(actor=Depends(identity),db:Session=Depends(session)):
        rows=db.scalars(select(ExecutionProposal).where(ExecutionProposal.tenant_id==actor.tenant).order_by(ExecutionProposal.created_at.desc())).all()
        return [{'id':r.id,'task_id':r.task_id,'recommendation':r.recommendation,'evidence_basis':r.evidence_basis,'status':r.status,'proposed_by':r.proposed_by,'reviewed_by':r.reviewed_by} for r in rows]
    @router.post('/proposals/{pid}/review')
    def review(pid:str,data:ProposalReview,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','reviewer','approver'})
        row=db.scalar(select(ExecutionProposal).where(ExecutionProposal.id==pid,ExecutionProposal.tenant_id==actor.tenant))
        if not row:raise HTTPException(404,'Proposal not found')
        if row.status!='proposed':raise HTTPException(409,'Already reviewed')
        if row.proposed_by==actor.user:raise HTTPException(403,'Separation of duties required')
        row.status='approved_for_manual_action' if data.approved else 'rejected';row.reviewed_by=actor.user
        # This does NOT dispatch tools or change production; separate executor/policy gate required.
        events(db,actor,'etes.proposal_reviewed',pid,{'decision':row.status});db.commit()
        return {'id':pid,'status':row.status,'executed':False}
    return router
