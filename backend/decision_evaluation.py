"""R5.6 additive Decision Evaluation Contract.

A frozen evaluation is a *process assessment*, not approval of a decision or proof
of causal impact. Application-level append-only; DB superusers still require
separate immutability controls (WORM/anchoring).
"""
from __future__ import annotations
import hashlib, json, secrets
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, select, update
from sqlalchemy.orm import Session
from sqlalchemy.types import JSON
from .db import Base
from .intelligence import DecisionRecord
from .decision_governance import ActionPacket
from .strategy_outcomes import Assumption, StrategyDecisionLink, KeyResult, Observation

RUBRIC_VERSION='r5.6-evaluation-1'
WEIGHTS={'evidence':20,'economics':15,'risk':15,'counterfactual':15,'alternatives':10,'accountability':15,'measurement':10}
ATTRIBUTION=('experimental','quasi_experimental','correlational','estimated','unknown')

class DecisionEvaluation(Base):
    __tablename__='di_evaluations'
    id=Column(String(48), primary_key=True)
    tenant_id=Column(String(64),nullable=False,index=True)
    decision_id=Column(String(48),ForeignKey('di_decisions.id'),nullable=False,index=True)
    rubric_version=Column(String(64),nullable=False)
    status=Column(String(24),nullable=False,default='draft')
    answers=Column(JSON,nullable=False)
    author=Column(String(120),nullable=False)
    reviewer=Column(String(120),nullable=True)
    score=Column(Integer,nullable=True)
    context=Column(JSON,nullable=True)
    content_hash=Column(String(64),nullable=True)
    created_at=Column(DateTime(timezone=True),nullable=False,default=lambda:datetime.now(timezone.utc))
    locked_at=Column(DateTime(timezone=True),nullable=True)
    request_id=Column(String(100),nullable=False)
    __table_args__=(UniqueConstraint('tenant_id','request_id',name='uq_di_eval_request'),)

class Answer(BaseModel):
    state:Literal['verified','provisional','missing','not_applicable']
    evidence_ref:str=Field(default='',max_length=500)
    explanation:str=Field(default='',max_length=1000)

