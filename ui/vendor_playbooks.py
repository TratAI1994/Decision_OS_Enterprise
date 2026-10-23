"""Decision OS vendor-inspired executive guidance (original content, read-only).

These are educational readiness checklists, NOT cloud-provider certifications.
No secrets, local databases, or external writes. No outcomes are inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

import streamlit as st


@dataclass(frozen=True)
class Gate:
    key: str
    stage: str
    question: str
    why: str
    evidence: str
    severity: str = 'required'

CONTENT = {
    'Microsoft Transformation': {
        'strap':'STRATEGY · RESPONSIBILITY · ADOPTION',
        'headline':'Make AI transformation accountable to business outcomes.',
        'summary':'Work from business objective to accountable deployment, responsible AI controls, adoption evidence and realized value.',
        'phases':['Business value','Responsible design','Secure delivery','Adoption','Outcome review'],
        'reference':[('Microsoft AI Adoption','https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ai/strategy'),('Microsoft Responsible AI','https://www.microsoft.com/en-us/ai/responsible-ai')],
        'gates':[
            Gate('m1','Business value','Is the business problem linked to a baseline and measurable target?','Value must be evaluated independently of software delivery.','Approved problem statement, baseline and target'),
            Gate('m2','Business value','Is there a named sponsor accountable for outcome realization?','An accountable executive must own the decision.','Sponsor identity, outcome owner and review date'),
            Gate('m3','Responsible design','Has a context-specific human/stakeholder impact assessment been reviewed?','Potential harm requires explicit evidence and independent oversight.','Impact assessment and reviewer record'),
            Gate('m4','Responsible design','Are privacy, fairness, safety and transparency concerns assessed?','Principles must produce concrete controls.','Data classification, risk assessment and mitigations'),
            Gate('m5','Secure delivery','Are least privilege and security release checks documented?','A viable model is not equivalent to a safe deployment.','Threat model, access policy, test results'),
            Gate('m6','Adoption','Is successful use measured beyond licenses activated?','Usage is not business value.','Usage cohort, task-success baseline, training plan'),
            Gate('m7','Outcome review','Is value compared against actual observations and attribution limitations?','Observed improvement does not establish causal impact.','Outcome contract, observation and attribution review'),
        ],
    },
    'AWS Operational Readiness': {
        'strap':'DESIGN · DEVELOP · DEPLOY · OPERATE',
        'headline':'Turn responsible AI into operational release evidence.',
        'summary':'An operational review inspired by AWS Well-Architected and Responsible AI guidance, separating provider controls from enterprise responsibilities.',
        'phases':['Design','Develop','Deploy','Operate'],
        'reference':[('AWS Responsible AI Lens','https://docs.aws.amazon.com/wellarchitected/latest/responsible-ai-lens/responsible-ai-lens.html'),('AWS Responsible AI','https://aws.amazon.com/ai/responsible-ai/')],
        'gates':[
            Gate('a1','Design','Is the use case narrowly scoped, with prohibited uses stated?','Ambiguous scopes create untestable performance and safety promises.','Intended-use and limitations card'),
            Gate('a2','Design','Is shared responsibility mapped for provider and enterprise?','Managed platforms do not own customer decisions, data rights or approvals.','RACI / responsibility assignment matrix'),
            Gate('a3','Design','Are data classification, threat model and failure modes captured?','Risk assessment must cover the whole architecture.','Data inventory and threat analysis'),
            Gate('a4','Develop','Are model/application evaluations documented on representative inputs?','Benchmark scores alone do not establish workload suitability.','Evaluation dataset, error analysis, versioned tests'),
            Gate('a5','Develop','Are guardrails and abuse cases adversarially tested?','Configured guards can fail and must be measured.','Prompt-injection, misuse and leakage test report'),
            Gate('a6','Deploy','Are release gates, rollback and human sign-off evidenced?','Deployment requires a bounded go/no-go decision.','Release checklist, approval record, rollback runbook'),
            Gate('a7','Operate','Are monitoring, drift, incidents, cost and retest ownership defined?','A one-time gate is insufficient after real usage begins.','Observability plan, alarms, on-call ownership'),
        ],
    },
    'Google Evaluation & Safety': {
        'strap':'EVALUATE · SECURE · EXPERIMENT · LEARN',
        'headline':'Demand evidence that the AI system works—and stays safe.',
        'summary':'An evaluation-first operating pattern drawing on Google AI Principles and Secure AI Framework (SAIF).',
        'phases':['Frame','Evaluate','Secure AI','Experiment','Learn'],
        'reference':[('Google SAIF','https://www.saif.google/secure-ai-framework'),('Google AI Principles','https://ai.google/principles/'),('Google ML Crash Course','https://developers.google.com/machine-learning/crash-course')],
        'gates':[
            Gate('g1','Frame','Are expected benefit, failure costs and alternative non-AI options defined?','Evaluation begins with a decision criterion, not a model benchmark.','Baseline, alternatives and error-cost model'),
            Gate('g2','Evaluate','Are evaluation metrics, slices and acceptance thresholds predeclared?','A score is meaningful only against explicit success criteria.','Versioned evaluation plan'),
            Gate('g3','Evaluate','Have held-out and out-of-distribution inputs been tested?','Production conditions differ from development samples.','Robustness and distribution-shift results'),
            Gate('g4','Secure AI','Have data, model, app and infrastructure SAIF threats been assessed?','Prompt injection and data poisoning require defense in depth.','SAIF risk-to-control mapping'),
            Gate('g5','Secure AI','Have red-team findings been reviewed and retested after mitigation?','A vulnerability fix is not verified until retested.','Finding IDs, remediations and retest evidence'),
            Gate('g6','Experiment','Is business attribution supported by a defensible comparison method?','Before/after correlation must not be presented as causality.','Randomized or quasi-experimental protocol, limitations'),
            Gate('g7','Learn','Are rollback triggers, feedback loops and assumption revalidation defined?','Safe performance needs ongoing evaluation after deployment.','Drift criteria, incident signals, learning review'),
        ],
    }
}
STATUSES=('Not assessed','Evidence available · awaiting review','Gap identified','Reviewed · evidence sufficient')

def summarize(gates, statuses):
    """Pure score: evaluated coverage, NOT compliance or real-world evidence verification."""
    results=[statuses.get(g.key,'Not assessed') for g in gates]
    reviewed=sum(s=='Reviewed · evidence sufficient' for s in results)
    gaps=sum(s=='Gap identified' for s in results)
    awaiting=sum(s=='Evidence available · awaiting review' for s in results)
    return {'reviewed':reviewed,'gaps':gaps,'awaiting':awaiting,'unknown':len(results)-reviewed-gaps-awaiting,'total':len(gates)}

def build_brief(title, gates, statuses, record, context):
    counts=summarize(gates,statuses)
    lines=[f'# Decision OS — {title}',f'Generated UTC: {datetime.now(UTC).isoformat(timespec="seconds")}',
      'Status: SELF-ASSESSED DRAFT; not an independent verification, certification or authorization.',
      f'Initiative: {record or "Not specified"}',f'Business decision: {context or "Not specified"}',
      f'Reviewed (self-reported): {counts["reviewed"]}/{counts["total"]}; gaps: {counts["gaps"]}; unassessed: {counts["unknown"]}',
      '', '## Evidence and decision gates']
    for gate in gates:
        lines += [f'### {gate.stage} · {gate.question}',f'Status: {statuses.get(gate.key,"Not assessed")}',f'Why: {gate.why}',f'Expected evidence: {gate.evidence}','']
    lines += ['## Decision integrity', 'No approval, risk classification, observation or evidence verification is implied.',
      'Every item requires authorized source linking, independent review and current policy evaluation in the backend.',
      '## Next action','Assign a responsible evidence owner and bring the outstanding controls to the existing Decision Action Center.']
    return '\n'.join(lines)

def _card(text, subtitle='', accent='#3b82f6'):
    st.markdown(f'<div style="background:#fff;border:1px solid #e1e8f2;border-left:4px solid {accent};border-radius:13px;padding:17px 20px;margin:8px 0;box-shadow:0 3px 14px #10244609;color:#14233b"><div style="font-weight:750;font-size:15px">{escape(text)}</div><div style="font-size:12px;color:#63738d;margin-top:5px">{escape(subtitle)}</div></div>',unsafe_allow_html=True)

def render_vendor_playbook(page, api=None, nav=None):
    cfg=CONTENT[page]
    st.markdown('''<style>
       .vendorhero{background:linear-gradient(115deg,#0a1830,#12365a 70%,#176d75);padding:30px 32px;border-radius:21px;color:white;margin-bottom:18px;box-shadow:0 16px 34px #0c234020}
       .vendorhero small{color:#95dce7;letter-spacing:.12em;font-weight:750}.vendorhero h1{color:white!important;font-size:31px;margin:.4rem 0;line-height:1.12}.vendorhero p{color:#d1e1f3;font-size:14px;max-width:740px}
       .vendor-step{background:#eef3fa;border-radius:10px;padding:12px 6px;text-align:center;font-size:12px;font-weight:650;color:#243d5b;border:1px solid #dfe7f1}
       </style>''',unsafe_allow_html=True)
    st.markdown(f'<div class="vendorhero"><small>DECISION OS · {escape(cfg["strap"])}</small><h1>{escape(page)}</h1><p>{escape(cfg["headline"])}</p><p>{escape(cfg["summary"])}</p></div>',unsafe_allow_html=True)
    st.caption('Original, vendor-inspired operational guidance. Not Microsoft, AWS, or Google software, endorsement, certification or a compliance determination.')
    steps=st.columns(len(cfg['phases']))
    for col,phase in zip(steps,cfg['phases']):
        with col:st.markdown(f'<div class="vendor-step">{escape(phase)}</div>',unsafe_allow_html=True)
    st.write('')
    # Existing API is optional; never silently imply that a typed name is linked to a real decision.
    initiative_name=''; selection=None
    if api:
        initiatives=api('GET','/v1/initiatives',quiet=True) or []
        if isinstance(initiatives,list) and initiatives:
            selection=st.selectbox('Use an existing authorized initiative', [None]+initiatives,
                format_func=lambda x:'Not linked · guidance only' if x is None else str(x.get('name','Untitled')),key='vp_initiative_'+page)
            initiative_name=selection.get('name','') if selection else ''
    decision_context=st.text_input('Decision under consideration',placeholder='Example: Should we expand the AI claims pilot?',key='vp_context_'+page)
    gates=cfg['gates']
    st.markdown('#### Readiness · evidence, not checkboxes')
    st.caption('Self-assess readiness. “Reviewed” is an unverified user declaration in this page. No value is persisted, and release approval still requires backend review.')
    statuses={}
    for stage in cfg['phases']:
        group=[g for g in gates if g.stage==stage]
        if not group:continue
        st.markdown(f'**{stage}**')
        for gate in group:
            with st.container(border=True):
                left,right=st.columns([3,2],gap='large')
                with left:
                    st.markdown(f'**{gate.question}**')
                    st.caption(gate.why)
                    st.markdown(f'<span style="font-size:12px;color:#395d89"><b>Required artifact:</b> {escape(gate.evidence)}</span>',unsafe_allow_html=True)
                with right:
                    statuses[gate.key]=st.selectbox('Evidence status',STATUSES,key='vp_'+page+'_'+gate.key)
    counts=summarize(gates,statuses)
    st.markdown('#### Executive readiness summary')
    a,b,c,d=st.columns(4)
    a.metric('Reviewed · self-reported',f'{counts["reviewed"]}/{counts["total"]}')
    b.metric('Gaps',counts['gaps'])
    c.metric('Awaiting review',counts['awaiting'])
    d.metric('Not assessed',counts['unknown'])
    if counts['gaps'] or counts['unknown'] or counts['awaiting']:
        st.warning('Decision readiness is incomplete. No policy approval or certification has been issued.')
    else:
        st.info('All items are marked reviewed by the user. Independent review and backend policy evaluation are still required.')
    with st.expander('What would change a decision?',expanded=False):
        st.write('Treat a missing business baseline, required security clearance, material safety finding, or unverified outcome as a reason to request more evidence—not as an automatic approval.')
        st.write('Economic claims are forecasts until reconciled; improvements are correlated until a defensible attribution analysis supports stronger conclusions.')
    memo=build_brief(page,gates,statuses,initiative_name,decision_context)
    st.download_button('Download readiness decision card',memo,file_name='decision-os-'+page.lower().replace(' ','-')+'.md',mime='text/markdown',key='vp_dl_'+page,type='primary')
    st.caption('Export contains only the explicit current-page self-assessment and selected initiative title; it does not include personal data or API secrets.')
    st.markdown('#### Learn the original framework')
    for label,url in cfg['reference']:
        st.markdown(f'- [{label}]({url})')
    if nav and st.button('Open governed Action Center',key='vp_open_action_'+page):nav('Decision Action Center')
