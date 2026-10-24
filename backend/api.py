"""Decision OS HTTP API. API keys are deployment bootstrap credentials, NOT SSO."""
from __future__ import annotations
import os,json,secrets,re
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from fastapi import FastAPI,Depends,HTTPException,Header,Response
from pydantic import BaseModel,Field
from sqlalchemy import select,update
from sqlalchemy.orm import Session
from .core import STAGES,REQUIRED,states,descendants,fingerprint,optimize
from .db import Base,Initiative,Evidence,Approval,Benefit,Audit,WorkspaceDocument,engine_for,session_factory

_engine=None; _sessions=None

def configure(url: str | None=None):
    global _engine,_sessions
    if _engine is not None: _engine.dispose()
    _engine=engine_for(url);Base.metadata.create_all(_engine);_sessions=session_factory(_engine)

def session():
    if _sessions is None: configure()
    with _sessions() as s: yield s

class Identity(BaseModel):
    user:str
    tenant:str
    role:str

def identity(authorization: str | None=Header(default=None)) -> Identity:
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Bearer credential required')
    key=authorization[7:]
    try: registry=json.loads(os.getenv('DECISION_OS_IDENTITIES','{}'))
    except ValueError:raise HTTPException(500,'Identity configuration invalid')
    import hmac
    matched=next((v for k,v in registry.items() if hmac.compare_digest(k,key)),None)
    if matched is None: raise HTTPException(401,'Invalid credential')
    return Identity.model_validate(matched)

class NewInitiative(BaseModel):
    name:str=Field(min_length=3,max_length=180)
    owner:str=Field(min_length=2,max_length=120)
    description:str=''

class ModifyInitiative(NewInitiative):
    expected_version:int=Field(ge=1)

class NewEvidence(BaseModel):
    stage:str
    key:str
    reference:str=Field(min_length=3)
    expected_version:int=Field(ge=1)

class VerifyEvidence(BaseModel):
    expected_version:int=Field(ge=1)

class Approve(BaseModel):
    expected_version:int=Field(ge=1)

