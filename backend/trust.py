"""R5 Trust Office: guarded, tenant-scoped attestations and imported evaluation findings.
No regulation classification is a legal determination; no automatic security scan is claimed.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .intelligence import DecisionRecord
from .models import AIControlEvidence, AIRiskAssessment, RedTeamFinding

FRAMEWORKS={
 'NIST_AI_RMF':('GOVERN','MAP','MEASURE','MANAGE'),
 'NIST_AI_RMF_GENAI':('GOVERN','MAP','MEASURE','MANAGE'),
 'EU_AI_ACT':('prohibited_practices_review','high_risk_applicability','transparency_review','human_oversight','technical_documentation','logging','post_market_monitoring'),
 'OWASP_LLM':('LLM01','LLM02','LLM03','LLM04','LLM05','LLM06','LLM07','LLM08','LLM09','LLM10')
}
SEVERITY={'critical','high','medium','low','informational'}
CLASSIFICATIONS={'review_required','potential_high_risk','potential_prohibited','transparency_review','other_assessed'}

class NewAssessment(BaseModel):
 initiative_id:str;decision_id:str
 request_id:str|None=Field(default=None,min_length=16,max_length=100,pattern=r'^[a-zA-Z0-9_-]+$')
 title:str=Field(min_length=3,max_length=180)
 ai_role:str=Field(pattern='^(provider|deployer|other|unknown)$')
 geography:str=Field(min_length=2,max_length=100)
 intended_use:str=Field(min_length=10,max_length=5000)
 risk_factors:dict=Field(default_factory=dict)
 classification:str='review_required'
 owner:str=Field(min_length=2,max_length=120)
 assessment_source:str=Field(min_length=3,max_length=500)

class ReviewAssessment(BaseModel):
 expected_version:int=Field(ge=1)
 decision:str=Field(pattern='^(accept_for_review|needs_changes)$')
 note:str=Field(min_length=5,max_length=2000)

class NewControl(BaseModel):
 framework:str;control_id:str
 evidence_reference:str=Field(min_length=3,max_length=2000)
 evidence_quality:str=Field(pattern='^(self_reported|measured|independently_checked)$',default='self_reported')

class FindingInput(BaseModel):
 source_tool:str=Field(pattern='^(pyrit|garak|manual|other)$')
 source_run_id:str=Field(min_length=1,max_length=180)
 source_finding_id:str=Field(min_length=1,max_length=180)
 category:str=Field(min_length=2,max_length=100)
 severity:str=Field(pattern='^(critical|high|medium|low|informational)$')
 title:str=Field(min_length=3,max_length=220)
 evidence_reference:str=Field(min_length=3,max_length=2000)
 observed_result:str=Field(min_length=3,max_length=5000)
 remediation:str=Field(default='',max_length=4000)

class FindingsImport(BaseModel):
 format:str=Field(pattern='^(decision_os_v1|pyrit_normalized_v1)$')
 findings:list[FindingInput]=Field(min_length=1,max_length=100)

class FindingReview(BaseModel):
 expected_version:int=Field(ge=1)
 disposition:str=Field(pattern='^(triaged|remediated_pending_retest|accepted_risk|false_positive)$')
 note:str=Field(min_length=5,max_length=2000)


def assessment_dict(x):
 return {'id':x.id,'initiative_id':x.initiative_id,'decision_id':x.decision_id,'title':x.title,'ai_role':x.ai_role,'geography':x.geography,'intended_use':x.intended_use,'risk_factors':x.risk_factors,'classification':x.classification,'owner':x.owner,'assessment_source':x.assessment_source,'review_status':x.review_status,'reviewed_by':x.reviewed_by,'version':x.version}

def finding_dict(x):
 return {'id':x.id,'assessment_id':x.assessment_id,'initiative_id':x.initiative_id,'decision_id':x.decision_id,'source_tool':x.source_tool,'source_run_id':x.source_run_id,'source_finding_id':x.source_finding_id,'category':x.category,'severity':x.severity,'title':x.title,'evidence_reference':x.evidence_reference,'observed_result':x.observed_result,'remediation':x.remediation,'status':x.status,'verified_by':x.verified_by,'version':x.version}

def build_router(identity,session,require,events,find_initiative):
 router=APIRouter(prefix='/v1/trust',tags=['R5 Risk & Red Team'])
 def own_assessment(db,actor,aid):
  a=db.scalar(select(AIRiskAssessment).where(AIRiskAssessment.id==aid,AIRiskAssessment.tenant_id==actor.tenant))
  if not a:raise HTTPException(404,'Assessment not found')
  return a
 def own_finding(db,actor,fid):
  f=db.scalar(select(RedTeamFinding).where(RedTeamFinding.id==fid,RedTeamFinding.tenant_id==actor.tenant))
  if not f:raise HTTPException(404,'Finding not found')
  return f
 @router.get('/frameworks')
 def frameworks(actor=Depends(identity)):
  return {'crosswalk':FRAMEWORKS,'disclosure':'Navigation only. Check current legal obligations and published framework version with qualified reviewers.'}
 @router.post('/assessments',status_code=201)
 def create_assessment(data:NewAssessment,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'admin','lead','editor'})
  find_initiative(db,actor,data.initiative_id)
  d=db.scalar(select(DecisionRecord).where(DecisionRecord.id==data.decision_id,DecisionRecord.tenant_id==actor.tenant,DecisionRecord.initiative_id==data.initiative_id))
  if d is None:raise HTTPException(422,'Funding decision must belong to the initiative and tenant')
  if data.classification not in CLASSIFICATIONS:raise HTTPException(422,'Unknown risk classification')
  if data.classification in ('potential_high_risk','potential_prohibited') and data.ai_role=='unknown':
   # Unknown role is permitted but explicitly unresolved.
   pass
  if data.request_id:
   duplicate=db.scalar(select(AIRiskAssessment).where(AIRiskAssessment.tenant_id==actor.tenant,AIRiskAssessment.request_id==data.request_id))
   if duplicate:
    if duplicate.initiative_id!=data.initiative_id or duplicate.decision_id!=data.decision_id:raise HTTPException(409,'Submission token already used for another assessment')
    return assessment_dict(duplicate)
  row=AIRiskAssessment(id=secrets.token_hex(12),tenant_id=actor.tenant,**data.model_dump())
  db.add(row);events(db,actor,'trust.assessment_created',row.id,{'initiative_id':row.initiative_id,'decision_id':row.decision_id,'classification':row.classification})
  try:db.commit()
  except IntegrityError:
   db.rollback()
   if data.request_id:
    duplicate=db.scalar(select(AIRiskAssessment).where(AIRiskAssessment.tenant_id==actor.tenant,AIRiskAssessment.request_id==data.request_id))
    if duplicate and duplicate.initiative_id==data.initiative_id and duplicate.decision_id==data.decision_id:return assessment_dict(duplicate)
   raise HTTPException(409,'Conflicting submission; refresh and retry')
  return assessment_dict(row)
 @router.get('/assessments')
 def list_assessments(initiative_id:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
  q=select(AIRiskAssessment).where(AIRiskAssessment.tenant_id==actor.tenant)
  if initiative_id:q=q.where(AIRiskAssessment.initiative_id==initiative_id)
  return [assessment_dict(a) for a in db.scalars(q.order_by(AIRiskAssessment.created_at.desc())).all()]
 @router.get('/assessments/{aid}')
 def detail(aid:str,actor=Depends(identity),db:Session=Depends(session)):
  a=own_assessment(db,actor,aid)
  controls=db.scalars(select(AIControlEvidence).where(AIControlEvidence.tenant_id==actor.tenant,AIControlEvidence.assessment_id==aid)).all()
  findings=db.scalars(select(RedTeamFinding).where(RedTeamFinding.tenant_id==actor.tenant,RedTeamFinding.assessment_id==aid)).all()
  open_severe=[f for f in findings if f.severity in ('critical','high') and f.status!='false_positive']
  return {**assessment_dict(a),'control_evidence':[{'id':c.id,'framework':c.framework,'control_id':c.control_id,'reference':c.evidence_reference,'quality':c.evidence_quality,'status':c.status,'verified_by':c.verified_by} for c in controls], 'findings':[finding_dict(f) for f in findings], 'release_advisory':{'high_or_critical_unresolved':len(open_severe),'eligible_for_automatic_release':False,'reason':'Human-controlled gates and additional evaluations required'}, 'disclosure':'Provisional assessment, not a compliance certification.'}
 @router.post('/assessments/{aid}/review')
 def review(aid:str,data:ReviewAssessment,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'reviewer','admin'})
  row=own_assessment(db,actor,aid)
  if row.owner==actor.user:raise HTTPException(403,'Owner cannot review own assessment')
  target='reviewed' if data.decision=='accept_for_review' else 'needs_changes'
  count=db.execute(update(AIRiskAssessment).where(AIRiskAssessment.id==aid,AIRiskAssessment.tenant_id==actor.tenant,AIRiskAssessment.version==data.expected_version).values(review_status=target,reviewed_by=actor.user,review_note=data.note,version=AIRiskAssessment.version+1)).rowcount
  if count!=1:raise HTTPException(409,'Stale assessment version')
  events(db,actor,'trust.assessment_reviewed',aid,{'status':target,'note':data.note});db.commit()
  return {'status':target,'reviewed_by':actor.user,'version':data.expected_version+1,'certified_compliance':False}
 @router.post('/assessments/{aid}/controls',status_code=201)
 def submit_control(aid:str,data:NewControl,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'admin','lead','editor'})
  own_assessment(db,actor,aid)
  if data.framework not in FRAMEWORKS or data.control_id not in FRAMEWORKS[data.framework]:raise HTTPException(422,'Unsupported framework/control crosswalk')
  c=AIControlEvidence(id=secrets.token_hex(12),tenant_id=actor.tenant,assessment_id=aid,framework=data.framework,control_id=data.control_id,evidence_reference=data.evidence_reference,evidence_quality=data.evidence_quality,submitted_by=actor.user)
  db.add(c);events(db,actor,'trust.control_submitted',c.id,{'assessment_id':aid,'framework':data.framework,'control_id':data.control_id});db.commit()
  return {'id':c.id,'status':'submitted','verified':False}
 @router.post('/controls/{cid}/verify')
 def verify_control(cid:str,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'reviewer','admin'})
  c=db.scalar(select(AIControlEvidence).where(AIControlEvidence.id==cid,AIControlEvidence.tenant_id==actor.tenant))
  if not c:raise HTTPException(404,'Control evidence not found')
  if c.submitted_by==actor.user:raise HTTPException(403,'Independent reviewer required')
  if c.status!='submitted':raise HTTPException(409,'Control evidence already reviewed')
  c.status='verified';c.verified_by=actor.user
  events(db,actor,'trust.control_verified',cid,{'assessment_id':c.assessment_id});db.commit()
  return {'status':'verified','verified_by':actor.user}
 @router.post('/assessments/{aid}/findings/import',status_code=201)
 def import_findings(aid:str,data:FindingsImport,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'admin','lead','editor'})
  a=own_assessment(db,actor,aid)
  created=[];duplicates=[]
  # Normalize PyRIT outputs offline into pyrit_normalized_v1 records; do not claim arbitrary PyRIT JSON is supported.
  for f in data.findings:
   previous=db.scalar(select(RedTeamFinding).where(RedTeamFinding.tenant_id==actor.tenant,RedTeamFinding.assessment_id==aid,RedTeamFinding.source_tool==f.source_tool,RedTeamFinding.source_run_id==f.source_run_id,RedTeamFinding.source_finding_id==f.source_finding_id))
   if previous:
    duplicates.append(previous.id);continue
   row=RedTeamFinding(id=secrets.token_hex(12),tenant_id=actor.tenant,assessment_id=aid,initiative_id=a.initiative_id,decision_id=a.decision_id,reported_by=actor.user,**f.model_dump())
   db.add(row);created.append(row.id)
  events(db,actor,'trust.findings_imported',aid,{'created':len(created),'duplicate':len(duplicates),'format':data.format});db.commit()
  return {'assessment_id':aid,'decision_id':a.decision_id,'created_ids':created,'duplicate_ids':duplicates,'attestation':'imported_unverified','automatic_release':False}
 @router.get('/findings')
 def list_findings(assessment_id:str|None=None,actor=Depends(identity),db:Session=Depends(session)):
  q=select(RedTeamFinding).where(RedTeamFinding.tenant_id==actor.tenant)
  if assessment_id:q=q.where(RedTeamFinding.assessment_id==assessment_id)
  return [finding_dict(f) for f in db.scalars(q.order_by(RedTeamFinding.created_at.desc())).all()]
 @router.post('/findings/{fid}/review')
 def disposition(fid:str,data:FindingReview,actor=Depends(identity),db:Session=Depends(session)):
  require(actor,{'reviewer','admin'})
  f=own_finding(db,actor,fid)
  if f.reported_by==actor.user:raise HTTPException(403,'Finding author cannot self-review')
  n=db.execute(update(RedTeamFinding).where(RedTeamFinding.id==fid,RedTeamFinding.tenant_id==actor.tenant,RedTeamFinding.version==data.expected_version).values(status=data.disposition,verified_by=actor.user,version=RedTeamFinding.version+1)).rowcount
  if n!=1:raise HTTPException(409,'Finding version conflict')
  events(db,actor,'trust.finding_reviewed',fid,{'disposition':data.disposition,'note':data.note});db.commit()
  return {'id':fid,'status':data.disposition,'version':data.expected_version+1,'approved_for_release':False}
 @router.get('/summary')
 def summary(actor=Depends(identity),db:Session=Depends(session)):
  a=db.scalars(select(AIRiskAssessment).where(AIRiskAssessment.tenant_id==actor.tenant)).all()
  f=db.scalars(select(RedTeamFinding).where(RedTeamFinding.tenant_id==actor.tenant)).all()
  return {'assessments':len(a),'pending_review':sum(x.review_status!='reviewed' for x in a),'findings':len(f),'open_high_critical':sum(x.severity in ('critical','high') and x.status!='false_positive' for x in f),'scope':'current tenant','warning':'Risk counts are not probability-of-failure or compliance scores.'}
 return router