class DraftIn(BaseModel):
    decision_id:str
    answers:dict[str,Answer]
    request_id:str=Field(min_length=12,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')

class LockIn(BaseModel):
    expected_status:Literal['draft']='draft'
    confirmation:Literal['I have independently reviewed the evidence and accept the limitations.']

class AttributionIn(BaseModel):
    label:Literal['experimental','quasi_experimental','correlational','estimated','unknown']
    evidence_ref:str=Field(default='',max_length=500)
    limitations:str=Field(min_length=10,max_length=2000)


def canonical(obj):return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def content_hash(obj):return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()

def score_answers(answers:dict)->dict:
    """No partial numerical score; N/A requires reviewed rationale and adjusted denominator."""
    errors=[]; numerator=denominator=0
    for name,weight in WEIGHTS.items():
        a=answers.get(name)
        if not a:errors.append(f'{name}: missing assessment');continue
        state=a.get('state') if isinstance(a,dict) else a.state
        ref=a.get('evidence_ref','') if isinstance(a,dict) else a.evidence_ref
        why=a.get('explanation','') if isinstance(a,dict) else a.explanation
        if state=='not_applicable':
            if len(why.strip())<20:errors.append(f'{name}: N/A requires a meaningful rationale')
            continue
        denominator+=weight
        if state=='verified':
            if len(ref.strip())<3:errors.append(f'{name}: verified evidence reference required')
            else:numerator+=weight
        elif state=='provisional':errors.append(f'{name}: provisional evidence requires independent verification')
        elif state=='missing':errors.append(f'{name}: required evidence missing')
        else:errors.append(f'{name}: invalid status')
    if denominator==0:errors.append('No applicable scoring controls')
    return {'score':round(100*numerator/denominator) if not errors and denominator else None,
            'verified_weight':numerator,'applicable_weight':denominator,'errors':errors,'rubric_version':RUBRIC_VERSION}


def outcome_language(attribution:str)->str:
    if attribution in ('experimental','quasi_experimental'):
        return 'Causal analysis reported; verify study design, assumptions, bias and limitations before asserting causality.'
    return 'Causality not established. The observation cannot be attributed to this AI intervention.'


def build_router(identity,session,require,events,find_initiative):
    router=APIRouter(prefix='/v1/decision-evaluation',tags=['R5.6 Decision Evaluation'])
    def own_decision(db,actor,did):
        d=db.scalar(select(DecisionRecord).where(DecisionRecord.tenant_id==actor.tenant,DecisionRecord.id==did))
        if d is None:raise HTTPException(404,'Decision not available')
        return d
    def own_eval(db,actor,eid):
        row=db.scalar(select(DecisionEvaluation).where(DecisionEvaluation.tenant_id==actor.tenant,DecisionEvaluation.id==eid))
        if row is None:raise HTTPException(404,'Evaluation not available')
        return row
    def view(e):
        data={'id':e.id,'decision_id':e.decision_id,'rubric_version':e.rubric_version,'status':e.status,'answers':e.answers,
              'author':e.author,'reviewer':e.reviewer,'score':e.score,'created_at':str(e.created_at),'locked_at':str(e.locked_at) if e.locked_at else None,
              'context':e.context,'content_hash':e.content_hash}
        data['hash_valid']=content_hash({'decision_id':e.decision_id,'rubric_version':e.rubric_version,'answers':e.answers,'context':e.context,'score':e.score,'author':e.author,'reviewer':e.reviewer,'locked_at':e.locked_at.replace(tzinfo=timezone.utc).isoformat()})==e.content_hash if e.content_hash and e.locked_at else None
        return data

    @router.get('/rubric')
    def rubric(actor=Depends(identity)):
        return {'version':RUBRIC_VERSION,'weights':WEIGHTS,'allowed_states':['verified','provisional','missing','not_applicable'],'notice':'A score measures assessed process completeness, not decision correctness. All verified responses still require independent review.'}

    @router.get('/decisions/{did}')
    def list_evals(did:str,actor=Depends(identity),db:Session=Depends(session)):
        own_decision(db,actor,did)
        return [view(e) for e in db.scalars(select(DecisionEvaluation).where(DecisionEvaluation.tenant_id==actor.tenant,DecisionEvaluation.decision_id==did).order_by(DecisionEvaluation.created_at.desc())).all()]

    @router.post('/draft',status_code=201)
    def draft(data:DraftIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'lead','admin','editor','finance','risk'})
        own_decision(db,actor,data.decision_id)
        if set(data.answers)!=set(WEIGHTS):raise HTTPException(422,'Answer each of the seven rubric domains')
        prior=db.scalar(select(DecisionEvaluation).where(DecisionEvaluation.tenant_id==actor.tenant,DecisionEvaluation.request_id==data.request_id))
        if prior:
            if prior.decision_id!=data.decision_id or prior.answers!={k:v.model_dump() for k,v in data.answers.items()}:raise HTTPException(409,'Idempotency key reused for different submission')
            return view(prior)
        row=DecisionEvaluation(id=secrets.token_hex(16),tenant_id=actor.tenant,decision_id=data.decision_id,rubric_version=RUBRIC_VERSION,
            author=actor.user,request_id=data.request_id,answers={k:v.model_dump() for k,v in data.answers.items()})
        db.add(row);db.flush();events(db,actor,'evaluation.drafted',row.id,{'decision_id':row.decision_id});db.commit();return view(row)

    @router.post('/{eid}/lock')
    def lock(eid:str,data:LockIn,actor=Depends(identity),db:Session=Depends(session)):
        require(actor,{'admin','reviewer','risk'})
        e=own_eval(db,actor,eid)
        if e.status!='draft':raise HTTPException(409,'Already locked; create a new evaluation version')
        if e.author==actor.user:raise HTTPException(403,'Independent reviewer required')
        d=own_decision(db,actor,e.decision_id)
        checks=score_answers(e.answers)
        if checks['errors']:raise HTTPException(409,{'reason':'Insufficient verified evidence','missing':checks['errors']})
        # Lock is available only after separately governed approval, and captures the
        # approval reference; does not itself approve an investment or execution.
        approved=db.scalar(select(ActionPacket).where(ActionPacket.tenant_id==actor.tenant,ActionPacket.decision_id==d.id,ActionPacket.status=='approved').order_by(ActionPacket.approved_at.desc()))
        if approved is None:raise HTTPException(409,'No independently approved Action Packet available to anchor evaluation')
        if approved.approval_by==actor.user:raise HTTPException(403,'Evaluation reviewer must differ from approving reviewer')
        assumptions=db.scalars(select(Assumption).where(Assumption.tenant_id==actor.tenant,Assumption.decision_id==d.id)).all()
        links=db.scalars(select(StrategyDecisionLink).where(StrategyDecisionLink.tenant_id==actor.tenant,StrategyDecisionLink.decision_id==d.id)).all()
        kr_ids=[l.key_result_id for l in links]
        krs=db.scalars(select(KeyResult).where(KeyResult.tenant_id==actor.tenant,KeyResult.id.in_(kr_ids))).all() if kr_ids else []
        observations=db.scalars(select(Observation).where(Observation.tenant_id==actor.tenant,Observation.key_result_id.in_(kr_ids))).all() if kr_ids else []
        context={'decision':{'id':d.id,'version':d.version,'title':d.title,'rationale':d.rationale,'assumptions':d.assumptions,
                'evidence_refs':d.evidence_refs,'confidence_basis':d.confidence_basis},
                 'approved_packet':{'id':approved.id,'version':approved.version,'approval_by':approved.approval_by,'approved_at':str(approved.approved_at),'policy':approved.policy_approval},
                 'assumptions':[{'id':a.id,'version':a.version,'statement':a.statement,'status':a.validation_status,'evidence_ref':a.evidence_ref} for a in assumptions],
                 'key_results':[{'id':k.id,'version':k.version,'target':k.target,'unit':k.unit} for k in krs],
                 'observations':[{'id':o.id,'value':o.value,'source_ref':o.source_ref,'attribution':o.attribution,'limitations':o.limitations} for o in observations],
                 'snapshot_limitations':'References are captured as represented in the current database; evidence bytes and external documents are not WORM-archived.'}
        # Compare-and-swap rejects concurrent attempts to lock the same draft.
        updated=db.execute(update(DecisionEvaluation).where(DecisionEvaluation.id==eid,DecisionEvaluation.tenant_id==actor.tenant,DecisionEvaluation.status=='draft').values(status='locked')).rowcount
        if updated!=1:raise HTTPException(409,'Evaluation already locked by another reviewer')
        e.context=context;e.score=checks['score'];e.reviewer=actor.user;e.locked_at=datetime.now(timezone.utc);e.status='locked'
        e.content_hash=content_hash({'decision_id':e.decision_id,'rubric_version':e.rubric_version,'answers':e.answers,'context':e.context,'score':e.score,'author':e.author,'reviewer':e.reviewer,'locked_at':e.locked_at.isoformat()})
        events(db,actor,'evaluation.locked',eid,{'snapshot_sha256':e.content_hash,'rubric_version':RUBRIC_VERSION})
        db.commit();return view(e)

    return router
