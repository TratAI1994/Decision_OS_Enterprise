"""Decision OS / CAIO Industry Intelligence.

Industry templates and demonstrations are illustrative. Live facts come exclusively from
an authenticated, tenant-scoped API adapter. Copilot is deterministic, not an LLM.
No data is written, submitted, approved, or executed by this module.
"""
from __future__ import annotations

import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import streamlit as st

VISION = ('Decision OS is an Industry Transformation Decision Intelligence Platform that helps '
          'enterprises evaluate strategic decisions, validate assumptions, measure value realization, '
          'quantify decision debt, and continuously learn from outcomes across banking, healthcare, '
          'manufacturing, government, technology, and AI ecosystems.')

@dataclass(frozen=True)
class Industry:
    name: str
    icon: str
    decisions: tuple[str, ...]
    kpis: tuple[str, ...]
    scenario: str
    confounders: tuple[str, ...]
    evidence: tuple[str, ...]
    review: str

INDUSTRIES: dict[str, Industry] = {
 'Banking':Industry('Banking','🏦',('Credit underwriting','Fraud detection','Core modernization'),('Default rate (bps)','Fraud losses','Risk-adjusted return'), 'Did underwriting AI reduce defaults, or did borrower mix and the economy change?',('Economic cycle','Credit policy changes'),('Segment baseline','Independent model validation','Fairness assessment'),'Model risk and credit governance'),
 'Insurance':Industry('Insurance','🛡️',('Claims triage','Underwriting automation','Fraud analytics'),('Claims handling time','Leakage ratio','Claims accuracy'), 'Claims costs rose after a sound AI triage approval. Was a catastrophe responsible rather than the deployment?',('Catastrophe severity','Claim mix'),('Baseline by claim class','Independent quality review','Claim event history'),'Claims oversight and customer fairness'),
 'Healthcare':Industry('Healthcare','🏥',('Clinical decision support','Patient flow','Capacity planning'),('Patient wait time','Safety events','Readmission rate'), 'Did patient flow AI reduce waiting without raising safety risk? Clinical sign-off is required.',('Case mix','Seasonality'),('Clinical safety study','Patient privacy review','Clinical oversight'),'Patient safety, privacy and clinical accountability'),
 'Manufacturing':Industry('Manufacturing','🏭',('Factory automation','Digital twins','Predictive maintenance'),('First-pass yield','Unplanned downtime','Cost per unit'), 'Factory yield improved after digital twin rollout. Did process tuning or supplier quality explain the gain?',('Supplier material quality','Product mix'),('Line-level baselines','Control-line comparison','Safety evaluation'),'OT safety and factory change control'),
 'Retail':Industry('Retail','🛒',('AI pricing','Inventory placement','Demand forecasting'),('Contribution margin','Stockout rate','Forecast bias'), 'Did AI pricing improve margin, or would margin have risen due to market shifts? Counterfactual required.',('Competitor pricing','Seasonality'),('Comparable stores','Price elasticity analysis','Promotion ledger'),'Pricing fairness and customer impact'),
 'Public Sector':Industry('Public Sector','🏛️',('Citizen service automation','Grant prioritization','Service modernization'),('Case resolution time','Appeal rate','Equity of access'), 'Did AI improve citizen service or increase denial and appeal disparities?',('Policy reform','Case complexity'),('Public impact assessment','Appeal audit','Accessibility review'),'Public accountability and appeal rights'),
 'Energy':Industry('Energy','⚡',('Grid optimization','Predictive asset maintenance','Generation planning'),('Outage minutes','Grid losses','Maintenance cost'), 'Did predictive maintenance prevent outages, or was demand unusually low?',('Weather','Demand fluctuations'),('Grid operations history','Reliability assessment','Asset baseline'),'Operational resilience and safety'),
 'Telecom':Industry('Telecom','📡',('5G network investment','Churn prediction','Network optimization'),('Customer churn','Network availability','Cost per GB'), 'Did targeted retention reduce churn or did competitor pricing change?',('Competitor promotions','Coverage changes'),('Control cohorts','Network quality telemetry','Subscriber segment definitions'),'Customer privacy and network resilience'),
 'Technology':Industry('Technology','💻',('Copilot productivity','Platform modernization','Engineering automation'),('Change failure rate','Lead time','Developer task completion'), 'Did a coding assistant improve deployment throughput without increasing defects?',('Team staffing','Release policy changes'),('DORA baselines','Security scan findings','Adoption cohorts'),'Software supply chain and agent scopes'),
 'Supply Chain':Industry('Supply Chain','🚚',('Fulfillment optimization','Warehouse automation','Routing intelligence'),('Cost per order','On-time delivery','Split shipment rate'), 'Did the optimizer reduce fulfillment costs or simply move cost to downstream carriers?',('Fuel prices','Seasonal demand'),('End-to-end cost ledger','Carrier SLA evidence','Lane-matched controls'),'Supply chain continuity and vendor accountability'),
 'Education':Industry('Education','🎓',('Learning copilot','Student success','Curriculum modernization'),('Completion rate','Learning gain','Student equity'), 'Did tutoring AI improve learning or did the cohort selection explain results?',('Selection bias','Instructor changes'),('Pre-post learning assessments','Privacy review','Comparison cohort'),'Learner safeguarding and equitable access'),
 'Enterprise IT':Industry('Enterprise IT','🖥️',('Cloud migration','Identity modernization','AIOps and DevSecOps'),('Incident MTTR','Cloud cost per workload','Deployment frequency'), 'Did cloud migration generate net savings after licensing, egress, migration and operational costs?',('Workload mix','Contract renegotiation'),('Cloud billing ledger','Pre/post workload baseline','Security architecture review'),'Platform access, audit and cost ownership'),
}