class NewBenefit(BaseModel):
    period:str=Field(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')
    planned:float=Field(ge=0,allow_inf_nan=False)
    reported:float=Field(ge=0,allow_inf_nan=False)
    run_cost:float=Field(ge=0,allow_inf_nan=False)
    evidence_reference:str=Field(min_length=3)

class OptimizeRequest(BaseModel):
    spec:dict

def require(actor:Identity,roles:set[str]):
    if actor.role not in roles:raise HTTPException(403,'Insufficient permission')

def find_initiative(db:Session,actor:Identity,iid:str)->Initiative:
    row=db.scalar(select(Initiative).where(Initiative.id==iid,Initiative.tenant_id==actor.tenant))
    if row is None:raise HTTPException(404,'Not found in tenant')
    return row

def events(db:Session,actor:Identity,event:str,entity_id:str,detail:dict):
    # Serialization of a per-tenant chain needs DB advisory locking in a multi-worker production deployment.
    last=db.scalar(select(Audit).where(Audit.tenant_id==actor.tenant).order_by(Audit.id.desc()).limit(1))
    prev=last.event_hash if last else 'GENESIS'
    doc={'tenant':actor.tenant,'actor':actor.user,'event':event,'entity':entity_id,'detail':detail,'previous':prev}
    db.add(Audit(tenant_id=actor.tenant,actor=actor.user,event=event,entity_id=entity_id,detail=detail,prev_hash=prev,event_hash=fingerprint(doc)))

def serialize(i:Initiative)->dict:
    return {'id':i.id,'name':i.name,'owner':i.owner,'description':i.description,'version':i.version}

def bump(db:Session,actor:Identity,iid:str,expected:int):
    # Compare-and-swap is one atomic SQL UPDATE; checked row count prevents lost writes.
    count=db.execute(update(Initiative).where(Initiative.id==iid,Initiative.tenant_id==actor.tenant,Initiative.version==expected).values(version=Initiative.version+1)).rowcount
    if count!=1:raise HTTPException(409,'Version conflict; refresh before retrying')

def snapshot(db:Session,actor:Identity,iid:str)->tuple[list[dict],list[dict]]:
    ev=db.scalars(select(Evidence).where(Evidence.initiative_id==iid,Evidence.tenant_id==actor.tenant)).all()
    ap=db.scalars(select(Approval).where(Approval.initiative_id==iid,Approval.tenant_id==actor.tenant)).all()
    return ([{'id':e.id,'stage':e.stage,'key':e.key,'status':e.status,'submitted_by':e.submitted_by,'verified_by':e.verified_by,'reference':e.reference,'hash':e.content_hash} for e in ev], [{'stage':a.stage,'actor':a.actor,'scope_hash':a.scope_hash} for a in ap])

app=FastAPI(title='Decision OS Enterprise API',version='0.1.0',docs_url='/docs')

@app.get('/health')
def health():return {'status':'ok','service':'decision-os'}

@app.get('/v1/me')
def me(actor:Identity=Depends(identity)):return actor.model_dump()

@app.post('/v1/initiatives',status_code=201)
def create(data:NewInitiative,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','lead','editor'})
    iid=secrets.token_hex(12); i=Initiative(id=iid,tenant_id=actor.tenant,**data.model_dump())
    db.add(i);events(db,actor,'initiative.created',iid,data.model_dump());db.commit()
    return serialize(i)

@app.get('/v1/initiatives')
def list_initiatives(actor:Identity=Depends(identity),db:Session=Depends(session)):
    return [serialize(i) for i in db.scalars(select(Initiative).where(Initiative.tenant_id==actor.tenant).order_by(Initiative.created_at.desc()))]

@app.get('/v1/initiatives/{iid}')
def detail(iid:str,actor:Identity=Depends(identity),db:Session=Depends(session)):
    i=find_initiative(db,actor,iid);ev,ap=snapshot(db,actor,iid)
    return {**serialize(i),'stages':states(ev,ap),'evidence':ev,'approvals':ap}

@app.put('/v1/initiatives/{iid}')
def revise(iid:str,data:ModifyInitiative,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','lead','editor'});find_initiative(db,actor,iid)
    bump(db,actor,iid,data.expected_version)
    db.execute(update(Initiative).where(Initiative.id==iid,Initiative.tenant_id==actor.tenant).values(**data.model_dump(exclude={'expected_version'})))
    db.query(Approval).filter_by(initiative_id=iid,tenant_id=actor.tenant).delete()
    events(db,actor,'initiative.revised',iid,{'version':data.expected_version+1});db.commit()
    return serialize(find_initiative(db,actor,iid))

@app.post('/v1/initiatives/{iid}/evidence',status_code=201)
def submit_evidence(iid:str,data:NewEvidence,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','lead','editor'});find_initiative(db,actor,iid)
    if data.stage not in REQUIRED or data.key not in REQUIRED[data.stage]:raise HTTPException(422,'Unknown stage/evidence contract')
    ev,ap=snapshot(db,actor,iid)
    current=states(ev,ap)[data.stage]
    if current['blocked_by']:raise HTTPException(409,{'blocked_by':current['blocked_by']})
    bump(db,actor,iid,data.expected_version)
    # no automatically verified evidence; reviewer must attest independently
    existing=db.scalar(select(Evidence).where(Evidence.initiative_id==iid,Evidence.stage==data.stage,Evidence.key==data.key))
    if existing:
        existing.reference=data.reference;existing.content_hash=fingerprint(data.reference);existing.submitted_by=actor.user;existing.verified_by=None;existing.status='submitted'
    else:
        db.add(Evidence(id=secrets.token_hex(12),tenant_id=actor.tenant,initiative_id=iid,stage=data.stage,key=data.key,reference=data.reference,content_hash=fingerprint(data.reference),submitted_by=actor.user,status='submitted'))
    affected=descendants(data.stage)
    db.query(Evidence).filter(Evidence.initiative_id==iid,Evidence.tenant_id==actor.tenant,Evidence.stage.in_(affected)).update({'status':'stale','verified_by':None},synchronize_session=False)
    if data.stage == 'release' or 'release' in affected:
        db.query(Approval).filter_by(initiative_id=iid,tenant_id=actor.tenant).delete()
    events(db,actor,'evidence.submitted',iid,{'stage':data.stage,'key':data.key,'hash':fingerprint(data.reference)});db.commit()
    return {'status':'submitted','version':data.expected_version+1,'invalidated_stages':sorted(affected)}

@app.post('/v1/initiatives/{iid}/evidence/{evidence_id}/verify')
def verify(iid:str,evidence_id:str,data:VerifyEvidence,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','reviewer'});find_initiative(db,actor,iid)
    ev=db.scalar(select(Evidence).where(Evidence.id==evidence_id,Evidence.initiative_id==iid,Evidence.tenant_id==actor.tenant))
    if ev is None:raise HTTPException(404,'Evidence not found')
    if ev.submitted_by==actor.user:raise HTTPException(403,'Two-person verification required')
    if ev.status!='submitted':raise HTTPException(409,'Evidence not awaiting review')
    bump(db,actor,iid,data.expected_version)
    ev.status='verified';ev.verified_by=actor.user
    events(db,actor,'evidence.verified',iid,{'evidence_id':evidence_id,'hash':ev.content_hash});db.commit()
    return {'status':'verified','version':data.expected_version+1}

@app.post('/v1/initiatives/{iid}/release-approval')
def approve(iid:str,data:Approve,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','approver'});find_initiative(db,actor,iid)
    ev,approvals=snapshot(db,actor,iid);progress=states(ev,approvals)
    if progress['release']['status']!='awaiting_approval':raise HTTPException(409,'Release prerequisites incomplete')
    if any(e['submitted_by']==actor.user for e in ev if e['stage'] in ('release','evaluation','security')):raise HTTPException(403,'Approver cannot approve own release/evaluation/security evidence')
    bump(db,actor,iid,data.expected_version)
    scope=fingerprint({'evidence':sorted((x['stage'],x['key'],x['hash']) for x in ev if x['status']=='verified'),'version':data.expected_version+1})
    db.add(Approval(id=secrets.token_hex(12),tenant_id=actor.tenant,initiative_id=iid,stage='release',actor=actor.user,scope_hash=scope))
    events(db,actor,'release.approved',iid,{'scope_hash':scope});db.commit()
    return {'status':'approved','scope_hash':scope,'version':data.expected_version+1}

@app.post('/v1/initiatives/{iid}/benefits',status_code=201)
def record_benefit(iid:str,data:NewBenefit,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','lead','finance'});find_initiative(db,actor,iid)
    if db.scalar(select(Benefit).where(Benefit.initiative_id==iid,Benefit.period==data.period)):
        raise HTTPException(409,'Period already recorded; use a future adjustment workflow')
    b=Benefit(id=secrets.token_hex(12),tenant_id=actor.tenant,initiative_id=iid,classification='self_reported',**data.model_dump())
    db.add(b);events(db,actor,'benefit.reported',iid,data.model_dump());db.commit()
    return {'id':b.id,'classification':'self_reported','net_reported':data.reported-data.run_cost}

@app.get('/v1/value-tower')
def value_tower(actor:Identity=Depends(identity),db:Session=Depends(session)):
    rows=db.scalars(select(Benefit).where(Benefit.tenant_id==actor.tenant)).all()
    return {'currency':'USD (input convention)','classification':'self_reported','planned':sum(x.planned for x in rows),'reported':sum(x.reported for x in rows),'run_cost':sum(x.run_cost for x in rows),'net_reported':sum(x.reported-x.run_cost for x in rows),'periods':len(rows)}

@app.get('/v1/executive/board-scorecard')
def board_scorecard(actor:Identity=Depends(identity),db:Session=Depends(session)):
    """Finance taxonomy: no synthetic or self-reported entry counts as reconciled."""
    inits=db.scalars(select(Initiative).where(Initiative.tenant_id==actor.tenant)).all()
    rows=db.scalars(select(Benefit).where(Benefit.tenant_id==actor.tenant)).all()
    buckets={}
    for b in rows:
        name=next((i.name for i in inits if i.id==b.initiative_id),'Unknown initiative')
        item=buckets.setdefault(b.initiative_id,{'initiative_id':b.initiative_id,'name':name,'planned':0.,'reported':0.,'run_cost':0.,'periods':0,'source_class':'self_reported'})
        item['planned']+=b.planned;item['reported']+=b.reported;item['run_cost']+=b.run_cost;item['periods']+=1
    per=list(buckets.values())
    for r in per:r['net_reported']=r['reported']-r['run_cost']
    demo=[x for x in inits if x.name.startswith('[DEMO')]
    return {'total_initiatives':len(inits),'demo_initiatives':len(demo),'real_initiatives':len(inits)-len(demo),
            'planned':sum(x.planned for x in rows),'self_reported':sum(x.reported for x in rows),
            'actual_run_cost_self_reported':sum(x.run_cost for x in rows),
            'net_self_reported':sum(x.reported-x.run_cost for x in rows),
            'finance_reconciled':None,'finance_reconciled_status':'NOT_IMPLEMENTED',
            'periods':len(rows),'source_class':'self_reported','initiatives':per,
            'caution':'Demo entries are fictional. Self-reported results are not independently reconciled, and no finance-certified metric is available.'}

@app.get('/v1/audit')
def audit(actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','reviewer','approver'})
    return [{'id':a.id,'event':a.event,'actor':a.actor,'entity_id':a.entity_id,'previous_hash':a.prev_hash,'hash':a.event_hash} for a in db.scalars(select(Audit).where(Audit.tenant_id==actor.tenant).order_by(Audit.id.desc()).limit(100))]

@app.post('/v1/optimize')
def solve(data:OptimizeRequest,actor:Identity=Depends(identity)):
    require(actor,{'admin','lead','editor','reviewer','approver','finance'})
    try:return optimize(data.spec)
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e))


# Authenticated domain computation — modelled analytics never certify operational evidence.
class AnalyticsRequest(BaseModel):
    payload:dict=Field(default_factory=dict)

@app.post('/v1/analytics/{tool}')
def run_analytics(tool:str,data:AnalyticsRequest,actor:Identity=Depends(identity)):
    require(actor,{'admin','lead','editor','reviewer','approver','finance'})
    from . import legacy_engines as L
    p=data.payload
    try:
        if tool=='portfolio':
            spec,issues=L.make_spec(p['items'],p['budget'],p.get('max_items',len(p['items'])),p.get('min_items',0),p.get('min_cats'),p.get('required'),p.get('excluded'),p.get('forbidden'))
            if issues: raise ValueError('; '.join(issues))
            res=L.solve_portfolio(spec)
            if p.get('include_shadow',False) and res.get('status')=='OPTIMAL':res['shadow']=L.shadow_price_analysis(spec,res)
            return res
        if tool=='risk':
            spec,issues=L.make_spec(p['items'],p['budget'],p.get('max_items',len(p['items'])),p.get('min_items',0))
            if issues:raise ValueError('; '.join(issues))
            if len(spec['items'])>L.MAX_EXACT:raise ValueError('Sampled CVaR enumeration supports at most 18 candidates; use portfolio MILP for larger cases')
            return L.solve_cvar(spec,alpha=p.get('alpha',0.1),weight=p.get('weight',0.6),n=p.get('scenarios',200),seed=p.get('seed',42),correlation=p.get('correlation',0.1))
        if tool=='pareto':
            spec,issues=L.make_spec(p['items'],p['budget'],p.get('max_items',len(p['items'])))
            if issues:raise ValueError('; '.join(issues))
            if len(spec['items'])>14:raise ValueError('Exact Pareto enumeration limited to 14 items for interactive API latency')
            return {'points':L.pareto(spec)}
        if tool=='fulfillment':
            f=L.fulfillment_plan_split_sku if p.get('split',True) else L.fulfillment_plan
            return f(p['cart'],p.get('promise_days',5),p.get('zone',1))
        if tool=='pricing':return L.pricing_economics(p['mau_m'],p['conversion_pct'],p['monthly_price_inr'],p.get('fx_usd_per_inr',0.012),p['evc_inr'],p.get('variable_cost_pct',0.14))
        if tool=='ltv':return L.unit_economics_ltv(p['monthly_price_inr'],p.get('fx_usd_per_inr',0.012),p.get('variable_cost_pct',0.14),p.get('monthly_churn_pct',3.5),p.get('cac_usd',4.5))
        if tool=='forecast':
            out=L.forecast_band(p['history'],p.get('horizon',30),p.get('promo',False),p.get('quantile',0.95))
            return {k:v.tolist() if hasattr(v,'tolist') else v for k,v in out.items()}
        if tool=='quality':return L.score_nlp_eval_cases(p['cases'],p.get('use_degraded',False))
        if tool=='ast':return L.inspect_python_ast(p['source'])
        if tool=='pipeline':return L.generate_verified_pipeline_starter()
        if tool=='shapley':
            spec,issues=L.make_spec(p['items'],p['budget'],p.get('max_items',len(p['items'])))
            if issues:raise ValueError('; '.join(issues))
            return {'attribution':L.shapley_attribution(spec,p['selected'])}
        if tool=='counterfactual':
            spec,issues=L.make_spec(p['items'],p['budget'],p.get('max_items',len(p['items'])))
            if issues:raise ValueError('; '.join(issues))
            return {'counterfactuals':L.counterfactual(spec,{'selected':p['selected'],'metrics':L.metrics(spec,p['selected'])})}
        raise HTTPException(404,'Unregistered analytics tool')
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,ZeroDivisionError) as exc:
        raise HTTPException(422,str(exc))

class WorkspaceWrite(BaseModel):
    payload:dict
    expected_version:int=Field(ge=0)

@app.get('/v1/workspaces/{workspace_id}')
def workspace_get(workspace_id:str,actor:Identity=Depends(identity),db:Session=Depends(session)):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',workspace_id):raise HTTPException(422,'Invalid workspace identifier')
    row=db.get(WorkspaceDocument,(actor.tenant,workspace_id))
    return {'payload':row.payload if row else {},'version':row.version if row else 0}

@app.put('/v1/workspaces/{workspace_id}')
def workspace_put(workspace_id:str,data:WorkspaceWrite,actor:Identity=Depends(identity),db:Session=Depends(session)):
    require(actor,{'admin','lead','editor','finance'})
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',workspace_id):raise HTTPException(422,'Invalid workspace identifier')
    if len(json.dumps(data.payload))>250000:raise HTTPException(413,'Workspace payload exceeds 250KB')
    row=db.get(WorkspaceDocument,(actor.tenant,workspace_id))
    if row is None:
        if data.expected_version!=0:raise HTTPException(409,'Workspace changed; refresh')
        row=WorkspaceDocument(tenant_id=actor.tenant,workspace_id=workspace_id,payload=data.payload,version=1)
        db.add(row)
    else:
        n=db.execute(update(WorkspaceDocument).where(WorkspaceDocument.tenant_id==actor.tenant,WorkspaceDocument.workspace_id==workspace_id,WorkspaceDocument.version==data.expected_version).values(payload=data.payload,version=WorkspaceDocument.version+1)).rowcount
        if n!=1:raise HTTPException(409,'Workspace changed; refresh')
    events(db,actor,'workspace.saved',workspace_id,{'payload_hash':fingerprint(data.payload)})
    db.commit()
    return {'version':data.expected_version+1}

@app.get('/v1/initiatives/{iid}/critical-path')
def initiative_critical_path(iid:str,days_per_open_stage:int=8,actor:Identity=Depends(identity),db:Session=Depends(session)):
    if not 1<=days_per_open_stage<=90:raise HTTPException(422,'Duration must be 1-90 days')
    find_initiative(db,actor,iid)
    ev,ap=snapshot(db,actor,iid);status=states(ev,ap)
    from .core import STAGES
    early_start={};early_end={};days={}
    for name,deps in STAGES.items():
        days[name]=0 if status[name]['status']=='complete' else days_per_open_stage
        early_start[name]=max((early_end[d] for d in deps),default=0)
        early_end[name]=early_start[name]+days[name]
    finish=max(early_end.values(),default=0)
    children={k:[] for k in STAGES}
    for name,deps in STAGES.items():
        for dep in deps:children[dep].append(name)
    late_start={};late_end={}
    for name in reversed(list(STAGES)):
        late_end[name]=min((late_start[ch] for ch in children[name]),default=finish)
        late_start[name]=late_end[name]-days[name]
    rows=[{'stage':name,'status':status[name]['status'],'duration_days':days[name],
           'early_start':early_start[name],'early_finish':early_end[name],
           'late_start':late_start[name],'late_finish':late_end[name],
           'float_days':late_start[name]-early_start[name],
           'on_critical_path':bool(days[name]>0 and late_start[name]==early_start[name])}
          for name in STAGES]
    return {'initiative_id':iid,'remaining_days_scenario':finish,'critical_stages':[r['stage'] for r in rows if r['on_critical_path']],
            'assumption':'Uniform remaining stage durations; not actual delivery time forecasts','stages':rows}

# R1.1–R3 additive intelligence API. Import models before configure()/create_all().
from .intelligence import build_router
app.include_router(build_router(identity,session,require,events,find_initiative))

# R4 ETES models must be imported before application startup creates schema.
from .execution import build_router as build_etes_router
app.include_router(build_etes_router(identity,session,require,events,find_initiative))

# R5.0: explicit, scoped funding-decision lookup for reactive forms.
# This reuses the R1 decision model; it does not infer decisions from execution tasks.
@app.get('/v1/initiatives/{initiative_id}/funding-decisions',tags=['AI Trust R5'])
def funding_decisions_for_initiative(initiative_id:str,actor:Identity=Depends(identity),db:Session=Depends(session)):
    from .intelligence import DecisionRecord,decision_json
    find_initiative(db,actor,initiative_id)
    matches=db.scalars(select(DecisionRecord).where(
        DecisionRecord.tenant_id==actor.tenant,
        DecisionRecord.initiative_id==initiative_id
    ).order_by(DecisionRecord.created_at.desc())).all()
    return [decision_json(d) for d in matches]

# R5.0/R5.1 — additive AI Trust Office; models registered before app startup.
from .models import AIRiskAssessment, AIControlEvidence, RedTeamFinding
from .trust import build_router as build_trust_router
app.include_router(build_trust_router(identity,session,require,events,find_initiative))

# R5.2–R5.4 additive, tenant-scoped decision governance routes.
from .decision_governance import build_router as build_decision_governance_router
app.include_router(build_decision_governance_router(identity,session,require,events,find_initiative))

# R5.5 additive strategy-to-outcomes models. Registered before configure() startup.
from .strategy_outcomes import build_router as build_strategy_router
app.include_router(build_strategy_router(identity,session,require,events,find_initiative))

# R5.6 additive, reviewer-bound evaluation snapshots.
from .decision_evaluation import build_router as build_evaluation_router
app.include_router(build_evaluation_router(identity,session,require,events,find_initiative))

# R7: independent decision event attestation and deterministic replay.
from .decision_events import build_router as build_decision_events_router
app.include_router(build_decision_events_router(identity,session,require))

# R8 finance outcome events: independent finance attestation only.
from .outcome_economics import build_router as build_outcome_router
app.include_router(build_outcome_router(identity,session,require))

# R9.5 additive trust evidence endpoints
from .trust_foundation import build_router as build_r95_trust_router
app.include_router(build_r95_trust_router(identity,session,require))

# R9.9 authenticated ingestion
from .authenticated_ingestion import build_router as authenticated_source_router
app.include_router(authenticated_source_router(identity, session, require))