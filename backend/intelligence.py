"""Decision OS R1.1–R3: tenant-scoped decision memory, evidence provenance,
AI cost, workforce, agent registry, risk and scenario planning.

No generated narrative is attested; scenarios are not actual outcomes.
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    select,
    update,
)
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON

from .db import Base, Benefit, Initiative


class DecisionRecord(Base):
    __tablename__='di_decisions'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    initiative_id=Column(String(48),ForeignKey('initiatives.id'),nullable=False)
    title=Column(String(180),nullable=False)
    option_chosen=Column(String(800),nullable=False)
    alternatives=Column(JSON,nullable=False,default=list)
    rationale=Column(String(3000),nullable=False)
    assumptions=Column(JSON,nullable=False,default=list)
    evidence_refs=Column(JSON,nullable=False,default=list)
    owner=Column(String(120),nullable=False)
    state=Column(String(32),nullable=False,default='proposed')
    outcome=Column(String(3000),nullable=False,default='')
    outcome_source=Column(String(800),nullable=False,default='')
    review_date=Column(String(10),nullable=False,default='')
    version=Column(Integer,nullable=False,default=1)
    # R5.1.1 nullable extensions; existing tenant_id and version are preserved.
    risk_tier=Column(String(24),nullable=True)
    confidence_basis=Column(String(40),nullable=True)
    supersedes_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=True)
    review_started_at=Column(DateTime(timezone=True),nullable=True)
    approved_at=Column(DateTime(timezone=True),nullable=True)
    execution_started_at=Column(DateTime(timezone=True),nullable=True)
    closed_at=Column(DateTime(timezone=True),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(UTC))

class OfficeRecord(Base):
    __tablename__='di_office_records'
    id=Column(String(48),primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    kind=Column(String(32),nullable=False,index=True)
    name=Column(String(180),nullable=False)
    owner=Column(String(120),nullable=False)
    payload=Column(JSON,nullable=False)
    evidence_status=Column(String(32),nullable=False,default='self_reported')
    version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(UTC))

VALID_KINDS={'risk','economics','agent','copilot','workforce','twin_node','twin_edge'}
VALID_CLASS={'modeled','self_reported','independently_verified','finance_reconciled'}

class NewDecision(BaseModel):
    initiative_id:str
    title:str=Field(min_length=4,max_length=180)
    option_chosen:str=Field(min_length=2,max_length=800)
    alternatives:list[str]=Field(default_factory=list,max_length=15)
    rationale:str=Field(min_length=5,max_length=3000)
    assumptions:list[str]=Field(default_factory=list,max_length=30)
    evidence_refs:list[str]=Field(default_factory=list,max_length=30)
    review_date:str=''

class OutcomeUpdate(BaseModel):
    expected_version:int=Field(ge=1)
    outcome:str=Field(min_length=5,max_length=3000)
    source_ref:str=Field(min_length=3,max_length=800)

class NewOfficeRecord(BaseModel):
    kind:str
    name:str=Field(min_length=3,max_length=180)
    owner:str=Field(min_length=2,max_length=120)
    payload:dict[str,Any]=Field(default_factory=dict)
    evidence_status:str='self_reported'
    request_id:str|None=Field(default=None,min_length=10,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class OfficeUpdate(BaseModel):
    expected_version:int=Field(ge=1)
    payload:dict[str,Any]

class ScenarioRequest(BaseModel):
    budget:float=Field(ge=0,le=1e12,allow_inf_nan=False)
    candidates:list[dict]=Field(min_length=1,max_length=250)
    max_items:int=Field(default=100,ge=1,le=250)

class ExecutiveNarrativeRequest(BaseModel):
    audience:str='board'


def finite_nonneg(x,label):
    try: v=float(x)
    except (ValueError,TypeError):raise HTTPException(422,f'{label}: numeric value required')
    if not math.isfinite(v) or v<0 or v>1e12:raise HTTPException(422,f'{label}: invalid range')
    return v


def decision_json(d):
    return {'id':d.id,'tenant_id':d.tenant_id,'initiative_id':d.initiative_id,'title':d.title,'option_chosen':d.option_chosen,
            'alternatives':d.alternatives,'rationale':d.rationale,'assumptions':d.assumptions,
            'evidence_refs':d.evidence_refs,'owner':d.owner,'state':d.state,'outcome':d.outcome,
            'outcome_source':d.outcome_source,'review_date':d.review_date,'version':d.version,'risk_tier':d.risk_tier or 'unassessed','confidence_basis':d.confidence_basis or 'unknown','supersedes_id':d.supersedes_id,'review_started_at':d.review_started_at.isoformat() if d.review_started_at else None,'approved_at':d.approved_at.isoformat() if d.approved_at else None,'execution_started_at':d.execution_started_at.isoformat() if d.execution_started_at else None,'closed_at':d.closed_at.isoformat() if d.closed_at else None}

def office_json(r):
    return {'id':r.id,'kind':r.kind,'name':r.name,'owner':r.owner,'payload':r.payload,
            'evidence_status':r.evidence_status,'version':r.version}


def build_router(identity,session,require,events,find_initiative):
    router=APIRouter(prefix='/v1/intelligence',tags=['Decision Intelligence R1.1–R3'])

    @router.get('/decisions')
    def list_decisions(initiative_id:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
        query=select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant)
        if initiative_id:query=query.where(DecisionRecord.initiative_id==initiative_id)
        return [decision_json(x) for x in db.scalars(query.order_by(DecisionRecord.created_at.desc())).all()]

    @router.post('/decisions',status_code=201)
    def create_decision(data:NewDecision,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor'}); find_initiative(db,actor,data.initiative_id)
        row=DecisionRecord(id=secrets.token_hex(12),tenant_id=actor.tenant,owner=actor.user,risk_tier='unassessed',confidence_basis='unknown',**data.model_dump())
        db.add(row);events(db,actor,'decision.proposed',row.id,{'title':data.title,'evidence_refs':data.evidence_refs});db.commit()
        return decision_json(row)

    @router.post('/decisions/{decision_id}/outcome')
    def observe_outcome(decision_id:str,data:OutcomeUpdate,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','finance','reviewer'})
        row=db.scalar(select(DecisionRecord).where(DecisionRecord.id==decision_id,DecisionRecord.tenant_id==actor.tenant))
        if not row:raise HTTPException(404,'Decision not found')
        count=db.execute(update(DecisionRecord).where(DecisionRecord.id==decision_id,DecisionRecord.tenant_id==actor.tenant,DecisionRecord.version==data.expected_version).values(outcome=data.outcome,outcome_source=data.source_ref,state='outcome_reported',version=DecisionRecord.version+1)).rowcount
        if count!=1:raise HTTPException(409,'Version conflict; refresh decision')
        events(db,actor,'decision.outcome_reported',decision_id,{'outcome':data.outcome,'source_ref':data.source_ref})
        db.commit();return {'status':'outcome_reported','version':data.expected_version+1,'evidence_status':'self_reported'}

    @router.get('/memory')
    def business_memory(q:str='',actor=Depends(identity),db:Session=Depends(session)):
        # Deliberately transparent keyword search: no fabricated semantic relevance scores.
        query=q.strip().casefold()
        rows=db.scalars(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant)).all()
        results=[]
        for d in rows:
            text=' '.join([d.title,d.rationale,d.option_chosen,d.outcome,*d.assumptions]).casefold()
            if not query or all(word in text for word in query.split()): results.append(decision_json(d))
        return {'method':'literal keyword match','count':len(results),'decisions':results[:100]}

    @router.get('/records')
    def list_records(kind:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
        if kind and kind not in VALID_KINDS:raise HTTPException(422,'Unknown office record type')
        q=select(OfficeRecord).where(OfficeRecord.tenant_id==actor.tenant)
        if kind:q=q.where(OfficeRecord.kind==kind)
        return [office_json(r) for r in db.scalars(q.order_by(OfficeRecord.created_at.desc())).all()]

    @router.post('/records',status_code=201)
    def create_record(data:NewOfficeRecord,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor','finance'})
        if data.kind not in VALID_KINDS or data.evidence_status not in ('modeled','self_reported'):
            raise HTTPException(422,'Unsupported kind or evidence classification; reviewer actions are separate')
        if len(json.dumps(data.payload,allow_nan=False))>30000:raise HTTPException(413,'Payload too large')
        # Relationship is validated in the API, not trusted from client-supplied JSON.
        linked=data.payload.get('initiative_id')
        if data.kind in {'risk','economics','agent','copilot','workforce'} and not linked:
            raise HTTPException(422,'Choose an existing initiative')
        if linked:find_initiative(db,actor,str(linked))
        if data.request_id:
            stable_id=hashlib.sha256(f'{actor.tenant}:office:{data.request_id}'.encode()).hexdigest()[:24]
            existing=db.scalar(select(OfficeRecord).where(OfficeRecord.id==stable_id,OfficeRecord.tenant_id==actor.tenant))
            if existing:return office_json(existing)
        else:stable_id=secrets.token_hex(12)
        row=OfficeRecord(id=stable_id,tenant_id=actor.tenant,**data.model_dump(exclude={'request_id'}))
        db.add(row);events(db,actor,'office.created',row.id,{'kind':row.kind,'name':row.name});db.commit()
        return office_json(row)

    @router.put('/records/{record_id}')
    def update_record(record_id:str,data:OfficeUpdate,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','lead','editor','finance'})
        if len(json.dumps(data.payload,allow_nan=False))>30000:raise HTTPException(413,'Payload too large')
        linked=data.payload.get('initiative_id')
        if linked:find_initiative(db,actor,str(linked))
        count=db.execute(update(OfficeRecord).where(OfficeRecord.id==record_id,OfficeRecord.tenant_id==actor.tenant,OfficeRecord.version==data.expected_version).values(payload=data.payload,evidence_status='self_reported',version=OfficeRecord.version+1)).rowcount
        if count!=1:raise HTTPException(409,'Record missing or changed; refresh')
        events(db,actor,'office.updated',record_id,{'payload_changed':True});db.commit()
        return {'version':data.expected_version+1,'classification':'self_reported'}

    @router.get('/executive')
    def executive_snapshot(actor=Depends(identity),db:Session=Depends(session)):
        initiatives=db.scalars(select(Initiative).where(Initiative.tenant_id==actor.tenant)).all()
        benefits=db.scalars(select(Benefit).where(Benefit.tenant_id==actor.tenant)).all()
        decisions=db.scalars(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant)).all()
        records=db.scalars(select(OfficeRecord).where(OfficeRecord.tenant_id==actor.tenant)).all()
        return {'initiatives':len(initiatives),'decisions':len(decisions),
                'observed_decision_outcomes':sum(bool(d.outcome) for d in decisions),
                'planned_benefits':round(sum(b.planned for b in benefits),2),
                'self_reported_benefits':round(sum(b.reported for b in benefits),2),
                'self_reported_run_cost':round(sum(b.run_cost for b in benefits),2),
                'verified_financial_value':None,
                'office_counts':{k:sum(r.kind==k for r in records) for k in sorted(VALID_KINDS)},
                'disclosure':'Benefit observations are self-reported; no financial reconciliation performed.'}

    @router.post('/scenario')
    def scenario(request:ScenarioRequest,actor=Depends(identity)):
        require(actor,{'admin','lead','editor','finance','reviewer','approver'})
        from . import legacy_engines as L
        items=[]
        for j,p in enumerate(request.candidates):
            value=finite_nonneg(p.get('expected_value',0),'expected_value')
            cost=finite_nonneg(p.get('cost',0),'cost')
            items.append({'id':'candidate_'+str(j),'name':str(p.get('name',f'Initiative {j+1}'))[:120],
                          'impact':value,'cost':cost,'category':str(p.get('category','AI'))[:50],
                          'risk':0.,'secondary':0.,'requires':''})
        spec,errors=L.make_spec(items,request.budget,min(request.max_items,len(items)))
        if errors:raise HTTPException(422,errors)
        result=L.solve_portfolio(spec)
        if result['status']!='OPTIMAL':return {'status':result['status'],'disclosure':'Modeled values only'}
        chosen=[int(s.split('_')[-1]) for s in result['selected']]
        return {'status':result['status'],'selected':[request.candidates[i].get('name') for i in chosen],
                'total_expected_value':result['metrics']['impact'],'total_cost':result['metrics']['cost'],
                'budget':request.budget,'solver':result['method'],
                'disclosure':'Hypothetical scenario, not a forecast or independently verified ROI.'}

    @router.get('/economics-summary')
    def economics_summary(actor=Depends(identity),db:Session=Depends(session)):
        rows=db.scalars(select(OfficeRecord).where(OfficeRecord.tenant_id==actor.tenant,OfficeRecord.kind.in_(['economics','agent','copilot']))).all()
        items=[]
        for r in rows:
            p=r.payload
            runs=finite_nonneg(p.get('task_count',0),'task_count'); costs=finite_nonneg(p.get('cost_usd',0),'cost_usd')
            successes=finite_nonneg(p.get('successful_tasks',0),'successful_tasks')
            if successes>runs:raise HTTPException(422,'successful_tasks exceed task_count')
            items.append({'name':r.name,'kind':r.kind,'task_count':runs,'successful_tasks':successes,
                          'cost_usd':costs,'cost_per_task':round(costs/runs,4) if runs else None,
                          'cost_per_success':round(costs/successes,4) if successes else None,
                          'evidence_status':r.evidence_status})
        return {'items':items,'note':'Cost and usage entries are user-supplied, not system telemetry.'}

    @router.post('/executive-narrative')
    def executive_narrative(data:ExecutiveNarrativeRequest,actor=Depends(identity),db:Session=Depends(session)):
        # Deterministic and traceable; cannot hallucinate unsupported insights.
        ins=db.scalars(select(Initiative).where(Initiative.tenant_id==actor.tenant)).all()
        benefits=db.scalars(select(Benefit).where(Benefit.tenant_id==actor.tenant)).all()
        decisions=db.scalars(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant)).all()
        risks=db.scalars(select(OfficeRecord).where(OfficeRecord.tenant_id==actor.tenant,OfficeRecord.kind=='risk')).all()
        planned=sum(b.planned for b in benefits); reported=sum(b.reported for b in benefits); run=sum(b.run_cost for b in benefits)
        classified={}
        for row in benefits:
            key=row.classification or 'unclassified'
            classified[key]=classified.get(key,0)+1
        # Do not infer finance reconciliation from a user's text or OfficeRecord label.
        # This deployment has no independent finance certification workflow.
        supported_finance=0
        narrative=(f'Enterprise AI review: {len(ins)} initiatives and {len(decisions)} recorded investment decisions. '
                   f'Across {len(benefits)} benefit entries, planned value is ${planned:,.0f}; '
                   f'reported gross is ${reported:,.0f}; reported operating cost is ${run:,.0f}. '
                   f'{len(risks)} registered transformation risks. '
                   + ('No benefit entries are independently finance-reconciled in this deployment.'
                      if supported_finance==0 else f'{supported_finance} entries have finance-certified evidence.'))
        return {'audience':data.audience,'narrative':narrative,'counts_by_classification':classified,
                'finance_reconciled_count':supported_finance,'finance_reconciled_value':None,
                'source_refs':['/v1/initiatives','/v1/value-tower','/v1/intelligence/decisions','/v1/intelligence/records?kind=risk'],
                'status':'DRAFT - REQUIRES HUMAN REVIEW','generated_by':'deterministic template; no model invoked'}

    return router