SAMPLE_PROMPTS = ('What evidence is missing?', 'Calculate 20% of 4500000', 'If expected 20 and observed 15, what is the gap?', 'Evaluate the industry scenario', 'Draft a governed initiative')


def decimal_number(raw: str | float | Decimal) -> Decimal | None:
    if isinstance(raw, bool): return None
    try:
        value = Decimal(str(raw).replace(',',''))
        return value if value.is_finite() else None
    except (ValueError, InvalidOperation): return None


def calculate_gap(expected, observed, direction='higher') -> dict:
    e, o = decimal_number(expected), decimal_number(observed)
    if e is None or o is None: return {'status':'UNAVAILABLE','reason':'Expected or observed number missing'}
    delta=o-e
    percentage=(delta/abs(e)*100) if e != 0 else None
    return {'status':'CALCULATED', 'expected':str(e), 'observed':str(o),
            'signed_gap':str(delta), 'gap_pct':str(round(percentage,2)) if percentage is not None else None,
            'target_met':o>=e if direction=='higher' else o<=e,
            'caveat':'Arithmetic only: no causal or financial reconciliation claim.'}


def monte_carlo_scenario(baseline, min_gain, most_likely_gain, max_gain, runs=3000, seed=21) -> dict:
    """Hypothetical triangular scenario simulation. Not a confidence interval or prediction."""
    values=[decimal_number(x) for x in (baseline,min_gain,most_likely_gain,max_gain)]
    if any(v is None for v in values): raise ValueError('All inputs must be finite numeric values.')
    b,lo,mid,hi=(float(x) for x in values)
    if not lo<=mid<=hi or abs(b)>1e15 or max(abs(lo),abs(hi))>1e15:
        raise ValueError('Require min ≤ likely ≤ max and bounded inputs.')
    if not 100<=runs<=20000: raise ValueError('Runs must be 100–20000.')
    rng=random.Random(seed)
    draws=sorted(b+rng.triangular(lo,hi,mid) for _ in range(runs))
    return {'p10':round(draws[int(.1*(runs-1))],2),'p50':round(draws[int(.5*(runs-1))],2),
            'p90':round(draws[int(.9*(runs-1))],2),'runs':runs,'seed':seed,
            'disclaimer':'Illustrative sensitivity to assumed inputs; not a forecast, empirical probability, or observed result.'}


