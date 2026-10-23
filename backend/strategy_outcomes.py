"""R5.5 Strategy-to-Outcomes. Additive, tenant-scoped normalized tables.
Observations and experiment results are append-only application records.
No inference of causal attribution, confidence, or financial reconciliation.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Session

from .db import Base
from .execution import ExecutionTask
from .intelligence import DecisionRecord


def now():return datetime.now(UTC)
def new_id():return secrets.token_hex(16)

class FocusArea(Base):
    __tablename__='so_focus_areas'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    title=Column(String(180),nullable=False);owner=Column(String(120),nullable=False)
    description=Column(String(2000),nullable=False,default='');version=Column(Integer,nullable=False,default=1)
    created_at=Column(DateTime(timezone=True),nullable=False,default=now)
class Objective(Base):
    __tablename__='so_objectives'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    focus_id=Column(String(48),ForeignKey('so_focus_areas.id'),nullable=False)
    title=Column(String(180),nullable=False);owner=Column(String(120),nullable=False)
    horizon=Column(String(10),nullable=False);version=Column(Integer,nullable=False,default=1)
class KeyResult(Base):
    __tablename__='so_key_results'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    objective_id=Column(String(48),ForeignKey('so_objectives.id'),nullable=False)
    title=Column(String(180),nullable=False);unit=Column(String(48),nullable=False)
    direction=Column(String(20),nullable=False);baseline=Column(Float,nullable=False)
    target=Column(Float,nullable=False);target_date=Column(String(10),nullable=False)
    measurement_owner=Column(String(120),nullable=False)
    stale_after_days=Column(Integer,nullable=False,default=7)
    version=Column(Integer,nullable=False,default=1)
class StrategyDecisionLink(Base):
    __tablename__='so_decision_links'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    key_result_id=Column(String(48),ForeignKey('so_key_results.id'),nullable=False)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','key_result_id','decision_id',name='uq_so_kr_decision'),)
class Observation(Base):
    __tablename__='so_observations'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    key_result_id=Column(String(48),ForeignKey('so_key_results.id'),nullable=False)
    value=Column(Float,nullable=False);observed_at=Column(DateTime(timezone=True),nullable=False)
    source=Column(String(30),nullable=False);source_ref=Column(String(500),nullable=False)
    confidence=Column(String(20),nullable=False);attribution=Column(String(20),nullable=False)
    limitations=Column(String(2000),nullable=False,default='')
    verification=Column(String(30),nullable=False,default='self_reported')
    submitted_by=Column(String(120),nullable=False);created_at=Column(DateTime(timezone=True),nullable=False,default=now)
class Assumption(Base):
    __tablename__='so_assumptions'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False)
    statement=Column(String(1200),nullable=False);confidence=Column(String(20),nullable=False)
    validation_status=Column(String(24),nullable=False,default='unknown')
    evidence_ref=Column(String(500),nullable=False,default='')
    version=Column(Integer,nullable=False,default=1)
class DiscoveryExperiment(Base):
    __tablename__='so_experiments'
    id=Column(String(48),primary_key=True);tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False)
    customer_job=Column(String(1000),nullable=False);segment=Column(String(200),nullable=False)
    hypothesis=Column(String(1500),nullable=False);method=Column(String(32),nullable=False)
    metric=Column(String(120),nullable=False);direction=Column(String(20),nullable=False)
    threshold=Column(Float,nullable=False);evidence_ref=Column(String(500),nullable=False)
    observed_value=Column(Float,nullable=True);evaluated_at=Column(DateTime(timezone=True),nullable=True)
    result=Column(String(24),nullable=False,default='pending');version=Column(Integer,nullable=False,default=1)

class FocusIn(BaseModel):
    title:str=Field(min_length=5,max_length=180)
    owner:str=Field(min_length=2,max_length=120)
    description:str=Field(default='',max_length=2000)
class ObjectiveIn(BaseModel):
    focus_id:str;title:str=Field(min_length=5,max_length=180)
    owner:str=Field(min_length=2,max_length=120);horizon:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
class KeyResultIn(BaseModel):
    objective_id:str;title:str=Field(min_length=5,max_length=180)
    unit:str=Field(min_length=1,max_length=48)
    direction:str=Field(pattern=r'^(higher|lower)$')
    baseline:float=Field(allow_inf_nan=False);target:float=Field(allow_inf_nan=False)
    target_date:str=Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    measurement_owner:str=Field(min_length=2,max_length=120)
    stale_after_days:int=Field(default=7,ge=1,le=365)
class LinkIn(BaseModel):
    key_result_id:str;decision_id:str
class ObservationIn(BaseModel):
    key_result_id:str;value:float=Field(allow_inf_nan=False)
    observed_at:datetime;source:str=Field(pattern='^(manual|telemetry|financial_system|survey|composite)$')
    source_ref:str=Field(min_length=3,max_length=500)
    confidence:str=Field(pattern='^(high|moderate|low|unknown)$')
    attribution:str=Field(pattern='^(causal|correlated|estimated|unattributed)$')
    limitations:str=Field(default='',max_length=2000)
class AssumptionIn(BaseModel):
    decision_id:str;statement:str=Field(min_length=10,max_length=1200)
    confidence:str=Field(pattern='^(high|moderate|low|unknown)$')
    evidence_ref:str=Field(default='',max_length=500)
class ExperimentIn(BaseModel):
    decision_id:str;customer_job:str=Field(min_length=10,max_length=1000)
    segment:str=Field(min_length=2,max_length=200)
    hypothesis:str=Field(min_length=10,max_length=1500)
    method:str=Field(pattern='^(prototype|pilot|ab_test|concierge|wizard_of_oz)$')
    metric:str=Field(min_length=2,max_length=120)
    direction:str=Field(pattern='^(higher|lower)$')
    threshold:float=Field(allow_inf_nan=False)
    evidence_ref:str=Field(min_length=3,max_length=500)
class ExperimentResultIn(BaseModel):
    expected_version:int=Field(ge=1)
    observed_value:float=Field(allow_inf_nan=False)
    evidence_ref:str=Field(min_length=3,max_length=500)
class AssumptionReviewIn(BaseModel):
    expected_version:int=Field(ge=1)
    validation_status:str=Field(pattern='^(under_test|supported|invalidated|unknown)$')
    evidence_ref:str=Field(min_length=3,max_length=500)

def get(db,model,ident,tenant):
    obj=db.scalar(select(model).where(model.id==ident,model.tenant_id==tenant))
    if obj is None:raise HTTPException(404,'Not found')
    return obj

def body(r):
    return {c.name:(v.isoformat() if isinstance((v:=getattr(r,c.name)),datetime) else v) for c in r.__table__.columns}

def status(kr,obs,at=None):
    if not obs:return {'state':'NO_DATA','observation':None,'reason':'No recorded observation'}
    at=at or now()
    date=obs.observed_at.replace(tzinfo=UTC) if obs.observed_at.tzinfo is None else obs.observed_at
    age=(at-date).total_seconds()/86400
    if age>kr.stale_after_days:return {'state':'STALE','age_days':round(age,1),'observation':body(obs),'reason':'Observation exceeds freshness threshold'}
    meets=obs.value>=kr.target if kr.direction=='higher' else obs.value<=kr.target
    return {'state':'TARGET_MET_OBSERVED' if meets else 'IN_PROGRESS','age_days':round(age,1),'observation':body(obs),
            'gap':round(obs.value-kr.target,6),'reason':'Observed target is not independently attributed or verified by this status'}

def build_router(identity,session,require,events,find_initiative):
    router=APIRouter(prefix='/v1/strategy',tags=['Strategy-to-Outcomes R5.5'])
    def canwrite(actor):require(actor,{'admin','lead','editor'})
    def commit(db,actor,kind,obj):
        events(db,actor,kind,obj.id,{'record':obj.__tablename__});db.commit();db.refresh(obj);return body(obj)
    def getdecision(db,actor,id):
        d=get(db,DecisionRecord,id,actor.tenant)
        find_initiative(db,actor,d.initiative_id)
        return d
    @router.post('/focus-areas',status_code=201)
    def create_focus(p:FocusIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);r=FocusArea(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.focus.created',r)
    @router.get('/focus-areas')
    def list_focus(actor=Depends(identity),db:Session=Depends(session)):
        return [body(r) for r in db.scalars(select(FocusArea).where(FocusArea.tenant_id==actor.tenant))]
    @router.post('/objectives',status_code=201)
    def create_obj(p:ObjectiveIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);get(db,FocusArea,p.focus_id,actor.tenant)
        r=Objective(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.objective.created',r)
    @router.get('/objectives')
    def list_objs(actor=Depends(identity),db:Session=Depends(session)):
        return [body(r) for r in db.scalars(select(Objective).where(Objective.tenant_id==actor.tenant))]
    @router.post('/key-results',status_code=201)
    def create_kr(p:KeyResultIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);get(db,Objective,p.objective_id,actor.tenant)
        if p.baseline==p.target:raise HTTPException(422,'Target must differ from baseline')
        r=KeyResult(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.kr.created',r)
    @router.get('/key-results')
    def list_kr(actor=Depends(identity),db:Session=Depends(session)):
        rows=db.scalars(select(KeyResult).where(KeyResult.tenant_id==actor.tenant)).all();out=[]
        for r in rows:
            obs=db.scalar(select(Observation).where(Observation.tenant_id==actor.tenant,Observation.key_result_id==r.id).order_by(Observation.observed_at.desc(),Observation.created_at.desc()))
            out.append({**body(r),'measurement':status(r,obs)})
        return out
    @router.post('/decision-links',status_code=201)
    def link(p:LinkIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);get(db,KeyResult,p.key_result_id,actor.tenant);getdecision(db,actor,p.decision_id)
        existing=db.scalar(select(StrategyDecisionLink).where(StrategyDecisionLink.tenant_id==actor.tenant,StrategyDecisionLink.key_result_id==p.key_result_id,StrategyDecisionLink.decision_id==p.decision_id))
        if existing:return body(existing)
        r=StrategyDecisionLink(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.decision.linked',r)
    @router.get('/decision-links')
    def links(actor=Depends(identity),db:Session=Depends(session)):
        return [body(r) for r in db.scalars(select(StrategyDecisionLink).where(StrategyDecisionLink.tenant_id==actor.tenant))]
    @router.post('/observations',status_code=201)
    def observe(p:ObservationIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);get(db,KeyResult,p.key_result_id,actor.tenant)
        if p.observed_at>now()+timedelta(minutes=5):raise HTTPException(422,'Observation timestamp cannot be in the future')
        if p.attribution=='causal' and not p.limitations.strip():raise HTTPException(422,'Causal attribution requires a documented identification method in limitations')
        r=Observation(id=new_id(),tenant_id=actor.tenant,submitted_by=actor.user,**p.model_dump());db.add(r);return commit(db,actor,'strategy.observation.recorded',r)
    @router.post('/assumptions',status_code=201)
    def assumption(p:AssumptionIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);getdecision(db,actor,p.decision_id)
        r=Assumption(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.assumption.created',r)
    @router.get('/assumptions')
    def assumptions(actor=Depends(identity),db:Session=Depends(session)):
        return [body(r) for r in db.scalars(select(Assumption).where(Assumption.tenant_id==actor.tenant))]
    @router.post('/assumptions/{ident}/review')
    def review_assumption(ident:str,p:AssumptionReviewIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','risk'});r=get(db,Assumption,ident,actor.tenant)
        if r.version!=p.expected_version:raise HTTPException(409,'Version changed')
        r.validation_status=p.validation_status;r.evidence_ref=p.evidence_ref;r.version+=1
        return commit(db,actor,'strategy.assumption.reviewed',r)
    @router.post('/experiments',status_code=201)
    def experiment(p:ExperimentIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);getdecision(db,actor,p.decision_id)
        r=DiscoveryExperiment(id=new_id(),tenant_id=actor.tenant,**p.model_dump());db.add(r);return commit(db,actor,'strategy.experiment.created',r)
    @router.get('/experiments')
    def experiments(actor=Depends(identity),db:Session=Depends(session)):
        return [body(r) for r in db.scalars(select(DiscoveryExperiment).where(DiscoveryExperiment.tenant_id==actor.tenant))]
    @router.post('/experiments/{ident}/result')
    def experiment_result(ident:str,p:ExperimentResultIn,actor=Depends(identity),db:Session=Depends(session)):
        canwrite(actor);r=get(db,DiscoveryExperiment,ident,actor.tenant)
        if r.version!=p.expected_version:raise HTTPException(409,'Version changed')
        if r.result!='pending':raise HTTPException(409,'Experiment already evaluated')
        r.observed_value=p.observed_value;r.evaluated_at=now()
        r.result='supported' if (p.observed_value>=r.threshold if r.direction=='higher' else p.observed_value<=r.threshold) else 'not_supported'
        r.evidence_ref=p.evidence_ref;r.version+=1
        return commit(db,actor,'strategy.experiment.evaluated',r)
    @router.get('/lineage/{decision_id}')
    def lineage(decision_id:str,actor=Depends(identity),db:Session=Depends(session)):
        d=getdecision(db,actor,decision_id)
        links=db.scalars(select(StrategyDecisionLink).where(StrategyDecisionLink.tenant_id==actor.tenant,StrategyDecisionLink.decision_id==d.id)).all()
        chain=[]
        for l in links:
            kr=get(db,KeyResult,l.key_result_id,actor.tenant);obj=get(db,Objective,kr.objective_id,actor.tenant);focus=get(db,FocusArea,obj.focus_id,actor.tenant)
            chain.append({'focus_area':body(focus),'objective':body(obj),'key_result':body(kr),'link':body(l)})
        return {'decision':{'id':d.id,'title':d.title,'initiative_id':d.initiative_id},'initiative':d.initiative_id,'chains':chain,
                'assumptions':[body(x) for x in db.scalars(select(Assumption).where(Assumption.tenant_id==actor.tenant,Assumption.decision_id==d.id))],
                'experiments':[body(x) for x in db.scalars(select(DiscoveryExperiment).where(DiscoveryExperiment.tenant_id==actor.tenant,DiscoveryExperiment.decision_id==d.id))],
                'execution_tasks':[{'id':x.id,'title':x.title,'status':x.status,'technical_stage':x.technical_stage,'business_stage':x.business_stage} for x in db.scalars(select(ExecutionTask).where(ExecutionTask.tenant_id==actor.tenant,ExecutionTask.decision_id==d.id,ExecutionTask.initiative_id==d.initiative_id))]}
    return router
