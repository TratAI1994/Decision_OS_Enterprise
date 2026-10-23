"""Decision OS Flagship — REST-only Streamlit UI. No local database, no local optimizer.
Run: streamlit run ui/app.py; configure API_BASE_URL and DECISION_OS_UI_TOKEN.
Authenticated demo bearer tokens are bootstrapping credentials, not production SSO.
"""
from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title='Decision OS | Enterprise Intelligence',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
:root{--navy:#101b32;--blue:#2a67d4;--surface:#fff;--line:#e6eaf0}
.stApp{background:linear-gradient(120deg,#f3f6fb,#f9fafc);color:#16253b}
.block-container{max-width:1500px;padding-top:1.8rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#131f34}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span{color:#edf3ff!important}
[data-testid="stSidebar"] [data-baseweb="select"] span{color:#14233d!important}
[data-testid="stMetric"]{background:white;border:1px solid #e1e8f3;border-radius:16px;padding:16px;box-shadow:0 3px 17px #132d5d09}
[data-testid="stExpander"], [data-testid="stForm"]{border-radius:16px}
h1{letter-spacing:-.045em;font-weight:800}h2,h3{letter-spacing:-.025em}
.hero{padding:25px 30px;border-radius:19px;background:linear-gradient(112deg,#0b1933,#173e6a 65%,#14646d);color:white;margin-bottom:22px}
.hero .eyebrow{font-size:11px;letter-spacing:.16em;color:#bce5fb;font-weight:750}.hero h1{font-size:30px;margin:6px 0;color:white}.hero p{color:#d3e4f4;font-size:14px;margin:0}
.hint{background:#eef5fc;border:1px solid #dce7f7;padding:10px 14px;border-radius:10px;margin:10px 0}
</style>''',unsafe_allow_html=True)
BASE=os.getenv('API_BASE_URL','http://localhost:8000').rstrip('/')
TOKEN=os.getenv('DECISION_OS_UI_TOKEN','')
# Test-only credential input: entering a real issued token is not role impersonation.
# Disabled unless operator explicitly opts in on a local, non-production deployment.
LOCAL_IDENTITY_TEST=os.getenv('DECISION_OS_LOCAL_IDENTITY_TEST','false').lower()=='true'
def active_token():
    return st.session_state.get('issued_identity_token') or TOKEN


@st.cache_data(ttl=8,show_spinner=False)
def _get(base,token,path):
    resp=requests.get(base+path,headers={'Authorization':'Bearer '+token},timeout=25)
    resp.raise_for_status()
    return resp.json()

def api(method,path,payload=None,quiet=False):
    try:
        if method=='GET':return _get(BASE,active_token(),path)
        resp=requests.request(method,BASE+path,json=payload,headers={'Authorization':'Bearer '+active_token()},timeout=75)
        if not resp.ok:
            detail=resp.text[:500]
            if not quiet:st.error(f'API {resp.status_code} — {detail}')
            return None
        _get.clear()
        return resp.json()
    except requests.RequestException as exc:
        if not quiet:st.error(f'API unavailable: {exc}')
        return None

def calc(tool,p):return api('POST','/v1/analytics/'+tool,{'payload':p})
def hero(kicker,title,description):st.markdown(f'<div class="hero"><div class="eyebrow">{escape(kicker.upper())}</div><h1>{escape(title)}</h1><p>{escape(description)}</p></div>',unsafe_allow_html=True)
def graph(fig,height=390):
    fig.update_layout(height=height,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font={'color':'#213451','size':12},margin={'l':30,'r':30,'t':50,'b':45},legend={'orientation':'h','y':-0.2})
    st.plotly_chart(fig,width='stretch')
def money(x):return f'${float(x or 0):,.0f}'
def table(rows):
    if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
    else:st.info('No records in this workspace yet.')

def choose_initiative(key):
    ins=api('GET','/v1/initiatives')
    if not ins:
        st.info('Register an initiative in Command Center to use this workspace.')
        return None,None
    picked=st.selectbox('Initiative',ins,format_func=lambda x:x['name']+' · '+x['owner'],key=key)
    return picked,api('GET',f"/v1/initiatives/{picked['id']}")

def saveable(workspace,defaults):
    record=api('GET','/v1/workspaces/'+workspace) or {'payload':{},'version':0}
    data=defaults | (record.get('payload') or {})
    return data,record.get('version',0)

def save_inputs(key,payload,ver):
    if st.button('Save workspace inputs to PostgreSQL',key='save_'+key):
        if api('PUT','/v1/workspaces/'+key,{'payload':payload,'expected_version':ver}):st.success('Workspace inputs saved for this tenant');st.rerun()

def defaults():return [
 {'id':'modelops','name':'ModelOps AI','impact':9.,'cost':5.,'secondary':7.,'risk':1.5,'category':'MLOps','requires':''},
 {'id':'gpuflow','name':'GPUFlow','impact':8.,'cost':4.,'secondary':9.,'risk':1.,'category':'Platform','requires':''},
 {'id':'securerag','name':'SecureRAG','impact':7.,'cost':3.,'secondary':8.5,'risk':.8,'category':'Security','requires':''},
 {'id':'agentworks','name':'AgentWorks','impact':6.,'cost':2.,'secondary':6.,'risk':2.,'category':'Agents','requires':''},
 {'id':'vision','name':'VisionStack','impact':5.,'cost':2.,'secondary':4.,'risk':.5,'category':'Vision','requires':''}]

def solver_form(prefix='portfolio',run_controls=True):
    saved,ver=saveable('solver_'+prefix,{'items':defaults(),'budget':8.0,'max_items':5,'min_items':0})
    st.caption('All calculations execute in FastAPI. Edited candidates are not persisted until you click Save.')
    edited=st.data_editor(pd.DataFrame(saved['items']),num_rows='dynamic',hide_index=True,width='stretch',key='grid_'+prefix)
    c1,c2,c3=st.columns(3)
    budget=c1.number_input('Budget',min_value=0.,value=float(saved.get('budget',8.)),key='budget_'+prefix)
    nitems=len(edited)
    max_i=c2.number_input('Maximum projects',min_value=0,max_value=max(1,nitems),value=min(int(saved.get('max_items',nitems)),max(1,nitems)),key='max_'+prefix)
    min_i=c3.number_input('Minimum projects',min_value=0,max_value=max(1,nitems),value=min(int(saved.get('min_items',0)),max_i),key='min_'+prefix)
    items=edited.where(pd.notnull(edited),None).to_dict('records')
    p={'items':items,'budget':budget,'max_items':int(max_i),'min_items':int(min_i)}
    if run_controls:save_inputs('solver_'+prefix,p,ver)
    return p

def gate_graph(detail,key='gate'):
    states=detail['stages'];nodes=list(states)
    lane={'discover':0,'value':0,'data':1,'architecture':-1,'build':0,'evaluation':1,'security':-1,'pilot':0,'release':0,'operate':0}
    color={'complete':'#159b72','blocked':'#aeb6c3','ready':'#2477cb','in_progress':'#d48f20','awaiting_approval':'#7758d0'}
    fig=go.Figure()
    for idx,stage in enumerate(nodes):
        for parent in states[stage]['depends_on']:
            j=nodes.index(parent)
            fig.add_trace(go.Scatter(x=[j,idx],y=[lane[parent],lane[stage]],mode='lines',line={'color':'#becce0','width':2},hoverinfo='skip',showlegend=False))
    fig.add_trace(go.Scatter(x=list(range(len(nodes))),y=[lane[n] for n in nodes],mode='markers+text',text=[n.replace('_',' ').title() for n in nodes],textposition='bottom center',marker={'size':36,'color':[color[states[n]['status']] for n in nodes],'line':{'color':'white','width':2}},customdata=nodes,hovertemplate='%{customdata}<extra></extra>',showlegend=False))
    fig.update_layout(xaxis={'visible':False,'range':[-.5,len(nodes)-.3]},yaxis={'visible':False,'range':[-1.8,1.7]})
    event=st.plotly_chart(fig,height=315,width='stretch',on_select='rerun',selection_mode='points',key='dag_'+key)
    selected=None
    try:
        if event.selection.points:selected=event.selection.points[0]['customdata']
    except (AttributeError,KeyError,TypeError):pass
    return nodes,selected

METHODOLOGIES={
 'discover':('Design Thinking · User Research','Define personas, journey, evidence baseline and measurable problem.','Who needs this and what task is failing?'),
 'value':('OKRs · Cost of Delay · WSJF','Value hypothesis, alternatives, economics, outcome KPIs.','Would a simpler process change solve the problem?'),
 'data':('DataOps · Provenance · Privacy','Classify and inspect datasets, quality and permissions.','Are data rights and quality sufficient?'),
 'architecture':('HLD/LLD · ADR · STRIDE','Trust boundaries, APIs, threat models and failure modes.','How can this fail safely?'),
 'build':('SDLC · CI · Supply-chain security','Review source and build artifacts; link integration test results.','Can engineering reproduce this exact artifact?'),
 'evaluation':('Golden sets · Model risk · Red team','Attach independently executed evaluations, failures and acceptance thresholds.','Did the actual candidate satisfy measured thresholds?'),
 'security':('Zero Trust · OWASP LLM · Privacy','Obtain independent threat and privacy reviews.','What happens with malicious inputs or documents?'),
 'pilot':('Shadow/Canary · UX Measurement','Link user research, adoption and controlled outcome evidence.','Do users perform better than the baseline?'),
 'release':('Change advisory · Human sign-off','Review rollback plan, ownership and production readiness.','Who takes accountability for this release?'),
 'operate':('SRE · MLOps · FinOps · Value','Monitor outcomes, costs, incidents and quality drift.','What would make us pause or retire this system?')}

def mission(detail,title='M12 Implementation Map',key='m12'):
    hero('Implementation operating system',title,'Click a stage; inspect methods, evidence, owners, upstream blockers and next authorized actions.')
    nodes,clicked=gate_graph(detail,key)
    count=sum(x['status']=='complete' for x in detail['stages'].values())
    a,b,c=st.columns(3);a.metric('Completed stages',f'{count}/{len(nodes)}');b.metric('Initiative version',detail['version']);c.metric('Open evidence',sum(len(s['missing']) for s in detail['stages'].values()))
    selected=st.selectbox('Select implementation stage',nodes,index=nodes.index(clicked) if clicked in nodes else 0,key='inspect_'+key)
    info=detail['stages'][selected]
    method,how,user=METHODOLOGIES[selected]
    c1,c2=st.columns([1.25,1])
    with c1:
        st.subheader(selected.replace('_',' ').title())
        st.caption('Industry method: '+method)
        st.write(how)
        st.info('**Persona question:** '+user)
        st.write('**Current state:**',info['status'])
        st.write('**Dependencies:**',', '.join(info['depends_on']) or 'None')
        st.write('**Blocking stages:**',', '.join(info['blocked_by']) or 'None')
        st.write('**Missing independently verified artifacts:**',', '.join(info['missing']) or 'None')
    with c2:
        st.subheader('Evidence and authorized actions')
        for ev in [e for e in detail['evidence'] if e['stage']==selected]:
            st.write(f"{ev['key']} — **{ev['status']}**")
            st.caption(f"Source: {ev['reference']} · Submitted by {ev['submitted_by']}" )
            if ev['status']=='submitted':
                if st.button('Review and verify '+ev['key'],key=f"verify_{key}_{ev['id']}"):
                    res=api('POST',f"/v1/initiatives/{detail['id']}/evidence/{ev['id']}/verify",{'expected_version':detail['version']})
                    if res:st.rerun()
        if not info['blocked_by'] and info['missing']:
            with st.form('evidence_'+key+'_'+selected):
                artifact=st.selectbox('Required artifact',info['missing'])
                ref=st.text_input('Actual evidence URL, commit or artifact reference')
                if st.form_submit_button('Submit for independent verification'):
                    res=api('POST',f"/v1/initiatives/{detail['id']}/evidence",{'stage':selected,'key':artifact,'reference':ref,'expected_version':detail['version']})
                    if res:st.rerun()
        if selected=='release' and info['status']=='awaiting_approval':
            if st.button('Authorize release (authorized reviewer only)',type='primary'):
                if api('POST',f"/v1/initiatives/{detail['id']}/release-approval",{'expected_version':detail['version']}):st.rerun()
    st.caption('Evidence is submitted, not automatically verified. Review and release actions require appropriate credentials and separation of duties enforced by FastAPI.')

PAGES=['Outcome Economics','Decision Event Ledger','Decision Ledger','Architecture Mastery','Strategic Twin Studio','Industry Intelligence','Decision Operations','Ecosystem Intelligence','Strategy-to-Outcomes Review','Microsoft Transformation','AWS Operational Readiness','Google Evaluation & Safety','Decision Academy','Decision Quality & Assumption Engine','Executive Suite','Strategy & Outcomes R5.5','Decision Action Center','Decision Replay & Memory','AI Risk & Regulatory Office','AI Red Team Lab','Enterprise Transformation Execution','Program Manager Copilot','Command Center','Executive Board Scorecard','AI Transformation Portfolio','AI Mission Control','M12 Implementation Map','Enterprise Initiative Journey','AI Value Tower','MILP Optimization Cockpit','CVaR Risk Laboratory','Pareto & Scenario Lab','Counterfactual Studio','Decision Copilot','Visual Workflow Orchestrator','Agentic Transformation Workbench','Fulfillment Operations Lab','Pricing & Value Studio','Model Monitoring & Forecasting','AI Quality Evidence Lab','Transformation Schedule & CPM','CI/CD Blueprint Studio','Governance & Audit','Executive Decision Ledger','Enterprise Memory','Transformation Risk Radar','AI Economics Workbench','Copilot Transformation Office','Workforce Transformation Office','Agent Workforce Control Center','Enterprise Decision Twin','Executive Narrative Studio']
# Persona-focused navigation retains all legacy routes without exposing 37 items at once.
EXEC_SECTIONS={
    'Decision Infrastructure':['Outcome Economics','Decision Event Ledger','Decision Ledger'],
    'Industry Transformation':['Industry Intelligence','Strategic Twin Studio','Architecture Mastery'],
    'Overview':['Strategy-to-Outcomes Review','Executive Suite','Decision Academy','Decision Quality & Assumption Engine','Executive Board Scorecard','Executive Narrative Studio'],
    'AI Transformation Playbooks':['Ecosystem Intelligence','Microsoft Transformation','AWS Operational Readiness','Google Evaluation & Safety'],
    'Strategy & Outcomes':['Strategy & Outcomes R5.5','Executive Decision Ledger','AI Transformation Portfolio','AI Value Tower','Copilot Transformation Office'],
    'Decisions & Execution':['Decision Operations','Decision Action Center','Decision Replay & Memory','Enterprise Transformation Execution','Program Manager Copilot','M12 Implementation Map','Enterprise Initiative Journey'],
    'Risk & Trust':['AI Risk & Regulatory Office','AI Red Team Lab','Transformation Risk Radar','Governance & Audit','AI Quality Evidence Lab'],
    'Workforce & Scenarios':['Agent Workforce Control Center','Workforce Transformation Office','Enterprise Decision Twin','MILP Optimization Cockpit','CVaR Risk Laboratory'],
}
EXEC_SECTIONS['Specialist Explorer']=[p for p in PAGES if p not in {q for k,v in EXEC_SECTIONS.items() for q in v}]
PAGE_SECTIONS={p:category for category,pages in EXEC_SECTIONS.items() for p in pages}

def navigate_to(destination):
    st.session_state['exec_destination']=destination
    st.rerun()

with st.sidebar:
    st.markdown('### ◈ DECISION OS')
    st.caption('STRATEGY → OUTCOMES')
    if 'exec_destination' in st.session_state:
        target=st.session_state.pop('exec_destination')
        if target in PAGE_SECTIONS:
            st.session_state['exec_area']=PAGE_SECTIONS[target]
            st.session_state['exec_page']=target
    section_names=list(EXEC_SECTIONS)
    if st.session_state.get('exec_area') not in section_names:
        st.session_state['exec_area']='Overview'
    area=st.selectbox('Navigation',section_names,key='exec_area',help='Choose an executive domain. All existing specialist workspaces remain accessible.')
    choices=EXEC_SECTIONS[area]
    if st.session_state.get('exec_page') not in choices:
        st.session_state['exec_page']=choices[0]
    if area=='Specialist Explorer':
        st.caption('Advanced workspaces preserved for specialists')
        search=st.text_input('Find a specialist workspace',key='exec_find_workspace',placeholder='Search by module name')
        filtered=[x for x in choices if search.casefold() in x.casefold()]
        if filtered:
            if st.session_state['exec_page'] not in filtered:st.session_state['exec_page']=filtered[0]
            page=st.selectbox('Workspace',filtered,key='exec_page')
        else:
            st.warning('No matching workspace.')
            page='Executive Suite'
    else:
        page=st.radio('Workspace',choices,key='exec_page',label_visibility='collapsed')
    st.divider()
    if LOCAL_IDENTITY_TEST:
        with st.expander('Local identity verification',expanded=False):
            st.caption('Development only. Enter a separately issued API credential. This never changes your role without backend authentication.')
            entered=st.text_input('Issued test identity credential',type='password',key='reviewer_credential',help='Paste the local-reviewer bearer token from your own .env identity registry; do not share it in chat.')
            col_a,col_b=st.columns(2)
            if col_a.button('Verify and switch',key='switch_issued_identity'):
                candidate=entered.strip()
                if not candidate:st.warning('Enter the issued credential first.')
                else:
                    try:
                        response=requests.get(BASE+'/v1/me',headers={'Authorization':'Bearer '+candidate},timeout=8)
                        if response.ok:
                            previous=active_token();st.session_state.issued_identity_token=candidate
                            st.session_state.reviewer_credential='';_get.clear()
                            st.toast('Authenticated as '+response.json()['user']);st.rerun()
                        else:st.error('Credential not accepted by FastAPI. No identity change was made.')
                    except requests.RequestException:st.error('Cannot contact API. Identity unchanged.')
            if col_b.button('Return to default',key='reset_issued_identity'):
                st.session_state.pop('issued_identity_token',None);_get.clear();st.rerun()
    who=api('GET','/v1/me',quiet=True)
    if who:st.caption(f"{who['user']} · {who['role']} · tenant {who['tenant']}")
    st.divider();st.caption('Backend: '+BASE)
    if st.button('Refresh records'): _get.clear();st.rerun()
if not who:
    st.error('FastAPI authorization failed. Check API_BASE_URL and DECISION_OS_UI_TOKEN.');st.stop()


# ─── SECTION 2: TYPED DATA ADAPTERS ──────────────────────────────────
# Backend enforces tenant and row authorization. Fetch failures stay explicit.
from dataclasses import dataclass, field
from datetime import UTC


@dataclass(frozen=True)
class BriefingData:
    focus: list[dict]
    objectives: list[dict]
    krs: list[dict]
    decisions: list[dict]
    links: list[dict]
    assumptions: list[dict]
    experiments: list[dict]
    packets: list[dict]
    tasks: list[dict]
    unavailable: tuple[str, ...] = ()

def briefing_fetch(path: str, label: str) -> tuple[list[dict], bool]:
    data=api('GET',path,quiet=True)
    if not isinstance(data,list):return [],False
    return [x for x in data if isinstance(x,dict)],True

def load_briefing() -> BriefingData:
    endpoints={'focus':'/v1/strategy/focus-areas','objectives':'/v1/strategy/objectives',
               'krs':'/v1/strategy/key-results','decisions':'/v1/intelligence/decisions',
               'links':'/v1/strategy/decision-links','assumptions':'/v1/strategy/assumptions',
               'experiments':'/v1/strategy/experiments','packets':'/v1/decisions-governed/packets',
               'tasks':'/v1/execution/tasks'}
    result={}; failures=[]
    for name,path in endpoints.items():
        items,ok=briefing_fetch(path,name);result[name]=items
        if not ok:failures.append(name)
    return BriefingData(**result,unavailable=tuple(failures))

# ─── SECTION 3: PURE SCORING LOGIC ─────────────────────────────────────
def present(x):return x is not None and str(x).strip()!=''
def label(x,default='Not recorded'):return str(x) if present(x) else default

def kr_measure(kr:dict) -> tuple[str,dict]:
    m=kr.get('measurement') or {};return str(m.get('state') or 'UNKNOWN'),m.get('observation') or {}

def score_evidence(controls: list[dict]) -> dict:
    # Only a *known applicability and verification rubric* may generate a percentage.
    if not controls:return {'score':None,'ok':0,'total':0,'missing':[],'weak':[],'message':'Not assessable — applicable evidence-control register unavailable.'}
    applicable=[c for c in controls if c.get('applicable') is True]
    if not applicable:return {'score':None,'ok':0,'total':0,'missing':[],'weak':[],'message':'N/A — no applicable evidence requirements recorded.'}
    ok=[c for c in applicable if c.get('verified') is True and c.get('fresh') is True and c.get('quality_pass') is True]
    weak=[label(c.get('name')) for c in applicable if c.get('evidence_present') and c not in ok]
    missing=[label(c.get('name')) for c in applicable if not c.get('evidence_present')]
    return {'score':round(100*len(ok)/len(applicable),1),'ok':len(ok),'total':len(applicable),'missing':missing,'weak':weak,'message':f'{len(ok)} of {len(applicable)} applicable controls verified.'}

def score_quality(parts:dict,governance_complete:bool|None) -> dict:
    weights={'evidence':25,'reviews':25,'contract':20,'assumptions':15,'freshness':15}
    usable={k:float(v) for k,v in parts.items() if k in weights and isinstance(v,(int,float)) and 0<=v<=1}
    if not usable: return {'score':None,'message':'Not assessable — required verified components unavailable.','warning':'Approval status unverified' if governance_complete is None else ('Governance incomplete' if not governance_complete else '')}
    numerator=sum(weights[k]*v for k,v in usable.items());denom=sum(weights[k] for k in usable)
    return {'score':round(100*numerator/denom,1),'message':'Provisional evidence-and-process rubric; assessed components: '+', '.join(usable),'warning':('GOVERNANCE INCOMPLETE' if governance_complete is False else 'Governance status unverified' if governance_complete is None else '')}

def urgency(item:dict) -> tuple:
    # Missing dates/materiality do not become synthetic monetary impacts.
    blocked=bool(item.get('blocked'));invalid=bool(item.get('invalidated'))
    stale=bool(item.get('stale'));pending=bool(item.get('pending'))
    tier={'critical':4,'high':3,'limited':2,'minimal':1}.get(str(item.get('risk_tier','')).lower(),0)
    return (int(invalid),int(blocked),int(stale),int(pending),tier,label(item.get('title')))

def describe_attribution(obs:dict) -> str:
    value=str(obs.get('attribution') or 'unattributed').lower()
    if value in ('causal','causal_controlled','causal_quasi'):
        return 'Causal claim recorded; experimental identification and independent verification not established by this UI.'
    if value=='correlated':return 'Correlated, not demonstrated causal.'
    return 'Attribution '+value+'; causal effect not established.'

# ─── SECTION 4: PURE BRIEFING GENERATORS ───────────────────────────────
def make_briefing(data:BriefingData,selected_focus:str|None=None) -> dict:
    objectives=[o for o in data.objectives if str(o.get('focus_id'))==str(selected_focus)] if selected_focus else data.objectives
    objective_ids={str(o.get('id')) for o in objectives}
    krs=[k for k in data.krs if str(k.get('objective_id')) in objective_ids]
    kr_ids={str(k.get('id')) for k in krs}
    links=[l for l in data.links if str(l.get('key_result_id')) in kr_ids]
    dids={str(l.get('decision_id')) for l in links}
    decisions=[d for d in data.decisions if str(d.get('id')) in dids]
    assumptions=[a for a in data.assumptions if str(a.get('decision_id')) in dids]
    tasks=[t for t in data.tasks if str(t.get('decision_id')) in dids or any(str(t.get('initiative_id'))==str(d.get('initiative_id')) and present(d.get('initiative_id')) for d in decisions)]
    packets=[p for p in data.packets if str(p.get('decision_id')) in dids]
    attention=[]
    for d in decisions:
        did=str(d.get('id'));dass=[a for a in assumptions if str(a.get('decision_id'))==did]
        dkr=[k for k in krs if any(str(l.get('decision_id'))==did and str(l.get('key_result_id'))==str(k.get('id')) for l in links)]
        attention.append({'title':label(d.get('title')),'id':did,'risk_tier':d.get('risk_tier'),
                          'invalidated':any(str(a.get('validation_status','')).lower() in ('invalidated','refuted') for a in dass),
                          'blocked':any(str(t.get('status','')).lower() in ('blocked','delayed') for t in tasks if str(t.get('decision_id'))==did),
                          'stale':any(kr_measure(k)[0] in ('STALE','NO_DATA','UNKNOWN') for k in dkr),
                          'pending':any(str(p.get('status','')).lower() in ('draft','submitted','pending_review') for p in packets if str(p.get('decision_id'))==did)})
    attention.sort(key=urgency,reverse=True)
    return {'objectives':objectives,'krs':krs,'links':links,'decisions':decisions,'assumptions':assumptions,
            'tasks':tasks,'packets':packets,'attention':attention,
            'missing':[k for k in krs if kr_measure(k)[0] in ('NO_DATA','UNKNOWN')],
            'stale':[k for k in krs if kr_measure(k)[0]=='STALE'],
            'below':[k for k in krs if kr_measure(k)[0]=='IN_PROGRESS'],
            'baseline':None}

def board_memo(data:BriefingData,section:dict,focus_name:str) -> str:
    stamp=datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
    lines=['# Decision OS — Weekly Executive Brief','Generated: '+stamp,'Scope: '+focus_name,
           'Read-only extract from authenticated backend responses. Not an immutable review snapshot.','',
           '## 1. Executive summary',f"{len(section['decisions'])} visible linked decisions; {len(section['krs'])} outcome contracts. Data completeness must be evaluated before conclusions.",
           '## 2. Strategic priorities',focus_name,
           '## 3. Significant changes since last review','No previous review baseline available; changes cannot be established.',
           '## 4. Decisions requiring attention']
    lines.extend('- '+i['title']+' [Decision '+i['id']+']' for i in section['attention'][:20])
    lines+=['## 5. Outcome gaps and stale measurements']
    for k in section['krs']:
        state,obs=kr_measure(k)
        lines.append('- '+label(k.get('title'))+f" [KR {k.get('id')}]: {state}; target={k.get('target')} {label(k.get('unit'),'')}; observed={label(obs.get('value'),'Not measured')}; observed_at={label(obs.get('observed_at'))}; source_ref={label(obs.get('source_ref'))}; attribution={label(obs.get('attribution'),'unknown')}; limitations={label(obs.get('limitations'),'Not documented')}.")
    lines+=['## 6. Invalidated or untested assumptions']
    for a in section['assumptions']:
        lines.append('- '+label(a.get('statement'))+f" [Assumption {a.get('id')}]; validation={label(a.get('validation_status'))}; evidence={label(a.get('evidence_ref'))}")
    lines+=['## 7. Governance warnings','Evidence Coverage and Decision Process Quality not assessable without authenticated control/review rubric.']
    lines+=['## 8. Approved and executed actions','Actual external action execution not verified by the briefing API responses.']
    lines+=['## 9. Unverified / Missing Evidence']
    lines+=['- No immutable prior review snapshot available.','- Evidence-control register / independent verification data unavailable.']
    lines.extend('- KR '+label(k.get('id'))+' lacks an up-to-date measurement.' for k in section['missing']+section['stale'])
    lines+=['## 10. Recommended next decisions','Review missing evidence and overdue outcomes; no strategy or spend changes are authorized by this memo.']
    if data.unavailable:lines+=['## Data availability warnings','Unavailable API groups: '+', '.join(data.unavailable)]
    return '\n\n'.join(lines)+'\n'

# ─── SECTION 5: STREAMLIT RENDERING ────────────────────────────────────
def node(title,description,state='RECORDED'):
    palette={'STALE':('#fff5e8','#996000'),'NO_DATA':('#fff5e8','#996000'),'BLOCKED':('#fff0f1','#b22236'),
             'IN_PROGRESS':('#eef5ff','#285db1'),'TARGET_MET_OBSERVED':('#e8f7f1','#146b50'),
             'UNKNOWN':('#f1f3f7','#536176')}
    bg,fg=palette.get(state,('#f1f3f7','#536176'))
    st.markdown(f'<div style="border:1px solid #dfe5ec;border-left:5px solid {fg};border-radius:13px;padding:13px 16px;background:white;margin:5px 0"><div style="color:#526177;font-size:11px;font-weight:750">{escape(title.upper())} · {escape(state.replace("_"," "))}</div><div style="font-size:15px;font-weight:650;color:#182744">{escape(str(description))}</div></div>',unsafe_allow_html=True)

def render_executive_briefing():
    hero('Executive intelligence · Evidence before reassurance','Strategy → Outcomes | Weekly Briefing',
         'What changed? What requires a decision? Why is there a gap? What can leadership responsibly conclude?')
    st.caption('READ ONLY · Backend-authorized tenant data · Source-labelled observations · No AI-invented findings')
    data=load_briefing()
    if data.unavailable:st.error('INCOMPLETE DATA — unavailable API groups: '+', '.join(data.unavailable)+'. Counts and rankings below may be incomplete.')
    if data.focus:
        chosen=st.selectbox('Strategic focus area',data.focus,format_func=lambda f:label(f.get('title')),key='briefing_focus')
        focus_id=str(chosen.get('id'));focus_name=label(chosen.get('title'))
    else:
        focus_id=None;focus_name='No focus area available'
        st.info('No strategic focus areas returned. Create one in Strategy & Outcomes R5.5, or inspect API permissions.')
    sec=make_briefing(data,focus_id)
    st.markdown('### 01 · What changed since last review?')
    st.info('No previous review baseline available. The existing R5.5 APIs do not store immutable weekly briefing checkpoints. No change percentages are inferred.')
    st.markdown('### 02 · Decisions requiring attention')
    if sec['attention']:
        top=sec['attention'][0]
        with st.container(border=True):
            st.markdown('#### ACTION REVIEW · '+top['title'])
            flags=[name for name,k in [('Invalidated assumption','invalidated'),('Execution blocker','blocked'),('Missing/stale outcomes','stale'),('Pending packet','pending')] if top[k]]
            st.write('Why prioritized: '+(', '.join(flags) if flags else 'Linked decision under review'))
            st.caption('Priority ordering: invalidated assumptions → blockers → measurement gaps → pending reviews → risk tier. No invented deadline or value at risk.')
            st.code(top['id'],language=None)
        with st.expander('Additional decision queue',expanded=False):
            for row in sec['attention'][1:]:st.write('• '+row['title']+' · '+row['id'])
    else:st.info('No linked decisions found for this focus area. This is not an all-clear.')
    if st.button('Open controlled Action Center',key='brief_action'):navigate_to('Decision Action Center')
    st.markdown('### 03 · Outcome gaps and evidence quality')
    a,b,c,d=st.columns(4)
    a.metric('Outcome contracts',len(sec['krs']))
    b.metric('Stale observations',len(sec['stale']))
    c.metric('Not measured',len(sec['missing']))
    d.metric('Below target',len(sec['below']))
    coverage=score_evidence([]);quality=score_quality({},None)
    a,b=st.columns(2)
    with a:
        with st.container(border=True):
            st.markdown('**Evidence Coverage**');st.markdown('### Not assessable')
            st.caption(coverage['message']+' Evidence counts alone are not control compliance.')
    with b, st.container(border=True):
        st.markdown('**Decision Process Quality**');st.markdown('### Not assessable')
        st.caption(quality['message']+' This is not a measure of investment success.')
    if not sec['krs']:st.warning('No Key Result contracts linked to this focus area.')
    for k in sec['krs']:
        state,obs=kr_measure(k)
        with st.container(border=True):
            st.markdown('**'+label(k.get('title'))+'**')
            st.caption('Target: '+label(k.get('target'))+' '+label(k.get('unit'),'')+' · Observed: '+label(obs.get('value'),'NOT MEASURED')+' · State: '+state)
            if state in ('STALE','NO_DATA','UNKNOWN'):st.warning('Measurement is stale, missing or unknown — no on-track assertion.')
            st.caption('Recorded: '+label(obs.get('observed_at'))+' · Source: '+label(obs.get('source_ref'))+' · '+describe_attribution(obs))
    st.markdown('### 04 · Critical assumptions and reasons')
    invalid=[a for a in sec['assumptions'] if str(a.get('validation_status','')).lower() in ('invalidated','refuted')]
    untested=[a for a in sec['assumptions'] if str(a.get('validation_status','')).lower() in ('unknown','under_test','untested')]
    sup=[a for a in sec['assumptions'] if str(a.get('validation_status','')).lower() in ('valid','supported','confirmed')]
    aa,bb,cc=st.columns(3);aa.metric('Invalidated',len(invalid));bb.metric('Unknown / under test',len(untested));cc.metric('Supported',len(sup))
    for a in invalid+untested:
        st.warning(label(a.get('statement'))+' · '+label(a.get('validation_status'))+' · Decision '+label(a.get('decision_id'))+' · Evidence '+label(a.get('evidence_ref')))
    with st.expander('WHY? · Facts versus hypotheses versus causality',expanded=True):
        st.markdown('**OBSERVED FACTS**')
        for k in sec['krs'][:12]:
            state,obs=kr_measure(k)
            st.write('• '+label(k.get('title'))+': '+label(obs.get('value'),'Not measured')+' · '+state+' · source '+label(obs.get('source_ref'))+' · '+describe_attribution(obs))
            if present(obs.get('limitations')):st.caption('Limitations: '+str(obs['limitations']))
        if not sec['krs']:st.caption('No observable facts available.')
        st.markdown('**DOCUMENTED HYPOTHESES — NOT ESTABLISHED CAUSES**')
        for a in sec['assumptions'][:12]:st.write('• '+label(a.get('statement'))+' · Status: '+label(a.get('validation_status')))
        if not sec['assumptions']:st.caption('No linked, reviewable assumptions recorded.')
        st.markdown('**ESTABLISHED CAUSALITY**')
        st.info('No independently verified causal effect established from the available R5.5 briefing contracts.')
    st.markdown('### 05 · Strategy-to-outcome lineage')
    if focus_id:
        node('Strategic priority',focus_name)
        for obj in sec['objectives']:
            st.markdown('<div style="text-align:center;color:#64748b">↓</div>',unsafe_allow_html=True)
            node('Objective',label(obj.get('title')))
            for k in [x for x in sec['krs'] if str(x.get('objective_id'))==str(obj.get('id'))]:
                state,obs=kr_measure(k)
                st.markdown('<div style="text-align:center;color:#64748b">↓</div>',unsafe_allow_html=True)
                node('Key Result',label(k.get('title'))+' · target '+label(k.get('target')),state)
                kd=[l for l in sec['links'] if str(l.get('key_result_id'))==str(k.get('id'))]
                for link in kd:
                    d=next((d for d in sec['decisions'] if str(d.get('id'))==str(link.get('decision_id'))),None)
                    st.markdown('<div style="text-align:center;color:#64748b">↓</div>',unsafe_allow_html=True)
                    node('Decision',label((d or {}).get('title'),'Linked decision unavailable'),label((d or {}).get('state'),'UNKNOWN'))
                    related=[t for t in sec['tasks'] if str(t.get('decision_id'))==str(link.get('decision_id'))]
                    st.markdown('<div style="text-align:center;color:#64748b">↓</div>',unsafe_allow_html=True)
                    node('Execution',', '.join(label(t.get('title')) for t in related[:3]) if related else 'No linked task evidence', 'BLOCKED' if any(str(t.get('status','')).lower()=='blocked' for t in related) else 'UNKNOWN')
                st.markdown('<div style="text-align:center;color:#64748b">↓</div>',unsafe_allow_html=True)
                node('Observation',label(obs.get('value'),'Not measured')+' · '+label(obs.get('source_ref')),state)
    st.markdown('### 06 · Governance, replay and leadership next steps')
    pending=[p for p in sec['packets'] if str(p.get('status','')).lower() in ('draft','submitted','pending_review')]
    st.caption(str(len(pending))+' pending linked Action Packets · '+str(sum(str(t.get('status','')).lower() in ('blocked','delayed') for t in sec['tasks']))+' blocked/delayed tasks. No approvals can be executed here.')
    c1,c2,c3=st.columns(3)
    with c1:
        if st.button('Review approvals',key='brief_approvals',use_container_width=True):navigate_to('Decision Action Center')
    with c2:
        if st.button('Open Decision Replay',key='brief_replay',use_container_width=True):navigate_to('Decision Replay & Memory')
    with c3:
        if st.button('Inspect source OKRs',key='brief_okrs',use_container_width=True):navigate_to('Strategy & Outcomes R5.5')
    memo=board_memo(data,sec,focus_name)
    st.download_button('Generate Weekly Board Memo · Markdown',memo,file_name='decision_os_board_brief_'+datetime.now(UTC).strftime('%Y%m%d')+'.md',mime='text/markdown',key='brief_export')
    st.caption('Downloaded memo is a current read-only export, not an immutable, independently attested Board Snapshot.')

# ─── SECTION 6: MAIN APPLICATION ROUTING ──────────────────────────────
if page=='Strategy-to-Outcomes Review':
    render_executive_briefing()

if page=='Executive Suite':
    hero('Executive decision intelligence · Unified experience','Enterprise Strategy-to-Outcomes','Where should we invest? What requires a decision? What is blocked? Which outcomes are actually observed?')
    # Aggregate independently sourced endpoints, preserving their evidence classifications.
    board=api('GET','/v1/executive/board-scorecard',quiet=True) or {}
    focus=api('GET','/v1/strategy/focus-areas',quiet=True) or []
    objectives=api('GET','/v1/strategy/objectives',quiet=True) or []
    krs=api('GET','/v1/strategy/key-results',quiet=True) or []
    decisions=api('GET','/v1/intelligence/decisions',quiet=True) or []
    tasks=api('GET','/v1/execution/tasks',quiet=True) or []
    packets=api('GET','/v1/decisions-governed/packets',quiet=True) or []
    experiments=api('GET','/v1/strategy/experiments',quiet=True) or []
    if not isinstance(tasks,list): tasks=[]
    if not isinstance(packets,list): packets=[]
    if not isinstance(krs,list): krs=[]
    if not isinstance(decisions,list): decisions=[]
    if not isinstance(experiments,list): experiments=[]
    st.caption('LIVE TENANT-SCOPED DATA · Illustrative seeded records are not audited company results')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Strategic priorities',len(focus))
    c2.metric('Executive decisions',len(decisions))
    c3.metric('Awaiting packet review',sum(1 for p in packets if p.get('status')=='draft'))
    c4.metric('Blocked or delayed',sum(1 for t in tasks if str(t.get('status','')).lower() in ('blocked','delayed')))
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Outcome contracts',len(krs))
    c2.metric('Outdated observations',sum(1 for k in krs if k.get('measurement',{}).get('state')=='STALE'))
    c3.metric('Missing observations',sum(1 for k in krs if k.get('measurement',{}).get('state')=='NO_DATA'))
    c4.metric('Experiment outcomes',sum(1 for e in experiments if e.get('result') not in ('pending',None)))
    st.caption('Planned, self-reported and verified finance values are deliberately separate. A completed task does not satisfy a Key Result.')
    left,right=st.columns([1.4,1])
    with left:
        st.subheader('Strategy and observed reality')
        if krs:
            krows=[]
            for kr in krs:
                m=kr.get('measurement') or {};obs=m.get('observation') or {}
                krows.append({'Outcome':kr.get('title'),'Target':kr.get('target'),'Observed':obs.get('value','Not measured'),
                              'State':m.get('state','UNKNOWN'),'Attribution':obs.get('attribution','Unassessed')})
            table(krows)
        elif objectives:
            st.info('Objectives exist, but measurable Key Results have not been declared yet.')
        else:
            st.info('Start with a strategic Focus Area, Objective and measurable Key Result.')
        if st.button('Open Strategy & Outcomes',key='suite_strategy',type='primary'):
            navigate_to('Strategy & Outcomes R5.5')
        st.subheader('Evidence-backed value')
        a,b,c=st.columns(3)
        a.metric('Planned benefit',money(board.get('planned')))
        b.metric('Self-reported gross',money(board.get('self_reported')))
        c.metric('Finance-reconciled',money(board['finance_reconciled']) if board.get('finance_reconciled') is not None else 'Unavailable')
        st.caption(board.get('caution','Finance verification is not confirmed.'))
        if st.button('View financial evidence',key='suite_finance'):
            navigate_to('Executive Board Scorecard')
    with right:
        st.subheader('Decisions requiring attention')
        pending=[p for p in packets if p.get('status')=='draft']
        if pending:
            table([{'Packet':p.get('title','Untitled'),'Status':p.get('status'),'Requested by':p.get('created_by','Unknown')} for p in pending[:8]])
        else:st.success('No pending Action Packets are visible to your current identity.')
        if st.button('Go to Action Center',key='suite_action'):
            navigate_to('Decision Action Center')
        blocked=[t for t in tasks if str(t.get('status','')).lower() in ('blocked','delayed')]
        st.subheader('Execution bottlenecks')
        if blocked:table([{'Task':t.get('title'),'State':t.get('status'),'Linked decision':t.get('decision_id')} for t in blocked[:8]])
        else:st.caption('No blocked or delayed execution tasks recorded in this tenant.')
        if st.button('Inspect execution',key='suite_execute'):
            navigate_to('Enterprise Transformation Execution')
    st.divider()
    st.subheader('Your guided Strategy-to-Outcomes journey')
    steps=[('01 · Align','Define a strategic focus, objective and measurable outcome','Strategy & Outcomes R5.5'),
           ('02 · Discover','Record customer hypotheses, predeclared experiments and evidence','Strategy & Outcomes R5.5'),
           ('03 · Decide','Review alternatives, assumptions and the funding decision','Executive Decision Ledger'),
           ('04 · Deliver','Track authorized technical and business delivery','Enterprise Transformation Execution'),
           ('05 · Govern','Inspect risk assessments and observed red-team findings','AI Risk & Regulatory Office'),
           ('06 · Learn','Compare observed outcomes and replay historical context','Decision Replay & Memory')]
    for start in (0,3):
        cols=st.columns(3)
        for col,(heading,description,destination) in zip(cols,steps[start:start+3]):
            with col:
                with st.container(border=True):
                    st.markdown('**'+heading+'**')
                    st.caption(description)
                    if st.button('Open →',key='suite_step_'+str(start)+heading,use_container_width=True):
                        navigate_to(destination)
    with st.expander('What is this dashboard actually measuring?',expanded=False):
        st.write('All values are pulled from the existing tenant-filtered FastAPI endpoints. Stale observations cannot be presented as on track. Benefits from seed data are fictional/self-reported, and finance reconciliation is not implemented. No AI model invents values.')

if page=='Command Center':
    hero('Enterprise strategy and delivery','AI Transformation Command Center','Make decisions from measured work. Never confuse planned, self-reported and independently verified outcomes.')
    ins=api('GET','/v1/initiatives') or []; val=api('GET','/v1/value-tower') or {}
    a,b,c,d=st.columns(4)
    a.metric('Initiatives',len(ins));b.metric('Planned benefit',money(val.get('planned')));c.metric('Self-reported benefit',money(val.get('reported')));d.metric('Net self-reported',money(val.get('net_reported')))
    st.info('All figures are self-reported pending financial reconciliation. API evidence and reviewer controls enforce separate verification.')
    table(ins)
    with st.expander('Create new AI transformation initiative',expanded=not bool(ins)):
        with st.form('create'):
            name=st.text_input('Initiative name');owner=st.text_input('Business owner');description=st.text_area('Persona problem, business outcome and measurable goal')
            if st.form_submit_button('Register initiative',type='primary'):
                if api('POST','/v1/initiatives',{'name':name,'owner':owner,'description':description}):st.rerun()

elif page=='Executive Board Scorecard':
    hero('CEO & CFO · Value first','Enterprise AI Board Scorecard','What value has been planned, what is only reported, and what is independently reconciled?')
    score=api('GET','/v1/executive/board-scorecard') or {}
    col=st.columns(4)
    col[0].metric('Active initiative records',score.get('total_initiatives',0))
    col[1].metric('Planned value',money(score.get('planned',0)))
    col[2].metric('Self-reported gross',money(score.get('self_reported',0)))
    col[3].metric('Net self-reported',money(score.get('net_self_reported',0)))
    st.warning('Finance-reconciled value: NOT AVAILABLE. Synthetic demo entries and business self-reports must never be presented as audited outcomes.')
    if score.get('demo_initiatives',0):st.info(f"{score['demo_initiatives']} records are explicitly tagged as fictional demo data.")
    records=score.get('initiatives',[])
    if records:
        df=pd.DataFrame(records)
        chart=go.Figure()
        chart.add_trace(go.Bar(y=df['name'],x=df['planned'],orientation='h',name='Planned',marker_color='#688dba'))
        chart.add_trace(go.Bar(y=df['name'],x=df['reported'],orientation='h',name='Self-reported',marker_color='#16a085'))
        chart.update_layout(barmode='group',title='Plan vs. self-report by initiative')
        graph(chart,370);table(records)
    st.caption('Next release: finance reconciliation workflow, measured operational outcomes, corrections ledger, and provenance of source system readings.')

elif page in ('AI Mission Control','M12 Implementation Map','Enterprise Initiative Journey','Visual Workflow Orchestrator'):
    i,d=choose_initiative('init_'+page)
    if d: mission(d,title=page,key=re.sub(r'\W','',page))

elif page=='AI Transformation Portfolio':
    hero('Portfolio command','AI Transformation Portfolio','Business initiatives from PostgreSQL; link the investment decision to execution and evidence.')
    ins=api('GET','/v1/initiatives') or [];table(ins)
    if ins:
        i,d=choose_initiative('portfolio_init')
        if d:
            st.write('**Description:**',d['description']);done=sum(x['status']=='complete' for x in d['stages'].values());st.progress(done/max(1,len(d['stages'])),text=f'{done}/{len(d["stages"])} verified stages')
            with st.expander('Update initiative'):
                with st.form('update_init'):
                    name=st.text_input('Name',d['name']);owner=st.text_input('Owner',d['owner']);description=st.text_area('Outcome narrative',d['description'])
                    if st.form_submit_button('Save with optimistic version check'):
                        if api('PUT',f"/v1/initiatives/{d['id']}",{'name':name,'owner':owner,'description':description,'expected_version':d['version']}):st.rerun()

elif page=='AI Value Tower':
    hero('Finance · Value realization','AI Transformation Value Tower','Reported outcomes are not finance-reconciled; every entry requires an accountable source.')
    v=api('GET','/v1/value-tower') or {};c=st.columns(4)
    for el,label,key in zip(c,['Planned','Self-reported','Run cost','Net reported'],['planned','reported','run_cost','net_reported']):el.metric(label,money(v.get(key)))
    fig=go.Figure(go.Waterfall(x=['Planned','Reporting variance','Run cost','Net reported'],measure=['relative','relative','relative','total'],y=[v.get('planned',0),v.get('reported',0)-v.get('planned',0),-v.get('run_cost',0),v.get('net_reported',0)]))
    graph(fig,350)
    i,d=choose_initiative('value_init')
    if d:
        with st.form('benefits'):
            p=st.text_input('Accounting period YYYY-MM',datetime.now().strftime('%Y-%m'))
            a,b,c=st.columns(3)
            planned=a.number_input('Planned USD',min_value=0.0);reported=b.number_input('Reported USD',min_value=0.0);run=c.number_input('Actual run cost USD',min_value=0.0)
            reference=st.text_input('Source record / measurement reference')
            if st.form_submit_button('Record self-reported benefit'):
                if api('POST',f"/v1/initiatives/{d['id']}/benefits",{'period':p,'planned':planned,'reported':reported,'run_cost':run,'evidence_reference':reference}):st.rerun()

elif page in ('MILP Optimization Cockpit','Pareto & Scenario Lab','Counterfactual Studio','Decision Copilot'):
    hero('Decision intelligence',page,'All optimization and scenario calculations execute through authenticated FastAPI analytics routes.')
    p=solver_form(re.sub(r'\W','',page).lower())
    if st.button('Solve three-pass MILP',type='primary',key='solve_'+page):
        result=calc('portfolio',dict(p,include_shadow=True))
        if result:st.session_state['last_'+page]=result
    result=st.session_state.get('last_'+page)
    if result:
        if result.get('status')=='OPTIMAL':
            c=st.columns(3);c[0].metric('Primary impact',result['metrics']['impact']);c[1].metric('Spend',result['metrics']['cost']);c[2].metric('Secondary value',result['metrics']['secondary'])
        st.json(result)
        if result.get('status')=='OPTIMAL':
            if page=='Pareto & Scenario Lab' and st.button('Compute exact Pareto frontier'):
                r=calc('pareto',p)
                if r:
                    df=pd.DataFrame(r['points']);
                    if not df.empty:graph(px.scatter(df,x='secondary',y='impact',size='cost',hover_data=['selected']))
                    table(r['points'])
            elif page=='Counterfactual Studio' and st.button('Challenge every selection'):
                r=calc('counterfactual',dict(p,selected=result['selected']))
                if r:table(r['counterfactuals'])
            elif page=='Decision Copilot':
                st.info(f"API-verified modeled portfolio: {', '.join(result['selected'])}. Impact {result['metrics']['impact']}; spend {result['metrics']['cost']}/{p['budget']}. This is deterministic explanation, not an LLM-generated claim.")
                if st.button('Calculate contribution attribution'):
                    r=calc('shapley',dict(p,selected=result['selected']))
                    if r:table(r['attribution'])

elif page=='CVaR Risk Laboratory':
    hero('Tail-risk intelligence','Correlated CVaR Risk Laboratory','Sampled downside-aware portfolio selection, limited to 18 projects for interactive enumeration.')
    p=solver_form('risk');a,b,c,d=st.columns(4)
    p['alpha']=a.slider('Worst-tail fraction',0.05,0.40,0.10,0.05);p['weight']=b.slider('Downside weight',0.,1.,0.6,0.05)
    p['correlation']=c.slider('Cross-project correlation',0.,0.9,0.15,0.05);p['scenarios']=d.slider('Scenarios',50,600,200,50)
    if st.button('Run sampled CVaR optimization',type='primary'):
        r=calc('risk',p)
        if r:st.json(r)

elif page=='Fulfillment Operations Lab':
    hero('Operations research','Multi-Node Fulfillment Studio','Inventory-constrained, SLA-aware split-SKU optimization; modeled dispatch and cost assumptions.')
    saved,ver=saveable('fulfillment',{'cart':{'TV':1,'Diapers':2,'Socks':4,'Coffee Maker':1},'promise_days':5,'zone':1,'split':True})
    cols=st.columns(4);cart={}
    for idx,sku in enumerate(['TV','Diapers','Socks','Coffee Maker','Headphones']):
        with cols[idx%4]:cart[sku]=st.number_input(sku,0,20,int(saved['cart'].get(sku,0)),key='qty_'+sku)
    p={'cart':cart,'promise_days':st.selectbox('SLA days',[2,3,4,5],index=[2,3,4,5].index(int(saved['promise_days']))),'zone':st.selectbox('Zone',[1,2,3],index=int(saved['zone'])-1),'split':st.checkbox('Allow split-SKU allocations',value=bool(saved['split']))}
    save_inputs('fulfillment',p,ver)
    if st.button('Optimize fulfillment',type='primary'):
        r=calc('fulfillment',p)
        if r:
            if r['status']=='OPTIMAL':
                a,b,c=st.columns(3);a.metric('Total cost',money(r['cost']));b.metric('Shipments',r['shipments']);c.metric('Max ETA',str(r['eta_days'])+' days')
                if 'allocations' in r:table(r['allocations'])
                else:st.json(r.get('selected'))
            else:st.warning(r.get('reason',r['status']))

elif page=='Pricing & Value Studio':
    hero('Commercial intelligence','Pricing & Value Studio','Subscription economics, unit contribution, CAC payback and consumer value assumptions.')
    saved,ver=saveable('pricing',{'mau_m':2700.,'conversion_pct':.25,'monthly_price_inr':79.,'evc_inr':45.,'variable_cost_pct':.14,'monthly_churn_pct':3.5,'cac_usd':4.5,'fx_usd_per_inr':.012})
    a,b,c,d=st.columns(4)
    p={'mau_m':a.number_input('MAU millions',min_value=0.,value=float(saved['mau_m'])),'conversion_pct':b.number_input('Conversion %',min_value=0.,max_value=100.,value=float(saved['conversion_pct'])),'monthly_price_inr':c.number_input('Price ₹/month',min_value=0.,value=float(saved['monthly_price_inr'])),'evc_inr':d.number_input('EVC ₹/month',min_value=0.01,value=float(saved['evc_inr']))}
    e,f,g=st.columns(3);p['monthly_churn_pct']=e.number_input('Churn %',min_value=0.,value=float(saved['monthly_churn_pct']));p['cac_usd']=f.number_input('CAC USD',min_value=0.,value=float(saved['cac_usd']));p['variable_cost_pct']=g.slider('Variable cost %',0.,.9,float(saved['variable_cost_pct']))
    p['fx_usd_per_inr']=float(saved['fx_usd_per_inr']);save_inputs('pricing',p,ver)
    if st.button('Calculate pricing architecture',type='primary'):
        econ=calc('pricing',p);unit=calc('ltv',p)
        if econ and unit:
            a,b,c,d=st.columns(4);a.metric('Annual revenue',money(econ['revenue_usd']));b.metric('Annual contribution',money(econ['contribution_usd']));c.metric('LTV : CAC',f"{unit['ltv_cac_ratio']}×");d.metric('Payback months',unit['payback_months'])
            with st.expander('Calculation details'):st.json({'commercial':econ,'unit_economics':unit})

elif page=='Model Monitoring & Forecasting':
    hero('Operations / ML','Model Monitoring & Demand Forecasting','Empirical seasonal-trend forecast from input observations, not a live sensor feed.')
    saved,ver=saveable('forecast',{'history':[float(7+i*.05+(i%7==0)*3) for i in range(42)],'horizon':28,'quantile':.95,'promo':False})
    text=st.text_area('Observed daily demand — comma-separated',value=', '.join(str(v) for v in saved['history']),height=105)
    p={'horizon':st.slider('Future days',7,90,int(saved['horizon'])),'quantile':st.slider('Residual quantile',.5,.99,float(saved['quantile']),.01),'promo':st.checkbox('Assumed promotional shock',value=bool(saved['promo']))}
    try:p['history']=[float(x.strip()) for x in text.replace('\n',',').split(',') if x.strip()]
    except ValueError:p['history']=[];st.warning('Enter numeric observations.')
    save_inputs('forecast',p,ver)
    if st.button('Forecast',type='primary'):
        r=calc('forecast',p)
        if r:
            fig=go.Figure();x=list(range(len(r['p50'])));fig.add_trace(go.Scatter(x=x,y=r['p50'],name='Forecast'));fig.add_trace(go.Scatter(x=x,y=r['p05'],name='Lower residual band',line={'dash':'dot'}));fig.add_trace(go.Scatter(x=x,y=r['p95'],name='Upper residual band',line={'dash':'dot'}));graph(fig);st.caption(f"In-sample MAE {r['mae']:.2f}; not independently backtested.")

elif page=='AI Quality Evidence Lab':
    hero('Evaluation diagnostics','AI Quality Evidence Lab','Checks supplied text against references using lexical proxies and literal patterns. Not a live model evaluation or compliance attestation.')
    saved,ver=saveable('quality',{'context':'Monthly savings are $126,500, after cloud operating cost of $18,500.','good_output':'Net monthly savings are $126,500 after $18,500 in run costs.','required_entities':['$126,500','$18,500']})
    context=st.text_area('Ground-truth context',saved['context']);output=st.text_area('Actual model output / example',saved['good_output']);req=st.text_input('Required terms (comma separated)',', '.join(saved['required_entities']))
    case={'case_id':'user-input','context':context,'good_output':output,'degraded_output':output,'required_entities':[x.strip() for x in req.split(',') if x.strip()]}
    save_inputs('quality',{'context':context,'good_output':output,'required_entities':case['required_entities']},ver)
    if st.button('Run non-attesting text diagnostics',type='primary'):
        result=calc('quality',{'cases':[case]})
        if result:st.json(result)

elif page=='CI/CD Blueprint Studio':
    hero('Platform engineering','CI/CD Pipeline Blueprint Studio','Preview starter workflow and container instructions; files are not deployed or validated for customer infrastructure.')
    if st.button('Generate starter templates'):
        r=calc('pipeline',{})
        if r:
            for name,content in r.items():
                st.subheader(name.replace('_',' ').title());st.code(content,language='yaml' if 'yaml' in name else 'docker')
                st.download_button('Download '+name,content,file_name='decision-os-'+name.replace('_','-')+('.yml' if 'yaml' in name else '.Dockerfile'))
    with st.expander('Narrow AST check (eval/exec calls only)'):
        source=st.text_area('Python source to inspect')
        if st.button('Inspect') and source:
            r=calc('ast',{'source':source})
            if r:st.json(r)

elif page=='Transformation Schedule & CPM':
    hero('Transformation planning','Critical Path & Stage Dependencies','Forward and backward CPM passes run in FastAPI against the enterprise initiative workflow.')
    i,d=choose_initiative('cpm_i')
    if d:
        duration=st.slider('Modeled duration per incomplete stage (days)',1,30,8)
        r=api('GET',f"/v1/initiatives/{d['id']}/critical-path?days_per_open_stage={duration}")
        if r:
            st.metric('Modeled remaining critical-path duration',f"{r['remaining_days_scenario']} days")
            st.write('**Critical stages:**',', '.join(r['critical_stages']) or 'None')
            table(r['stages']);st.caption(r['assumption'])

elif page=='Agentic Transformation Workbench':
    hero('Human-controlled agents','Enterprise Delivery Advisory Workbench','Read-only recommendations grounded in tenant-scoped API evidence. Actions occur only through existing authorized workflow endpoints.')
    i,d=choose_initiative('agents_i')
    if d:
        stages=d['stages'];pending=[(k,v) for k,v in stages.items() if v['status'] in ('ready','in_progress','awaiting_approval')]
        waiting=[(k,v) for k,v in stages.items() if v['status']=='blocked']
        st.subheader('Specialist council')
        for label,narrative in [
            ('Delivery Planner',f"Ready stages: {', '.join(k for k,_ in pending) or 'None'}. Blocked stages: {len(waiting)}."),
            ('Security Challenger',f"Security status: {stages['security']['status']}; evaluation status: {stages['evaluation']['status']}."),
            ('Value Architect','Link business-case evidence from Value gate with self-reported outcome records; finance reconciliation is not automated.'),
            ('Decision Reviewer',f"Release gate: {stages['release']['status']}. No self-approval or auto-validation."),
            ('FinOps Advisor','Record run costs in Value Tower and compare against planned benefit.')]:
            with st.expander(label):st.write(narrative)
        st.caption('These are deterministic advisors, not autonomous language-model agents. Open M12 or Mission Control to submit verified workflow actions.')

elif page=='Governance & Audit':
    hero('Trust, controls and history','Governance & Audit','Append-only-style event records in PostgreSQL. Production-grade immutable audit storage and SSO remain separate infrastructure work.')
    rows=api('GET','/v1/audit')
    if rows:table(rows)
    else:st.info('Audit viewing requires reviewer/admin/approver role. No changes were made.')


# Release R1.1–R3: API-backed executive intelligence. These workspaces do not use SQLite.
elif page=='Enterprise Transformation Execution':
    hero('Strategy → funded decision → delivery','Enterprise Transformation Execution','Business and technical lifecycles, human/agent ownership and modeled delay exposure; every task traces to a funding decision.')
    initiatives=api('GET','/v1/initiatives') or []
    decisions=api('GET','/v1/intelligence/decisions') or []
    assignees=api('GET','/v1/execution/assignees') or []
    tasks=api('GET','/v1/execution/tasks') or []
    if tasks:
        a,b,c=st.columns(3)
        a.metric('Linked execution items',len(tasks))
        b.metric('Blocked or delayed',sum(t['status'] in ('blocked','delayed') for t in tasks))
        c.metric('Modeled deferred value',money(sum(t['impact']['modeled_deferred_value'] for t in tasks)))
        st.caption('The modeled value may overlap across tasks. Do not treat this as realized financial loss or sum as audited ROI.')
        for label,field,stages in [('Business lifecycle','business_stage',['Idea','Validation','Funded','Delivering','Operational','Value Realized']),('Technical lifecycle','technical_stage',['Data','Build','Evaluate','Secure','Pilot','Release'])]:
            st.markdown('### '+label)
            cols=st.columns(len(stages))
            for col,stage in zip(cols,stages):
                with col:
                    st.markdown('**'+stage+'**')
                    stage_tasks=[x for x in tasks if x[field]==stage]
                    for t in stage_tasks:
                        with st.container(border=True):
                            st.caption(t['status'].upper())
                            st.markdown('**'+t['title']+'**')
                            st.caption(t['assignee_kind']+' · '+t['assignee_ref'])
                            if t['status'] in ('blocked','delayed'):
                                st.error(money(t['impact']['modeled_deferred_value'])+' modeled exposure')
        st.markdown('### Inspect task and update its execution state')
        selected=st.selectbox('Select task',tasks,format_func=lambda t:t['title']+' · '+t['status'],key='r4_task_pick')
        thread=api('GET','/v1/execution/thread/'+selected['id'])
        if thread:
            st.markdown('**Why does this task exist?**')
            st.info('Funding decision: '+thread['funding_decision']['title']+' — '+thread['funding_decision']['rationale'])
            st.caption('Initiative: '+thread['initiative']['name']+' · Decision ID: '+selected['decision_id'])
        with st.form('r4_update',clear_on_submit=False):
            status=st.selectbox('Execution status',['open','in_progress','blocked','delayed','completed'],index=['open','in_progress','blocked','delayed','completed'].index(selected['status']))
            bs=st.selectbox('Business phase',['Idea','Validation','Funded','Delivering','Operational','Value Realized'],index=['Idea','Validation','Funded','Delivering','Operational','Value Realized'].index(selected['business_stage']))
            ts=st.selectbox('Technical phase',['Data','Build','Evaluate','Secure','Pilot','Release'],index=['Data','Build','Evaluate','Secure','Pilot','Release'].index(selected['technical_stage']))
            blocked_since=st.date_input('Blocker first observed',value=__import__('datetime').date.today()) if status in ('blocked','delayed') else None
            if st.form_submit_button('Save execution transition',type='primary'):
                body={'expected_version':selected['version'],'status':status,'business_stage':bs,'technical_stage':ts,'blocked_since':blocked_since.isoformat() if blocked_since else None}
                if api('PATCH','/v1/execution/tasks/'+selected['id'],body):st.toast('Task updated');st.rerun()
    else:
        st.info('No execution tasks yet. First register a strategic funding decision in Executive Decision Ledger.')
    if not decisions:
        st.warning('Create a board/funding decision in Executive Decision Ledger before starting execution.')
    elif not assignees:
        st.warning('No tenant assignees available.')
    else:
        with st.expander('Create value-linked execution task',expanded=not bool(tasks)):
            with st.form('r4_create_task',clear_on_submit=True):
                valid_decisions=[d for d in decisions if any(i['id']==d['initiative_id'] for i in initiatives)]
                if valid_decisions:
                    decision=st.selectbox('Board decision',valid_decisions,format_func=lambda d:d['title']+' · '+d['initiative_id'])
                    initiative=next(i for i in initiatives if i['id']==decision['initiative_id'])
                    st.caption('Linked initiative: '+initiative['name'])
                    title=st.text_input('What deliverable is required?')
                    description=st.text_area('User problem, acceptance criteria, definition of done')
                    assignee=st.selectbox('Human or registered agent',assignees,format_func=lambda a:a['kind'].title()+' · '+a['label'])
                    c1,c2=st.columns(2)
                    bs=c1.selectbox('Business lifecycle',['Idea','Validation','Funded','Delivering','Operational'])
                    ts=c2.selectbox('Technical lifecycle',['Data','Build','Evaluate','Secure','Pilot','Release'])
                    daily=st.number_input('Modeled expected value deferred per calendar day ($)',min_value=0.0,value=0.0,step=100.0)
                    source=st.text_input('Source / economic assumption reference',placeholder='Board business case hypothesis v1')
                    if st.form_submit_button('Create linked task',type='primary'):
                        body={'decision_id':decision['id'],'initiative_id':decision['initiative_id'],'title':title,'description':description,'assignee_kind':assignee['kind'],'assignee_ref':assignee['ref'],'business_stage':bs,'technical_stage':ts,'daily_value_at_risk':daily,'cost_model_source':source}
                        if api('POST','/v1/execution/tasks',body):st.toast('Task created');st.rerun()
    st.markdown('### Decision Copilot · Execution context')
    st.caption('Explain the active stage, blockers, source decision and next authorized step; suggestions are advisory and require human approval.')
    if tasks:
        selected_help=st.selectbox('Explain work item',tasks,format_func=lambda t:t['title'],key='r4_help')
        thread=api('GET','/v1/execution/thread/'+selected_help['id'])
        if thread:
            st.write('**Business reason:** '+thread['funding_decision']['rationale'])
            st.write('**Accountable:** '+selected_help['assignee_ref'])
            st.write('**Current next step:** '+('Investigate blocker; record evidence and propose remediation.' if selected_help['status'] in ('blocked','delayed') else 'Review acceptance evidence and proceed through permitted gates.'))

elif page=='Program Manager Copilot':
    hero('Evidence-grounded delivery intelligence','Program Manager Copilot','Deterministic brief from tenant-scoped execution records. No autonomous tools or invented test results.')
    brief=api('GET','/v1/execution/brief') or {}
    a,b,c=st.columns(3)
    a.metric('Execution items',brief.get('total_tasks',0))
    b.metric('Blocked and delayed',brief.get('blocked_count',0))
    c.metric('Modeled deferred value',money(brief.get('total_modeled_deferred_value',0)))
    st.warning(brief.get('warning','All cost-of-delay figures are scenario estimates.'))
    for finding in brief.get('findings',[]):
        with st.expander(finding['title']+' · '+finding['status']):
            st.write('Technical phase: '+finding['technical_stage'])
            st.write('Estimated delay: '+str(finding['impact']['delay_days'])+' calendar days')
            st.write('Modeled exposure: '+money(finding['impact']['modeled_deferred_value']))
            st.write('Recommended action: '+finding['recommendation'])
            st.caption('Assumption: '+finding['impact']['source'])
    tasks=api('GET','/v1/execution/tasks') or []
    if tasks:
        st.markdown('### Stage a human-reviewed intervention')
        with st.form('r4_proposal',clear_on_submit=True):
            target=st.selectbox('Execution task',tasks,format_func=lambda t:t['title'])
            recommendation=st.text_area('Proposed intervention',placeholder='Reassign security review capacity, subject to security approval')
            basis=st.text_input('Evidence / issue reference')
            if st.form_submit_button('Submit proposal for independent review'):
                if api('POST','/v1/execution/proposals',{'task_id':target['id'],'recommendation':recommendation,'evidence_basis':basis}):st.toast('Proposal queued');st.rerun()
    proposals=api('GET','/v1/execution/proposals') or []
    for p in proposals:
        with st.container(border=True):
            st.markdown('**'+p['recommendation']+'**')
            st.caption('Status: '+p['status']+' · Proposed by '+p['proposed_by']+' · Evidence: '+p['evidence_basis'])
            if p['status']=='proposed':
                l,r=st.columns(2)
                if l.button('Approve for manual action',key='r4_ap'+p['id']):
                    if api('POST','/v1/execution/proposals/'+p['id']+'/review',{'approved':True}):st.rerun()
                if r.button('Reject',key='r4_rej'+p['id']):
                    if api('POST','/v1/execution/proposals/'+p['id']+'/review',{'approved':False}):st.rerun()
    st.info('Optional Ollama/LangGraph reasoning should draft proposals only. This release does not execute unattended tool calls, deploy code, or grant itself approvals.')

elif page=='Executive Decision Ledger':
    hero('Institutional decision intelligence','Executive Decision Ledger','Capture the rationale and alternatives before decisions are made; review what happened afterward.')
    decisions=api('GET','/v1/intelligence/decisions') or []
    table(decisions)
    ins=api('GET','/v1/initiatives') or []
    if ins:
        with st.expander('Register a strategic decision',expanded=True):
            chosen=st.selectbox('Related initiative',ins,format_func=lambda i:i['name']+' · '+i['owner'],key='di_dec_i')
            with st.form('di_create_decision'):
                title=st.text_input('Decision to be made',placeholder='Expand AI knowledge assistant to Finance')
                opt=st.text_input('Preferred option',placeholder='Controlled 90-day pilot')
                alternatives=st.text_input('Alternatives considered (semicolon-separated)')
                rationale=st.text_area('Rationale and trade-offs')
                assumptions=st.text_area('Assumptions (one per line)')
                evidence=st.text_area('Evidence links or references (one per line)')
                review=st.text_input('Outcome review date (YYYY-MM-DD, optional)')
                if st.form_submit_button('Record proposal',type='primary'):
                    payload={'initiative_id':chosen['id'],'title':title,'option_chosen':opt,
                             'alternatives':[a.strip() for a in alternatives.split(';') if a.strip()],
                             'rationale':rationale,'assumptions':[a.strip() for a in assumptions.splitlines() if a.strip()],
                             'evidence_refs':[e.strip() for e in evidence.splitlines() if e.strip()],
                             'review_date':review}
                    if api('POST','/v1/intelligence/decisions',payload):st.rerun()
    if decisions:
        with st.expander('Report an observed outcome (does not certify it)'):
            index=st.selectbox('Select decision',list(range(len(decisions))),format_func=lambda i:decisions[i]['title']+' · v'+str(decisions[i]['version']))
            d=decisions[index]
            with st.form('di_report_outcome'):
                outcome=st.text_area('Observed result or variance')
                source=st.text_input('Source reference')
                if st.form_submit_button('Record self-reported outcome'):
                    if api('POST',f"/v1/intelligence/decisions/{d['id']}/outcome",{'expected_version':d['version'],'outcome':outcome,'source_ref':source}):st.rerun()

elif page=='Enterprise Memory':
    hero('Evidence-backed organizational learning','Enterprise Memory','Search historical decisions, assumptions and reported outcomes. Literal search; no semantic similarity claims.')
    q=st.text_input('Search decisions and lessons',placeholder='rollout cost adoption')
    result=api('GET','/v1/intelligence/memory?q='+requests.utils.quote(q)) or {}
    st.caption(f"Search: {result.get('method','keyword')} · {result.get('count',0)} matches")
    for d in result.get('decisions',[]):
        with st.expander(d['title']):
            st.markdown('**Decision:** '+d['option_chosen']);st.write('**Why:**',d['rationale'])
            st.write('**Assumptions:**',d['assumptions']);st.write('**Outcome:**',d['outcome'] or 'Not yet observed')
            st.write('**Source refs:**',d['evidence_refs']+[d['outcome_source']] if d['outcome_source'] else d['evidence_refs'])

elif page in ('Transformation Risk Radar','AI Economics Workbench','Copilot Transformation Office','Workforce Transformation Office','Agent Workforce Control Center'):
    config={
       'Transformation Risk Radar':('risk','Transformation Risk Radar','Register enterprise AI threats, impact, likelihood and mitigations.',{'category':'data','likelihood':0.4,'impact_usd':100000,'mitigation':'Independent quality gate','status':'open'}),
       'AI Economics Workbench':('economics','AI Economics Workbench','Actual cost and volume inputs for cost per task and successful outcome.',{'task_count':1000,'successful_tasks':900,'cost_usd':1500,'measurement_period':'2026-10'}),
       'Copilot Transformation Office':('copilot','Copilot Transformation Office','Track license deployment, activation and usage with transparent provenance.',{'licenses':500,'active_users':235,'task_count':0,'successful_tasks':0,'cost_usd':0,'program':'M365 Copilot'}),
       'Workforce Transformation Office':('workforce','Workforce Transformation Office','Track adoption programs, skills cohorts and readiness without intrusive worker scoring.',{'eligible_employees':400,'trained_employees':200,'active_users':150,'skill':'AI fundamentals'}),
       'Agent Workforce Control Center':('agent','Agent Workforce Control Center','Register agents, human owners, permitted capabilities, reliability and spend.',{'purpose':'Document QA','risk_tier':'medium','allowed_tools':[],'task_count':100,'successful_tasks':92,'cost_usd':30})}
    kind,title,subtitle,default=config[page]
    hero('Evidence-first operating model',title,subtitle)
    if kind=='risk':st.caption('Risk likelihood and impact are estimates; expected exposure is not a calibrated forecast.')
    entries=api('GET','/v1/intelligence/records?kind='+kind) or []
    table(entries)
    if kind in ('agent','copilot','economics'):
        calc_sum=api('GET','/v1/intelligence/economics-summary') or {}
        matched=[x for x in calc_sum.get('items',[]) if x['kind']==kind]
        if matched:
            st.subheader('Unit economics · self-reported')
            table(matched)
    initiatives=api('GET','/v1/initiatives') or []
    if not initiatives:
        st.info('Create an initiative first to register linked observations.')
    else:
        with st.expander('Register a linked observation',expanded=not bool(entries)):
            # Form clear-on-submit and a per-form idempotency token prevent accidental repeats.
            idem_key='new_record_token_'+kind
            if idem_key not in st.session_state:st.session_state[idem_key]=str(__import__('uuid').uuid4())
            with st.form('di_add_'+kind,clear_on_submit=True):
                initiative=st.selectbox('Related initiative',initiatives,
                    format_func=lambda i:i['name']+' · '+i['owner'],key='fk_initiative_'+kind)
                title=st.text_input('Program, asset or risk name',max_chars=180)
                # Owner is selected from legitimate tenant initiative owners, not typed as an ID.
                owner_names=sorted({i['owner'] for i in initiatives if i.get('owner')})
                owner=st.selectbox('Accountable business owner',owner_names,index=owner_names.index(initiative['owner']) if initiative['owner'] in owner_names else 0)
                payload={'initiative_id':initiative['id']}
                if kind=='risk':
                    payload['category']=st.selectbox('Risk category',['data','security','adoption','talent','funding','vendor','regulatory','delivery'])
                    payload['likelihood']=st.slider('Estimated probability',0.0,1.0,0.4,0.05)
                    payload['impact_usd']=st.number_input('Estimated exposure (USD)',min_value=0.0,value=100000.0,step=1000.0)
                    payload['mitigation']=st.text_area('Mitigation and mitigation evidence',max_chars=2000)
                    payload['status']=st.selectbox('Risk status',['open','mitigating','monitoring','closed'])
                elif kind=='economics':
                    payload['task_count']=st.number_input('Executed tasks',min_value=0,value=1000,step=10)
                    payload['successful_tasks']=st.number_input('Successful tasks',min_value=0,value=900,step=10)
                    payload['cost_usd']=st.number_input('Actual reported total cost (USD)',min_value=0.0,value=1500.0,step=50.0)
                    payload['measurement_period']=st.text_input('Measurement period (YYYY-MM)',value=datetime.now().strftime('%Y-%m'))
                elif kind=='copilot':
                    payload['program']=st.selectbox('Product family',['M365 Copilot','GitHub Copilot','Security Copilot','Copilot Studio','Other'])
                    payload['licenses']=st.number_input('Assigned licenses',min_value=0,value=500)
                    payload['active_users']=st.number_input('Active users',min_value=0,value=235)
                    payload['task_count']=st.number_input('Observed tasks',min_value=0,value=0)
                    payload['successful_tasks']=st.number_input('Successful tasks',min_value=0,value=0)
                    payload['cost_usd']=st.number_input('Reported cost (USD)',min_value=0.0,value=0.0)
                elif kind=='workforce':
                    payload['skill']=st.selectbox('Skill program',['AI fundamentals','Prompt engineering','Agent operations','Responsible AI','AI security','Data literacy'])
                    payload['eligible_employees']=st.number_input('Eligible employees',min_value=0,value=400)
                    payload['trained_employees']=st.number_input('Training completions',min_value=0,value=200)
                    payload['active_users']=st.number_input('Observed active AI users',min_value=0,value=150)
                elif kind=='agent':
                    payload['purpose']=st.text_area('Business process and agent purpose',max_chars=2000)
                    payload['risk_tier']=st.selectbox('Agent risk tier',['low','medium','high','critical'])
                    payload['allowed_tools']=st.multiselect('Permitted tool classes',['read_reports','draft_artifacts','run_evaluations','request_approval'])
                    payload['task_count']=st.number_input('Executed agent tasks',min_value=0,value=100)
                    payload['successful_tasks']=st.number_input('Successful agent tasks',min_value=0,value=92)
                    payload['cost_usd']=st.number_input('Reported agent cost (USD)',min_value=0.0,value=30.0)
                classification=st.selectbox('Evidence classification',['self_reported','modeled'])
                submitted=st.form_submit_button('Save observation',type='primary')
            if submitted:
                if kind in ('agent','copilot','economics') and payload.get('successful_tasks',0)>payload.get('task_count',0):
                    st.error('Successful tasks cannot exceed total tasks.')
                elif kind=='copilot' and payload['active_users']>payload['licenses']:
                    st.error('Active users cannot exceed assigned licenses.')
                elif kind=='workforce' and (payload['trained_employees']>payload['eligible_employees'] or payload['active_users']>payload['eligible_employees']):
                    st.error('Active and trained employees must not exceed eligible employees.')
                elif not title.strip():st.error('Enter a descriptive name.')
                else:
                    result=api('POST','/v1/intelligence/records',{'kind':kind,'name':title.strip(),
                        'owner':owner,'payload':payload,'evidence_status':classification,
                        'request_id':st.session_state[idem_key]})
                    if result:
                        st.session_state[idem_key]=str(__import__('uuid').uuid4())
                        st.toast('Saved once to PostgreSQL; fresh form ready.',icon='✅')
                        st.rerun()
    if kind=='risk' and entries:
        st.subheader('Modeled expected exposure')
        rows=[]
        for r in entries:
            p=r['payload']
            try:
                likelihood=float(p.get('likelihood',0));impact=float(p.get('impact_usd',0))
                exposure=likelihood*impact if 0<=likelihood<=1 and impact>=0 else None
            except (TypeError,ValueError):exposure=None
            rows.append({'Risk':r['name'],'Owner':r['owner'],'Expected exposure (USD)':exposure,'Status':p.get('status','unassessed')})
        table(rows)

elif page=='Enterprise Decision Twin':
    hero('Capital allocation · counterfactuals','Enterprise Decision Twin','Reallocate constrained budgets among proposed initiatives; modeled results do not overwrite real portfolio records.')
    ins=api('GET','/v1/initiatives') or []
    initial=[{'name':i['name'],'expected_value':100000.0,'cost':50000.0,'category':'AI'} for i in ins[:15]]
    if not initial:initial=[{'name':'Customer Copilot','expected_value':150000,'cost':60000,'category':'Productivity'},{'name':'Inventory AI','expected_value':190000,'cost':90000,'category':'Operations'}]
    df=st.data_editor(pd.DataFrame(initial),num_rows='dynamic',hide_index=True,width='stretch',key='twin_table')
    budget=st.number_input('Available investment budget ($)',min_value=0.,value=150000.,step=10000.)
    max_items=st.number_input('Maximum selected initiatives',min_value=1,max_value=250,value=10)
    if st.button('Optimize scenario',type='primary'):
        result=api('POST','/v1/intelligence/scenario',{'budget':budget,'candidates':df.fillna(0).to_dict('records'),'max_items':int(max_items)})
        if result:
            st.metric('Modeled portfolio value',money(result.get('total_expected_value',0)))
            st.metric('Investment allocated',money(result.get('total_cost',0)))
            st.write('**Recommended candidates:**',result.get('selected',[]))
            st.info(result['disclosure'])
    st.caption('This is a constrained portfolio scenario, not a complete calibrated enterprise digital twin. Workforce, dependencies and adoption require further models.')

elif page=='Executive Narrative Studio':
    hero('Board and steering committee','Executive Narrative Studio','Generate a deterministic executive report only from tenant-scoped stored records; requires human review.')
    audience=st.selectbox('Audience',['board','steering committee','transformation lead'])
    if st.button('Generate evidence-linked executive brief',type='primary'):
        report=api('POST','/v1/intelligence/executive-narrative',{'audience':audience})
        if report:
            st.warning(report['status']);st.write(report['narrative'])
            st.markdown('**Source endpoints**');st.write(report['source_refs'])
            st.download_button('Download draft narrative',report['narrative'],file_name='decision-os-executive-brief.txt')



elif page in ('Microsoft Transformation','AWS Operational Readiness','Google Evaluation & Safety'):
    from ui.vendor_playbooks import render_vendor_playbook
    render_vendor_playbook(page,api=api,nav=navigate_to)

elif page=='Industry Intelligence':
    from ui.industry_intelligence import render as render_industry_intelligence
    render_industry_intelligence(api=api,navigate=navigate_to)

elif page=='Architecture Mastery':
    from ui.architecture_mastery import render as render_architecture_mastery
    render_architecture_mastery(api=api,navigate=navigate_to)
elif page=='Strategic Twin Studio':
    from ui.strategic_twin import render as render_strategic_twin
    render_strategic_twin(api=api,navigate=navigate_to)

elif page=='Decision Operations':
    from ui.decision_operations import render as render_decision_operations
    render_decision_operations(api=api,navigate=navigate_to)

elif page=='Ecosystem Intelligence':
    from ui.ecosystem_intelligence import render_ecosystem_intelligence
    render_ecosystem_intelligence(api=api,navigate=navigate_to)

elif page=='Outcome Economics':
    from ui.outcome_economics import render as render_outcome_economics
    render_outcome_economics(api=api,navigate=navigate_to)

elif page=='Decision Event Ledger':
    from ui.decision_event_console import render as render_event_console
    render_event_console(api=api,navigate=navigate_to)
elif page=='Decision Ledger':
    from ui.decision_ledger import render as render_decision_ledger
    render_decision_ledger(api=api,navigate=navigate_to)

elif page=='Decision Quality & Assumption Engine':
    from ui.decision_quality import render as render_decision_quality
    render_decision_quality(api=api,navigate=navigate_to)

elif page=='Decision Academy':
    from ui.decision_academy import render_decision_academy
    render_decision_academy()

elif page=='Strategy & Outcomes R5.5':
    hero('Enterprise product strategy · R5.5','Strategy-to-Outcomes','Connect strategic priorities and product discovery to governed decisions, trustworthy Key Results, and recorded outcomes.')
    tabs=st.tabs(['1 · Strategy','2 · Outcome Contracts','3 · Discovery & Assumptions','4 · Decision Lineage'])
    focus=api('GET','/v1/strategy/focus-areas') or []
    objectives=api('GET','/v1/strategy/objectives') or []
    krs=api('GET','/v1/strategy/key-results') or []
    decisions=api('GET','/v1/intelligence/decisions') or []
    with tabs[0]:
        a,b,c=st.columns(3)
        a.metric('Strategic areas',len(focus));b.metric('Objectives',len(objectives));c.metric('Key Results',len(krs))
        with st.expander('Create strategic Focus Area',expanded=not focus):
            with st.form('r55_focus',clear_on_submit=True):
                name=st.text_input('Strategic theme *',help='The enterprise priority to which outcomes and investments must align.')
                owner=st.text_input('Accountable leader *',help='Person responsible for strategic outcomes; not a system login.')
                description=st.text_area('Intent and boundaries')
                if st.form_submit_button('Create Focus Area'):
                    if len(name.strip())<5 or len(owner.strip())<2:
                        st.error('Enter a strategic theme (at least 5 characters) and an accountable leader.')
                    else:
                        if api('POST','/v1/strategy/focus-areas',{'title':name,'owner':owner,'description':description}):st.toast('Focus Area created');st.rerun()
        if focus:
            with st.expander('Define Objective',expanded=not objectives):
                with st.form('r55_objective',clear_on_submit=True):
                    f=st.selectbox('Parent Focus Area *',focus,format_func=lambda x:x['title'])
                    title=st.text_input('Objective *',help='Business outcome sought, not an engineering task.')
                    owner=st.text_input('Objective owner *')
                    horizon=st.date_input('Target horizon',value=datetime.now().date())
                    if st.form_submit_button('Create Objective'):
                        if len(title.strip())<5 or len(owner.strip())<2:
                            st.error('Enter an objective (at least 5 characters) and an objective owner.')
                        else:
                            if api('POST','/v1/strategy/objectives',{'focus_id':f['id'],'title':title,'owner':owner,'horizon':str(horizon)}):st.toast('Objective created');st.rerun()
        table([{'Focus area':f['title'],'Owner':f['owner']} for f in focus])
    with tabs[1]:
        if objectives:
            with st.expander('Define measurable Key Result',expanded=not krs):
                with st.form('r55_kr',clear_on_submit=True):
                    obj=st.selectbox('Objective *',objectives,format_func=lambda x:x['title'])
                    title=st.text_input('Key Result *',help='Measurable business outcome, not deployment completion.')
                    a,b=st.columns(2)
                    unit=a.text_input('Measurement unit *',value='%',help='Use consistent units for baseline, observations and target.')
                    direction=b.selectbox('Desired direction',['lower','higher'])
                    a,b=st.columns(2)
                    baseline=a.number_input('Baseline',value=100.0);target=b.number_input('Target',value=85.0)
                    owner=st.text_input('Measurement owner *',help='Accountable for source accuracy and methodology.')
                    target_date=st.date_input('Target date');stale=st.number_input('Stale after days',min_value=1,max_value=365,value=7)
                    good=len(title.strip())>=5 and len(owner.strip())>=2 and len(unit.strip())>=1 and baseline!=target
                    if not good:st.caption('Required: KR title ≥5 characters, measurement owner, unit and a target different from baseline.')
                    if st.form_submit_button('Create outcome contract'):
                        if not good:
                            st.error('Provide a Key Result title, measurement owner and unit, and choose a target different from baseline.')
                        else:
                            body={'objective_id':obj['id'],'title':title,'unit':unit,'direction':direction,'baseline':baseline,'target':target,'target_date':str(target_date),'measurement_owner':owner,'stale_after_days':stale}
                            if api('POST','/v1/strategy/key-results',body):st.toast('Outcome contract created');st.rerun()
        if krs:
            st.subheader('Observed results and freshness')
            table([{'KR':k['title'],'Target':k['target'],'Unit':k['unit'],'Status':k['measurement']['state'],'Attribution':(k['measurement'].get('observation') or {}).get('attribution','—'),'Confidence':(k['measurement'].get('observation') or {}).get('confidence','unknown')} for k in krs])
            with st.expander('Record an observation'):
                with st.form('r55_observation',clear_on_submit=True):
                    k=st.selectbox('Measured KR *',krs,format_func=lambda x:x['title'])
                    value=st.number_input('Observed metric value',value=0.0)
                    observed=st.date_input('Observation date',value=datetime.now().date())
                    source=st.selectbox('Source',['manual','telemetry','financial_system','survey','composite'])
                    ref=st.text_input('Source evidence reference *',help='Auditable link or identifier for the actual measurement.')
                    confidence=st.selectbox('Assessed confidence',['unknown','low','moderate','high'],help='Must be assessed using documented evidence; not inferred from source type.')
                    attribution=st.selectbox('Attribution',['unattributed','correlated','estimated','causal'])
                    limitations=st.text_area('Methodology / confounding factors',help='Required for a causal claim; recommended for any attribution.')
                    if st.form_submit_button('Record measurement'):
                        if len(ref.strip())<3 or (attribution=='causal' and not limitations.strip()):
                            st.error('Provide a source evidence reference (at least 3 characters); causal attribution also needs an identification method.')
                        else:
                            body={'key_result_id':k['id'],'value':value,'observed_at':str(observed)+'T12:00:00Z','source':source,'source_ref':ref,'confidence':confidence,'attribution':attribution,'limitations':limitations}
                            if api('POST','/v1/strategy/observations',body):st.toast('Observation saved; target status recalculated');st.rerun()
        else:st.info('Create an Objective and its Key Result in the Strategy tab first.')
    with tabs[2]:
        st.info('Discovery and assumptions are linked to an existing governed Executive Decision; they do not bypass funding or approval.')
        if decisions:
            with st.expander('Register a testable assumption'):
                with st.form('r55_assumption',clear_on_submit=True):
                    d=st.selectbox('Linked Executive Decision *',decisions,format_func=lambda x:x['title'])
                    statement=st.text_area('Assumption to test *',help='Describe a falsifiable customer, technical or economic premise.')
                    confidence=st.selectbox('Current confidence',['unknown','low','moderate','high'])
                    if st.form_submit_button('Register assumption'):
                        if len(statement.strip())<10:
                            st.error('Describe a testable assumption with at least 10 characters.')
                        else:
                            if api('POST','/v1/strategy/assumptions',{'decision_id':d['id'],'statement':statement,'confidence':confidence}):st.toast('Assumption recorded');st.rerun()
            with st.expander('Pre-register discovery experiment'):
                with st.form('r55_experiment',clear_on_submit=True):
                    d=st.selectbox('Governed decision *',decisions,format_func=lambda x:x['title'])
                    job=st.text_input('Customer job-to-be-done *')
                    segment=st.text_input('Customer segment *')
                    hypothesis=st.text_area('Testable hypothesis *')
                    method=st.selectbox('Experiment method',['prototype','pilot','ab_test','concierge','wizard_of_oz'])
                    metric=st.text_input('Success metric *')
                    direction=st.selectbox('Success direction',['higher','lower'])
                    threshold=st.number_input('Predeclared success threshold',value=10.0)
                    evidence=st.text_input('Experiment protocol / evidence reference *')
                    enabled=min(len(job.strip()),len(hypothesis.strip()))>=10 and min(len(segment.strip()),len(metric.strip()))>=2 and len(evidence.strip())>=3
                    if st.form_submit_button('Pre-register experiment'):
                        if not enabled:
                            st.error('Complete the customer job, segment, hypothesis, success metric, and evidence reference before submission.')
                        else:
                            body={'decision_id':d['id'],'customer_job':job,'segment':segment,'hypothesis':hypothesis,'method':method,'metric':metric,'direction':direction,'threshold':threshold,'evidence_ref':evidence}
                            if api('POST','/v1/strategy/experiments',body):st.toast('Experiment success threshold frozen');st.rerun()
            exps=api('GET','/v1/strategy/experiments') or []
            table([{'Hypothesis':e['hypothesis'],'Metric':e['metric'],'Predeclared threshold':e['threshold'],'Result':e['result'],'Observed':e['observed_value']} for e in exps])
            pending=[e for e in exps if e['result']=='pending']
            if pending:
                with st.form('r55_result',clear_on_submit=True):
                    e=st.selectbox('Evaluate a pre-registered experiment',pending,format_func=lambda x:x['hypothesis'])
                    measured=st.number_input('Observed experiment result',value=0.0)
                    source=st.text_input('Result evidence reference *')
                    if st.form_submit_button('Evaluate against original threshold'):
                        if len(source.strip())<3:
                            st.error('Provide a result evidence reference with at least 3 characters.')
                        else:
                            if api('POST',f"/v1/strategy/experiments/{e['id']}/result",{'expected_version':e['version'],'observed_value':measured,'evidence_ref':source}):st.toast('Experiment evaluated');st.rerun()
        else:st.info('Register an Executive Decision before creating hypotheses or assumptions.')
    with tabs[3]:
        if krs and decisions:
            with st.form('r55_link'):
                k=st.selectbox('Key Result *',krs,format_func=lambda x:x['title'])
                d=st.selectbox('Executive Decision *',decisions,format_func=lambda x:x['title'])
                if st.form_submit_button('Link Key Result to Decision'):
                    if api('POST','/v1/strategy/decision-links',{'key_result_id':k['id'],'decision_id':d['id']}):st.toast('Strategic lineage linked');st.rerun()
            selected=st.selectbox('Replay strategic decision lineage',decisions,format_func=lambda x:x['title'],key='r55_lineage')
            lineage=api('GET',f"/v1/strategy/lineage/{selected['id']}")
            if lineage:
                table([{'Focus Area':x['focus_area']['title'],'Objective':x['objective']['title'],'Key Result':x['key_result']['title'],'Initiative ID':lineage['initiative']} for x in lineage['chains']])
                st.caption('Initiative ID links to its R4 technical execution records through the existing execution endpoints.')
        else:st.info('Create a Key Result and an Executive Decision first to connect strategy through execution.')

elif page=='Decision Action Center':
    hero('Enterprise transformation · Governed action','Decision Action Center','From a funded decision to an evidence-backed intervention, independent review, and accountable delivery.')
    st.caption('PMI / PMBOK: business case → plan → authorization → monitor & control → outcome. SAFe LPM: funding → execution → feedback. This is a methodology-informed workflow, not PMI or SAFe certification.')
    decisions=api('GET','/v1/intelligence/decisions') or []
    packets=api('GET','/v1/decisions-governed/packets') or []
    actions=api('GET','/v1/decisions-governed/actions') or []
    cols=st.columns(4)
    cols[0].metric('Decisions',len(decisions))
    cols[1].metric('Pending review',sum(p['status']=='draft' for p in packets))
    cols[2].metric('Approved packets',sum(p['status']=='approved' for p in packets))
    cols[3].metric('Accountable actions',len(actions))
    phases=st.tabs(['01 · Context & lineage','02 · Prepare proposal','03 · Independent review','04 · Follow-through'])
    if not decisions:
        st.info('Create an executive decision in Executive Decision Ledger to start the governed workflow.')
    else:
        with phases[0]:
            st.markdown('### Select the approved business context')
            selected=st.selectbox('Executive decision *',decisions,format_func=lambda x:x['title']+' · '+x['id'][:8],key='r52_selected',help='This decision anchors every proposed action to an existing enterprise funding or governance record.')
            context=api('GET','/v1/decisions-governed/context/'+selected['id']) or {}
            st.caption('Data is retrieved from the authenticated tenant. Financial claims remain assumptions until verified.')
            x,y,z=st.columns(3)
            x.metric('Linked execution tasks',len(context.get('tasks',[])))
            y.metric('Open severe trust findings',context.get('severe_open_findings',0))
            z.metric('Evidence references',len(context.get('evidence_refs',[])))
            if context.get('tasks'):
                st.markdown('**Actual execution tasks**')
                table(context['tasks'])
            if context.get('assumptions'):st.info('Decision assumptions: '+str(context['assumptions'])[:450])
        with phases[1]:
            st.markdown('### Source-first Action Packet preparation')
            st.caption('Use a context-generated draft as a starting point; review it before submitting. This is deterministic prefill, not autonomous AI.')
            tasks=context.get('tasks',[])
            task_opts=[('TASK · '+t.get('title','Task')+' · '+t['id'][:8],t['id']) for t in tasks]
            refs=context.get('evidence_refs',[])
            evidence_options=[('DECISION EVIDENCE · '+str(r),str(r)) for r in refs if r]
            evidence_options+=task_opts
            evidence_options=list(dict((v,(k,v)) for k,v in evidence_options).values())
            if not evidence_options:
                st.warning('No existing evidence or execution task is linked to this decision. Add evidence in the relevant workspace before proposing an action.')
            init_key='r55_draft_decision'
            if st.session_state.get(init_key)!=selected['id']:
                st.session_state[init_key]=selected['id']
                st.session_state['r55_title']='Request accountable review of '+selected['title'][:90]
                st.session_state['r55_rationale']='Review the documented decision and linked work. Verify blockers, evidence, impact and responsible owner before authorizing an intervention.'
                st.session_state['r55_ref_values']=[]
                st.session_state['r55_nonce']=secrets.token_urlsafe(24)
            if st.button('Generate draft from linked records',key='r55_generate',type='secondary'):
                open_tasks=[t for t in tasks if t.get('status') in ('blocked','delayed')]
                main=open_tasks[0] if open_tasks else (tasks[0] if tasks else None)
                st.session_state['r55_title']=('Review blocked task: '+main['title'])[:180] if main else 'Review decision: '+selected['title'][:150]
                st.session_state['r55_rationale']=(f"Execution task '{main['title']}' is recorded as {main.get('status','unknown')}. Review the cause, risks, and possible interventions against the funding decision. No financial amount has been independently verified." if main else 'Assess this executive decision against its recorded assumptions and evidence before recommending a controlled intervention.')
                st.session_state['r55_ref_values']=[main['id']] if main else ([evidence_options[0][1]] if evidence_options else [])
                st.rerun()
            left,right=st.columns([1,1])
            kind=left.selectbox('Proposed action *',['request_review','assign_reviewer','create_remediation','propose_budget_change','pause_initiative'],format_func=lambda k:{'request_review':'Request formal review','assign_reviewer':'Assign reviewer','create_remediation':'Create remediation','propose_budget_change':'Propose budget change','pause_initiative':'Request initiative pause'}[k],key='r55_kind',help='The action is a proposal only. No production systems or funds are changed.')
            cost=right.number_input('Proposed cost (USD)',min_value=0.,max_value=100000000.,value=0.,step=100.,key='r55_cost',help='Explicit advisory estimate only; finance authorization is separate.')
            title=st.text_input('Intervention title *',key='r55_title',max_chars=180,help='Name the precise intervention, at least 5 characters.')
            if len(title.strip())<5:st.caption(f'⚠ Add {5-len(title.strip())} more characters to the title.')
            rationale=st.text_area('Rationale and expected outcome *',key='r55_rationale',height=130,max_chars=3000,help='Explain the recorded issue and expected outcome. At least 20 characters; do not invent financial impact.')
            if len(rationale.strip())<20:st.caption(f'⚠ Add {20-len(rationale.strip())} more characters to the rationale.')
            available={v for _,v in evidence_options}
            st.session_state['r55_ref_values']=[v for v in st.session_state.get('r55_ref_values',[]) if v in available]
            ev=st.multiselect('Linked evidence / execution task records *',options=[v for _,v in evidence_options],format_func=lambda v:dict((v,k) for k,v in evidence_options).get(v,v),key='r55_ref_values',help='Choose real records linked to this executive decision. Arbitrary text like TASK-123 is not a verified reference.') if evidence_options else []
            has_permission=who.get('role') in ('admin','lead','editor','finance')
            valid=bool(has_permission and evidence_options and ev and len(title.strip())>=5 and len(rationale.strip())>=20)
            if not has_permission:st.warning('Your current role may inspect context but cannot draft an Action Packet.')
            if not ev:st.caption('⚠ Select at least one existing evidence or task record.')
            st.info('The backend independently re-checks tenant, decision, authorization, budget and security findings.')
            if st.button('Create packet for independent review',key='r55_create',type='primary',disabled=not valid):
                payload={'decision_id':selected['id'],'title':title.strip(),'action_kind':kind,'rationale':rationale.strip(),'evidence_refs':ev,'expected_spend_cents':round(cost*100),'request_id':st.session_state['r55_nonce']}
                result=api('POST','/v1/decisions-governed/packets',payload)
                if result:
                    st.session_state['r55_nonce']=secrets.token_urlsafe(24)
                    st.toast('Packet '+result['id'][:8]+' created — review pending.')
                    st.session_state['r55_last_created']=result['id']
                    st.rerun()
            if st.session_state.get('r55_last_created'):st.success('Last submitted packet: '+st.session_state['r55_last_created'])
        with phases[2]:
            st.markdown('### Independent human review')
            pending=[p for p in packets if p['status']=='draft']
            if not pending:st.success('No packets currently await review.')
            else:
                eligible=[p for p in pending if p['created_by']!=who['user']]
                mine=[p for p in pending if p['created_by']==who['user']]
                if mine:st.warning(f"{len(mine)} packet(s) were drafted by your current identity ({who['user']}). You cannot approve your own submission. A separately authenticated reviewer is required.")
                if not eligible:st.info('No packets are eligible for your identity. Sign in with a distinct, issued reviewer credential using the optional local identity verification panel, or use a separately configured reviewer session.')
                elif who.get('role') not in ('admin','reviewer','lead','finance'):st.warning('Your role does not permit packet review.')
                else:
                    pick=st.selectbox('Awaiting review',eligible,format_func=lambda p:p['title']+' · '+p['id'][:8]+' · submitted by '+p['created_by'],key='r55_review_pick')
                    st.write('**Proposed action:**',pick['title'])
                    st.write('**Draft policy:**',pick.get('policy_draft',{}).get('result','Unknown'))
                    st.caption('The backend repeats its policy checks at review time. A prior draft result is not final authorization.')
                    st.write('**Evidence references:**',', '.join(pick.get('evidence_refs',[])))
                    decision=st.radio('Reviewer decision',['approve','reject'],horizontal=True,key='r55_disposition',format_func=lambda v:'Approve accountable follow-up' if v=='approve' else 'Reject proposal')
                    assignee=st.text_input('Action owner *',key='r55_assignee',help='Named person responsible for follow-through; must be confirmed before approval.')
                    if st.button('Record independent review',type='primary',disabled=len(assignee.strip())<2,key='r55_review'):
                        result=api('POST',f"/v1/decisions-governed/packets/{pick['id']}/review",{'expected_version':pick['version'],'decision':decision,'assigned_owner':assignee.strip()})
                        if result:st.toast('Review decision recorded');st.rerun()
        with phases[3]:
            st.markdown('### Accountable follow-through')
            if actions:table(actions)
            else:st.info('Approved packets generate accountable follow-up records. No automatic spending, task reassignment, or deployment occurs.')
            st.caption('All external actions remain human-controlled. The next independently authorized execution layer must repeat authorization and policy checks immediately before changing an external system.')

elif page=='Decision Replay & Memory':
    hero('R5.4 · Institutional learning','Decision Replay & Memory','Inspect preserved historical decision snapshots and evidence-qualified prior outcomes.')
    decisions=api('GET','/v1/intelligence/decisions') or []
    if decisions:
        selected=st.selectbox('Replay decision',decisions,format_func=lambda x:x['title']+' · '+x['id'][:8],key='replay_selected')
        replay=api('GET','/v1/decisions-governed/replay/'+selected['id']) or {}
        st.info(replay.get('limitations',''))
        snaps=replay.get('historical_snapshots',[])
        if not snaps:st.warning('No historical snapshot yet. Snapshots start when an R5.2 Action Packet is created; past decisions cannot be reconstructed retroactively.')
        for r in snaps:
            with st.expander('Preserved snapshot · '+str(r['recorded_at'])):
                st.caption('SHA-256 content integrity check: '+('matches' if r['hash_valid'] else 'MISMATCH — investigate'))
                st.json(r['data'])
        table([{'id':x['id'],'title':x['title'],'status':x['status']} for x in replay.get('action_packets',[])])
    q=st.text_input('Search organizational decision memory',placeholder='e.g. security review',key='replay_search')
    memory=api('GET','/v1/decisions-governed/memory?q='+requests.utils.quote(q)) or {}
    st.caption('Keyword retrieval only; no statistical claims are inferred from unverified outcomes.')
    table(memory.get('items',[]))

elif page=='AI Risk & Regulatory Office':
    hero('R5.0 · Trust before autonomy','AI Risk & Regulatory Office','Risk classification, responsibility, evidence and independent review linked to the original funding decision.')
    summary=api('GET','/v1/trust/summary') or {}
    a,b,c=st.columns(3)
    a.metric('Assessments',summary.get('assessments',0));b.metric('Awaiting review',summary.get('pending_review',0));c.metric('Unresolved high/critical findings',summary.get('open_high_critical',0))
    st.warning('Preliminary screening—not legal advice, compliance certification or production-release authorization.')
    initiatives=api('GET','/v1/initiatives') or []
    # Outside st.form so changing the initiative reruns Streamlit and reloads options.
    if initiatives:
        st.markdown('#### Register AI system and regulatory assessment')
        init=st.selectbox('Initiative',initiatives,format_func=lambda i:i['name'],key='r5_initiative')
        valid=api('GET',f"/v1/initiatives/{init['id']}/funding-decisions") or []
        if not valid:
            st.warning('No funding decisions linked to this initiative. Create one in Executive Decision Ledger, then return here.')
            if st.button('Refresh funding decisions',key='r5_refresh_decisions'):
                _get.clear();st.rerun()
        # Reactive widgets outside a Streamlit form: changes validate on each rerun.
        from ui.validation import (
            autofill_from_context,
            errors_for_assessment,
            regulatory_details_required,
        )
        scope_key=f"r511_{init['id']}"
        decision=st.selectbox('Funding / executive decision *',valid,
            format_func=lambda d:d.get('title',d['id']),disabled=not valid,
            key='r511_decision_'+init['id'],help='Connects the risk assessment to the executive decision that authorized the initiative.')
        context=autofill_from_context(init,decision if valid else None)
        st.caption('Fields marked * are mandatory. Suggested values come from existing enterprise records; review and confirm them before submission.')
        title=st.text_input('AI system / application name *',value=context['title'],key=scope_key+'_title',help='Identifies the system that risk owners and auditors will assess.')
        st.caption('Prefilled from initiative metadata — review before submitting.')
        intended=st.text_area('Intended use and affected people *',value=context['intended_use'],key=scope_key+'_purpose',help='Explain the business process, affected people and what the AI does. Minimum 20 characters.')
        st.caption(f'{len(intended.strip())}/20 minimum characters. Review this draft for factual accuracy.')
        owner=st.text_input('Accountable risk owner *',value=context['owner'],key=scope_key+'_owner',help='Responsible person for reviewing risk findings and mitigation. Minimum 2 characters.')
        geo_choices=st.multiselect('Deployment jurisdictions / geographies *', ['India','EU / EEA','United Kingdom','United States','Canada','Singapore','Australia','Other / multi-region'], key=scope_key+'_geos',help='Choose the regions where the system is deployed, used, or placed on a market. More than one may apply.')
        extra_geo=st.text_input('Other jurisdiction details *',key=scope_key+'_geo_other',help='Identify the additional countries or regions.') if 'Other / multi-region' in geo_choices else ''
        geography=', '.join([g for g in geo_choices if g!='Other / multi-region']+[extra_geo.strip()] if extra_geo.strip() else [g for g in geo_choices if g!='Other / multi-region'])
        system_type=st.selectbox('AI system category *',['assistive','decision_support','autonomous_agent','general_purpose','other'],key=scope_key+'_systemtype',help='Determines which regulatory questions and control areas need review.')
        role=st.selectbox('AI Act organizational role *',['unknown','deployer','provider','other'],key=scope_key+'_role',help='The provider/deployer distinction can change legal obligations. Unknown is permitted for preliminary screening.')
        flagged=regulatory_details_required(geography,system_type,role,intended)
        if flagged:
            with st.expander('Regulatory applicability — additional review required',expanded=True):
                st.info('Potential applicability only. This does not classify an AI system under the EU AI Act.')
                classification=st.selectbox('Provisional classification *',['review_required','potential_high_risk','potential_prohibited','transparency_review','other_assessed'],key=scope_key+'_classification',help='Preliminary screening category. Legal review remains required for ambiguous or high-risk use.')
                st.caption('EU-related checks can apply based on market connection, intended use and organizational role, not geography alone.')
        else:
            classification='review_required'
        source=st.text_input('Assessment basis / technical document reference *',placeholder='e.g. ARCH-2026-042 or https://approved-repository/example',key=scope_key+'_source',help='Provide a real document identifier or evidence reference. Minimum 3 characters.')
        a1,a2,a3=st.columns(3)
        sensitive=a1.checkbox('Personal / sensitive information',key=scope_key+'_sensitive')
        consequential=a2.checkbox('Material impact on individuals',key=scope_key+'_consequential')
        autonomous=a3.checkbox('Agent can take external actions',key=scope_key+'_autonomous')
        data={'title':title,'intended_use':intended,'owner':owner,'geography':geography,'assessment_source':source,'decision_id':decision['id'] if valid else None}
        issues=errors_for_assessment(data)
        if 'Other / multi-region' in geo_choices and len(extra_geo.strip())<2:issues['geography_details']='Enter the additional jurisdiction(s), not just Other.'
        for field,message in issues.items():st.error(f'{field}: {message}',icon='⚠️')
        if scope_key+'_submission_id' not in st.session_state:
            st.session_state[scope_key+'_submission_id']=secrets.token_urlsafe(24)
        if st.button('Record preliminary assessment',key=scope_key+'_submit',type='primary',disabled=bool(issues) or not valid,
                     help='Disabled until all mandatory fields are valid and a funding decision is selected.'):
            payload={'initiative_id':init['id'],'decision_id':decision['id'],'request_id':st.session_state[scope_key+'_submission_id'],
                     'title':title.strip(),'ai_role':role,'geography':geography.strip(),'intended_use':intended.strip(),
                     'owner':owner.strip(),'assessment_source':source.strip(),'classification':classification,
                     'risk_factors':{'sensitive_data':sensitive,'consequential_decision':consequential,'external_actions':autonomous,'system_type':system_type}}
            result=api('POST','/v1/trust/assessments',payload)
            if result:
                st.session_state['r511_last_created']=result['id']
                for key in list(st.session_state):
                    if key.startswith(scope_key+'_'):del st.session_state[key]
                st.toast(f"Assessment recorded: {result['id']}",icon='✅')
                st.rerun()
        if st.session_state.get('r511_last_created'):
            st.success('Risk assessment saved: '+st.session_state['r511_last_created']+'. Independent review is still required.')
    else:st.info('Create an initiative and funding decision first.')
    assessments=api('GET','/v1/trust/assessments') or []
    table(assessments)
    if assessments:
        selected=st.selectbox('Inspect risk assessment',assessments,format_func=lambda x:x['title']+' · '+x['review_status'],key='r5_assessment_inspect')
        detail=api('GET','/v1/trust/assessments/'+selected['id']) or {}
        st.markdown('**Risk factors and lineage**');st.json({'decision_id':selected['decision_id'],'initiative_id':selected['initiative_id'],'factors':selected['risk_factors'],'classification':selected['classification']})
        st.caption(detail.get('disclosure',''))
        if detail.get('release_advisory',{}).get('high_or_critical_unresolved',0)>0:st.error('High or critical findings remain unresolved; escalate to release gate owner.')
        crosswalk=api('GET','/v1/trust/frameworks') or {}
        controls=crosswalk.get('crosswalk',{})
        with st.form('r5_control_form',clear_on_submit=True):
            framework=st.selectbox('Reference framework',list(controls))
            control=st.selectbox('Control / reference family',controls.get(framework,[]))
            evidence=st.text_input('Evidence reference (actual document / scan / review URL)')
            quality=st.selectbox('Evidence classification',['self_reported','measured','independently_checked'])
            if st.form_submit_button('Submit evidence for reviewer'):
                if api('POST',f"/v1/trust/assessments/{selected['id']}/controls",{'framework':framework,'control_id':control,'evidence_reference':evidence,'evidence_quality':quality}):st.success('Evidence submitted, not independently verified');st.rerun()
        table(detail.get('control_evidence',[]))
        if who['role'] in ('reviewer','admin'):
            with st.form('r5_assess_review'):
                outcome=st.selectbox('Independent review decision',['accept_for_review','needs_changes'])
                note=st.text_area('Review rationale / evidence gaps')
                if st.form_submit_button('Record reviewer decision'):
                    if api('POST',f"/v1/trust/assessments/{selected['id']}/review",{'expected_version':selected['version'],'decision':outcome,'note':note}):st.success('Review recorded; NOT legal certification');st.rerun()
            submitted=[x for x in detail.get('control_evidence',[]) if x['status']=='submitted']
            if submitted:
                c=st.selectbox('Control evidence awaiting independent verification',submitted,format_func=lambda x:x['framework']+' '+x['control_id'])
                if st.button('Verify selected evidence'):
                    if api('POST',f"/v1/trust/controls/{c['id']}/verify",{}):st.rerun()

elif page=='AI Red Team Lab':
    hero('R5.1 · Security evidence and attack lineage','AI Red Team & Evaluation Lab','Import normalized PyRIT findings, triage vulnerabilities and link every finding to an executive decision. No synthetic pass rates.')
    st.warning('This screen imports observed findings; it does not execute PyRIT or certify OWASP coverage. Run authorized adversarial tests separately against an approved test environment.')
    assessments=api('GET','/v1/trust/assessments') or []
    if not assessments:st.info('Create a linked AI risk assessment first in AI Risk & Regulatory Office.')
    else:
        selected=st.selectbox('AI assessment',assessments,format_func=lambda a:a['title'],key='r5_rt_assess')
        detail=api('GET',f"/v1/trust/assessments/{selected['id']}") or {}
        st.markdown(f"**Decision lineage:** `{selected['decision_id']}` → initiative `{selected['initiative_id']}` → assessment `{selected['id']}`")
        with st.expander('Import PyRIT-normalized findings',expanded=False):
            st.caption('Use format pyrit_normalized_v1. Normalize PyRIT version-specific exports to this documented schema; raw PyRIT databases are not parsed.')
            sample={'format':'pyrit_normalized_v1','findings':[{'source_tool':'pyrit','source_run_id':'engagement-001','source_finding_id':'finding-001','category':'prompt_injection','severity':'high','title':'Untrusted retrieval instruction redirected output','evidence_reference':'artifact://redteam/case-001','observed_result':'Observed in an approved isolated test; describe result without secrets','remediation':'Constrain tool access and rerun evaluation'}]}
            st.code(json.dumps(sample,indent=2),language='json')
            raw=st.text_area('Normalized findings JSON',value=json.dumps(sample,indent=2),height=220)
            if st.button('Import observed findings for review',type='primary'):
                try:
                    result=api('POST',f"/v1/trust/assessments/{selected['id']}/findings/import",json.loads(raw))
                    if result:st.success(f"Imported {len(result['created_ids'])} finding(s); {len(result['duplicate_ids'])} already existed.");st.rerun()
                except json.JSONDecodeError as exc:st.error('Invalid JSON: '+str(exc))
        findings=detail.get('findings',[])
        table(findings)
        high=[x for x in findings if x['severity'] in ('high','critical') and x['status']!='false_positive']
        a,b,c=st.columns(3);a.metric('Recorded findings',len(findings));b.metric('Unresolved high/critical',len(high));c.metric('Verified as remediated',0)  # Verification needs actual retest artifacts
        if findings and who['role'] in ('reviewer','admin'):
            finding=st.selectbox('Finding for independent disposition',findings,format_func=lambda f:f['severity'].upper()+' · '+f['title'])
            with st.form('r5_finding_review'):
                disposition=st.selectbox('Disposition',['triaged','remediated_pending_retest','accepted_risk','false_positive'])
                note=st.text_area('Evidence-based review rationale; retest needed for closure')
                if st.form_submit_button('Record independent disposition'):
                    if api('POST',f"/v1/trust/findings/{finding['id']}/review",{'expected_version':finding['version'],'disposition':disposition,'note':note}):st.rerun()
        st.caption('R5 red team result is an evidence record, not proof that the AI system is safe or compliant.')

# Context-aware copilot, scoped to current page; specialist tabs supply their own context.
# Enterprise-wide questions belong to the separate Decision Copilot workspace.
if page not in ('Strategic Twin Studio','Architecture Mastery'):
    from ui.context_copilot import render as render_context_copilot
    render_context_copilot(api=api,workspace=page,tab='Workspace',key='page_copilot_'+re.sub(r'[^a-z0-9]','_',page.lower()))