def rubric_checks(industry: Industry, checks: dict[str,str]) -> dict:
    """Answer completeness only; no verified compliance and no automatic approval."""
    control_names=('Business objective and baseline','Counterfactual or alternatives',
                   'Risk and affected-person impact','Outcome source and measurement plan',
                   'Named accountable reviewer','Explicit stop/review condition')
    states={name: checks.get(name,'Not assessed') for name in control_names}
    complete=[name for name,val in states.items() if val=='Documented · pending verification']
    missing=[name for name,val in states.items() if val!='Documented · pending verification']
    return {'controls':states,'documented_count':len(complete),'total':len(states),
            'not_documented':missing,'industry':industry.name,
            'status':'SELF-REPORTED · UNVERIFIED'}


def load_authorized(api: Callable | None) -> tuple[list[dict], list[str]]:
    if api is None: return [], ['Authenticated Decision OS API not provided']
    try:
        data=api('GET','/v1/intelligence/decisions',quiet=True)
        if isinstance(data,list):
            return [r for r in data if isinstance(r,dict)],[]
        return [],['Decision API unavailable or returned an unexpected shape']
    except Exception:
        return [],['Decision API request failed; no company data is available']


def decision_copilot_response(question: str, industry: Industry, evidence: list[dict] | None=None) -> dict:
    """Deterministic calculator and contextual guide. Closed-domain intent matching only.
    Never labels generated prose as frozen, verified, causal or finance-approved.
    """
    q=question.strip()
    if not q: return {'kind':'REFUSAL','text':'Please ask a specific question.','references':[]}
    if len(q)>700: return {'kind':'REFUSAL','text':'Question too long (700-character limit).','references':[]}
    # Strict numeric grammar: avoids arbitrary Python evaluation or numerals found in IDs.
    m=re.fullmatch(r'(?:calculate\s+)?(-?\d+(?:\.\d+)?)\s*%\s+of\s+(-?\d+(?:\.\d+)?)\s*\??',q,re.IGNORECASE)
    if m:
        a,b=map(Decimal,m.groups()); result=(a*b)/100
        return {'kind':'CALCULATION','text':f'{a}% of {b} = {result:,.2f}. This is arithmetic, not a verified financial outcome.','references':[]}
    m=re.fullmatch(r'(?:if\s+)?expected\s+(-?\d+(?:\.\d+)?)\s+and\s+observed\s+(-?\d+(?:\.\d+)?),?\s+what\s+is\s+the\s+gap\??',q,re.IGNORECASE)
    if m:
        result=calculate_gap(*m.groups())
        return {'kind':'CALCULATION','text':f'Observed minus expected = {result["signed_gap"]}; relative change = {result["gap_pct"] or "not defined"}%. Correlation and attribution are not established.','references':[]}
    lower=q.casefold()
    if any(x in lower for x in ('draft','prefill','pre-fill','create initiative','generate initiative')):
        return {'kind':'DRAFT','text':'I can prepare an industry-specific local draft for your review. I cannot write to the Decision OS API, approve controls, or create observed metrics from assumptions.','references':[]}
    if any(x in lower for x in ('evaluate','evaluation','test','experiment','counterfactual','accuracy','precision','recall')):
        return {'kind':'GUIDANCE','text':f'{industry.name}: define an outcome contract, a comparison group or justified quasi-experiment, measurement window, technical/error-cost evaluation, fairness and safety tests, plus a predeclared stop condition. Typical confounders: {", ".join(industry.confounders)}. No causal estimate is currently available.','references':[]}
    if any(x in lower for x in ('evidence','missing','govern','risk','compliance','control')):
        return {'kind':'GUIDANCE','text':f'{industry.name} evidence to request: {"; ".join(industry.evidence)}. These are suggested requirements, not verified submissions. Review focus: {industry.review}.','references':[]}
    if any(x in lower for x in ('decision','record','portfolio','status')):
        ids=[str(d.get('id')) for d in (evidence or []) if d.get('id')]
        return {'kind':'RECORDS','text':f'{len(ids)} decision records were returned by the authorized API. This does not establish completeness, readiness or outcome success.','references':ids[:20]}
    return {'kind':'REFUSAL','text':'Insufficient verified evidence or unsupported query. I cannot invent a result, attribute causality, claim compliance, or assert a live industry benchmark. Try one of the suggested evidence or math questions.','references':[]}


def draft_industry_case(industry: Industry, decision_type: str, sponsor: str, objective: str, checks: dict[str,str]) -> dict:
    """Reviewable local artifact. Any future persistence requires authenticated backend contracts."""
    if decision_type not in industry.decisions: raise ValueError('Invalid decision type')
    if len(sponsor.strip())<2 or len(objective.strip())<15:
        raise ValueError('Specify accountable sponsor and meaningful objective (15+ characters).')
    return {'artifact_type':'LOCAL_INDUSTRY_DECISION_DRAFT','version':'1.0', 'industry':industry.name,
            'decision_type':decision_type,'business_sponsor':sponsor.strip(),'objective':objective.strip(),
            'candidate_kpis':list(industry.kpis), 'candidate_evidence_requests':list(industry.evidence),
            'possible_confounders':list(industry.confounders),
            'self_assessment':rubric_checks(industry,checks),
            'attribution':'UNKNOWN', 'observed_outcomes':None,'finance_verified':False,
            'decision_quality_score':None,'independent_approval':None,
            'status':'LOCAL_PREVIEW_NOT_SUBMITTED',
            'next_steps':['Verify all source evidence and ownership', 'Review assumptions and counterfactual',
                          'Submit through authenticated backend decision contract', 'Obtain independent human review'],
            'disclosure':'Illustrative template and user-provided draft inputs only; no API write or execution.'}


def _css():
    st.markdown('''<style>
    .ind-hero{background:linear-gradient(122deg,#0b1832,#153b61);border-radius:22px;padding:28px 32px;color:#fff;margin-bottom:1.25rem}
    .ind-hero h1{color:#fff;font-size:2rem;letter-spacing:-.035em;margin:0 0 8px}
    .ind-hero p{color:#e0ebf5;font-size:1.01rem;line-height:1.5;margin:0;max-width:1050px}
    .ind-kicker{font-size:.78rem;letter-spacing:.10em;color:#91c2ed;text-transform:uppercase;margin-bottom:12px}
    </style>''',unsafe_allow_html=True)


def render(api: Callable | None=None, navigate: Callable | None=None):
    _css()
    st.markdown('<div class="ind-hero"><div class="ind-kicker">CAIO · Enterprise Transformation</div><h1>Industry Intelligence</h1><p>'+VISION+'</p></div>',unsafe_allow_html=True)
    st.caption('12 reusable industry templates · Synthetic teaching scenarios · Authenticated decisions where available · No vendor telemetry implied')
    if 'industry_key' not in st.session_state: st.session_state['industry_key']='Enterprise IT'
    st.subheader('Choose your industry')
    names=list(INDUSTRIES)
    for start in (0,4,8):
        cols=st.columns(4)
        for col,name in zip(cols,names[start:start+4]):
            with col:
                if st.button(f'{INDUSTRIES[name].icon}  {name}',key='ind_'+name,use_container_width=True,
                             type='primary' if st.session_state['industry_key']==name else 'secondary'):
                    st.session_state['industry_key']=name
                    st.session_state.pop('ind_messages',None)
                    st.rerun()
    ind=INDUSTRIES[st.session_state['industry_key']]
    st.divider()
    st.subheader(f'{ind.icon}  {ind.name} | Transformation intelligence')
    records,warnings=load_authorized(api)
    if warnings: st.caption('Live portfolio unavailable: '+'; '.join(warnings))
    a,b,c=st.columns(3)
    a.metric('Industry-specific decisions',len(ind.decisions),help='Template types, not approved projects')
    b.metric('Candidate KPI definitions',len(ind.kpis),help='Definitions only; no observed performance')
    c.metric('Verified industry benchmarks','Unavailable')
    strategy,controls,copilot,simulation,draft=st.tabs(['Executive Scenario','Evidence & Evaluation','Decision Copilot','Scenario Laboratory','Draft & Pre-fill'])
    with strategy:
        c1,c2=st.columns([1,1])
        with c1:
            st.markdown('**Strategic decision patterns**')
            for item in ind.decisions: st.markdown('• '+item)
            st.markdown('**Industry KPI contracts**')
            for k in ind.kpis: st.markdown('• '+k)
        with c2:
            st.info(ind.scenario)
            st.markdown('**Potential confounders**')
            for item in ind.confounders: st.markdown('• '+item)
            st.warning('Attribution: UNKNOWN. This is a fictional teaching scenario, not a customer observation.')
        st.markdown('**Decision journey**')
        st.write('Define value → Collect source evidence → Compare alternatives → Evaluate technical and safety risk → Human approval → Observe outcomes → Learn')
        if navigate and st.button('Open Decision Operations',key='ind_ops'):
            navigate('Decision Operations')
    with controls:
        st.caption('Deterministic completeness audit—not a compliance certification or quality score.')
        control_names=('Business objective and baseline','Counterfactual or alternatives','Risk and affected-person impact','Outcome source and measurement plan','Named accountable reviewer','Explicit stop/review condition')
        checks={}
        for key in control_names:
            checks[key]=st.selectbox(key,['Not assessed','Documented · pending verification','Gap identified'],key='industry_control_'+key)
        audit=rubric_checks(ind,checks)
        st.metric('Self-reported controls documented',f'{audit["documented_count"]}/{audit["total"]}')
        if audit['not_documented']: st.warning('Open controls: '+', '.join(audit['not_documented']))
        st.markdown('**Suggested industry evidence**')
        for e in ind.evidence: st.markdown('• '+e)
        st.caption('All responses are local to the current Streamlit session. Independent verification and policy gating require the backend.')
    with copilot:
        st.markdown('#### Decision Copilot · Python Evidence Advisor')
        st.caption('Deterministic intent router and Decimal arithmetic. No external LLM, no hallucinated finance, no automatic database writes.')
        prompts=st.columns(3)
        for idx,prompt in enumerate(SAMPLE_PROMPTS[:3]):
            if prompts[idx].button(prompt,key=f'ind_prompt_{idx}'):
                st.session_state['ind_pending_question']=prompt
        if 'ind_messages' not in st.session_state: st.session_state['ind_messages']=[]
        for item in st.session_state['ind_messages'][-12:]:
            with st.chat_message(item['role']): st.markdown(item['text'])
        user_question=st.chat_input('Ask about evidence, evaluation, a business-value calculation, or a draft',key='ind_chat')
        pending=st.session_state.pop('ind_pending_question',None)
        question=user_question or pending
        if question:
            answer=decision_copilot_response(question,ind,records)
            st.session_state['ind_messages'].extend([{'role':'user','text':question},
                {'role':'assistant','text':answer['text'] + ('\n\nSource record IDs: '+', '.join(answer['references']) if answer['references'] else '')}])
            st.rerun()
        with st.expander('Optional local LangGraph + Ollama · proposal mode'):
            st.caption('Requires separately installed langgraph and a running local Ollama model. This experimental graph generates unverified planning suggestions only, never facts or actions.')
            agent_model=st.text_input('Local Ollama model tag',value='llama3.2:3b',key='ind_agent_model')
            agent_question=st.text_area('Planning request (avoid personal or confidential data)',value='Suggest a responsible evaluation plan and human review gates for this illustrative scenario.',key='ind_agent_question')
            if st.button('Generate unverified agentic plan',key='ind_graph_go'):
                try:
                    from ui.industry_agent import run_local_graph
                    result=run_local_graph(ind.name,ind.scenario,agent_question,agent_model)
                    st.session_state['ind_graph_proposal']=result
                except Exception as ex:
                    st.error(f'Optional local agent unavailable: {type(ex).__name__}: {ex}')
            if st.session_state.get('ind_graph_proposal'):
                result=st.session_state['ind_graph_proposal']
                st.warning(result['status'])
                st.markdown(result['proposal'])
                st.caption('No source verification, approval or database write has occurred. Do not execute model-generated steps without review.')
    with simulation:
        st.markdown('**Deterministic numerical outcome check**')
        expected=st.number_input('Expected KPI improvement (%)',min_value=-100.0,max_value=1000.0,value=20.0,key='ind_expected')
        observed=st.number_input('Observed KPI improvement (%) — manually supplied for simulation',min_value=-100.0,max_value=1000.0,value=15.0,key='ind_observed')
        gap=calculate_gap(expected,observed)
        st.metric('Observed − expected (percentage points)',f'{float(gap["signed_gap"]):+.2f}')
        st.caption('This calculation is deterministic. Input values are manually supplied, not verified telemetry. No causal inference is performed.')
        st.markdown('**Non-deterministic evaluation: seeded Monte Carlo scenario**')
        lo,mid,hi=st.columns(3)
        minimum=lo.number_input('Minimum plausible gain',value=2.0,key='ind_min')
        likely=mid.number_input('Most likely gain',value=8.0,key='ind_likely')
        maximum=hi.number_input('Maximum plausible gain',value=15.0,key='ind_max')
        if st.button('Simulate illustrative outcomes',key='ind_sim'):
            try:
                result=monte_carlo_scenario(0,minimum,likely,maximum)
                st.session_state['ind_sim_result']=result
            except ValueError as ex: st.error(str(ex))
        if 'ind_sim_result' in st.session_state:
            res=st.session_state['ind_sim_result']
            c1,c2,c3=st.columns(3)
            c1.metric('P10 (scenario)',res['p10']);c2.metric('P50 (scenario)',res['p50']);c3.metric('P90 (scenario)',res['p90'])
            st.caption(res['disclaimer']+f' · Reproducible seed {res["seed"]}; {res["runs"]} draws')
    with draft:
        st.markdown('**Industry-guided draft & pre-fill**')
        st.caption('Pre-fill is a local JSON artifact for human review—not an authenticated API creation, verified evidence, or an executed action.')
        decision_type=st.selectbox('Decision type',ind.decisions,key='ind_case_decision')
        sponsor=st.text_input('Accountable human sponsor',placeholder='e.g. VP Manufacturing',key='ind_sponsor')
        objective=st.text_area('Business objective and scope',placeholder='Describe the problem and measurable outcome, without asserting a result.',key='ind_objective')
        if st.button('Generate reviewed draft',key='ind_generate',type='primary'):
            try:
                data=draft_industry_case(ind,decision_type,sponsor,objective,
                      {k:st.session_state.get('industry_control_'+k,'Not assessed') for k in ('Business objective and baseline','Counterfactual or alternatives','Risk and affected-person impact','Outcome source and measurement plan','Named accountable reviewer','Explicit stop/review condition')})
                st.session_state['ind_draft']=data
            except ValueError as ex: st.error(str(ex))
        d=st.session_state.get('ind_draft')
        if d and d.get('industry')==ind.name:
            st.json(d)
            st.download_button('Download JSON draft for governance review',json.dumps(d,indent=2),file_name='decision_os_industry_draft.json',mime='application/json',key='ind_export')
            st.warning('This draft is NOT SUBMITTED, NOT APPROVED, and NOT EXECUTABLE. Any future auto-fill into database forms requires explicit user confirmation and authenticated API validation.')
    st.caption('Industry templates are original product examples; not verified benchmarks or substitute regulatory advice. All live records are constrained by the connected API identity.')

if __name__=='__main__':
    st.set_page_config(page_title='Decision OS | Industry Intelligence',layout='wide')
    render()
