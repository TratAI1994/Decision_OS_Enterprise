"""Decision Academy: original, offline, read-only, microlearning addon for Decision OS.
No network calls, no credentials, no side effects. Streamlit is imported only during render.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import NamedTuple


@dataclass(frozen=True)
class Lesson:
    slug: str
    title: str
    principle: str
    beginner: str
    executive: str
    practice: str
    scenario: str
    alternatives: tuple[str, ...]
    correct: int
    explanation: str
    next_step: str
    source: str
    source_url: str
    framework: str

LESSONS = (
    Lesson('strategy', 'AI leadership & value', 'Strategy before technology',
        'An AI project is a bet: which problem, for whom, what measurable improvement, and at what cost?',
        'Demand a named sponsor, baseline, measurable outcome, competing alternatives, adoption plan and stop rule.',
        'Map one business problem to an outcome contract, funding decision, owner and review date.',
        'A claims leader requests an AI assistant. There is no baseline for claims-handling time. What should happen first?',
        ('Buy an LLM subscription and begin rollout', 'Measure handling-time baseline and define an outcome contract', 'Declare a 20% productivity gain'), 1,
        'Without a measured baseline, even a successful deployment cannot establish whether the business improved.',
        'Open Strategy & Outcomes R5.5; create a Focus Area, an Objective and a Key Result with baseline and target.',
        'ISB Online — Leadership with AI', 'https://online-em.isb.edu/leadership-with-ai',
        'AI leadership, operating models, business transformation, GenAI and responsible AI'),
    Lesson('ml', 'Machine learning in plain language', 'Choose the right model and metric',
        'Prediction models learn statistical patterns. Accuracy alone can be misleading when the mistakes have different costs.',
        'Ask about training data, leakage, distribution shift, false positives, false negatives and the financial cost of errors.',
        'Compare two risk thresholds with a confusion matrix and a business-value estimate.',
        'A fraud model flags 95% of transactions as legitimate. Fraud is rare. Which evaluation is best?',
        ('Report accuracy alone', 'Report precision, recall, false-positive cost and false-negative cost', 'Ignore the model and deploy automatically'), 1,
        'Imbalanced classes can create deceptively high accuracy. Choose thresholds using consequences, not presentation quality.',
        'Define test datasets, error-cost assumptions and measurement owner before the model decision is approved.',
        'Google — Machine Learning Crash Course', 'https://developers.google.com/machine-learning/crash-course',
        'Classification, datasets, overfitting, LLMs, production ML and fairness'),
    Lesson('microsoft', 'Enterprise AI adoption & execution', 'Adoption is an outcome, not a license count',
        'Successful AI deployment needs workflow fit, real user adoption, role-based support and a way to measure value.',
        'Separate licenses assigned, users activated, successful tasks, time saved and independently verified business outcomes.',
        'Write an AI adoption scorecard for one workstream with a baseline and a thirty-day review.',
        '500 AI seats were purchased, but only 80 people use the workflow. What should the review recommend?',
        ('Buy 500 additional seats', 'Diagnose friction and measure completed tasks before expanding', 'Mark the investment as fully adopted'), 1,
        'Licensing is an input. Activation, workflow success and value realized require their own observations.',
        'Use Copilot Transformation Office and Outcome Contracts; mark all unverified benefits as self-reported.',
        'Microsoft Learn — Transform your business with AI', 'https://learn.microsoft.com/en-us/training/paths/transform-your-business-with-microsoft-ai',
        'Business value, responsible AI governance, adoption, change and scaling'),
    Lesson('nist', 'NIST AI risk management', 'Govern → Map → Measure → Manage',
        'Set responsibilities; understand the context; evaluate risks; and manage the results with evidence.',
        'Require purpose, system boundary, owner, harm scenarios, risk evidence, human oversight and explicit residual-risk review.',
        'Build a control-and-evidence map for an AI claims decision-support application.',
        'An AI triage agent can recommend denial of a customer claim. What is the best next step?',
        ('Treat all denials as fully automated', 'Map affected people and harms, test controls, and require appropriate oversight', 'Rely on a generic responsible-AI checkbox'), 1,
        'NIST AI RMF organizes contextual risk management around Govern, Map, Measure and Manage; it is voluntary guidance, not certification.',
        'Open AI Risk & Regulatory Office; link contextual risks and evidence to a governed decision.',
        'NIST — AI Risk Management Framework & Playbook', 'https://airc.nist.gov/airmf-resources/playbook/',
        'Govern, Map, Measure, Manage; context-specific AI risk management'),
    Lesson('oecd', 'Human-centered AI principles', 'People, transparency, robustness and accountability',
        'An AI system should benefit people, respect rights, explain meaningful behavior, remain resilient and have accountable owners.',
        'Test stakeholder impact, human override, user explanation, incident response and who is accountable for adverse outcomes.',
        'Create a one-page responsible-AI assessment aligned to the OECD values-based principles.',
        'A ranking model disadvantages a particular customer group. The team says performance is strong overall. What now?',
        ('Ignore subgroup effects', 'Investigate fairness, explainability, affected people and remediation ownership', 'Disable all monitoring'), 1,
        'Overall performance can hide uneven harms. OECD principles cover inclusive growth, rights/fairness/privacy, transparency, robustness/security and accountability.',
        'Document stakeholders, explanation needs, controls and residual risk; escalate significant harms for human review.',
        'OECD — AI Principles (updated 2024)', 'https://oecd.ai/en/ai-principles',
        'Inclusive well-being, rights/fairness/privacy, transparency, robustness and accountability'),
)

CASE_STUDIES = {
    'Claims Triage Copilot': {
        'problem': 'High manual triage effort and unpredictable claims turnaround',
        'baseline': 'Unknown until measured; do not invent',
        'hypothesis': 'Assisted triage could reduce median handling time without worsening errors or fairness',
        'experiment': 'Shadow-mode pilot; predeclare median handling time, error rate, subgroup fairness, human override and sample size',
        'guardrail': 'Human final decision; privacy controls; audit log; red-team adversarial inputs',
        'outcome': 'Compare actual against target with attribution limits; continue, iterate or stop',
        'risk': 'Wrongful denial, bias, overreliance, PII leakage',
    },
    'Retail Fulfillment Promise': {
        'problem': 'Delivery promise accuracy trades off against cost-to-serve',
        'baseline': 'Observed promise misses, split rate, shipping costs; unknown until measured',
        'hypothesis': 'Optimization can lower total cost while maintaining the service commitment',
        'experiment': 'Shadow recommendations against baseline with route/capacity constraints; measure late deliveries and cost',
        'guardrail': 'Deterministic feasibility, inventory checks and approval for policy overrides',
        'outcome': 'Compare expected savings and measured outcomes; avoid causal claims without controlled comparisons',
        'risk': 'Stockouts, biased service levels, capacity exceptions',
    },
    'Enterprise Knowledge Assistant': {
        'problem': 'Knowledge discovery is slow and inconsistent across teams',
        'baseline': 'Task-completion time and retrieval accuracy; measure before pilot',
        'hypothesis': 'Permission-aware retrieval can improve task success with citations',
        'experiment': 'Blind evaluation set, permission tests, prompt injection tests and human assessment',
        'guardrail': 'Tenant scope, prompt injection defense, no unauthorized content in generated answers',
        'outcome': 'Measure task success, groundedness, adoption and answer refusal quality',
        'risk': 'Hallucinated citations, confidential-data exposure, incorrect advice',
    },
}

ROLE_PATHS = {
    'CEO / Chief Innovation Officer': ('strategy','microsoft','nist','oecd','ml'),
    'Principal Product Manager': ('strategy','ml','microsoft','oecd','nist'),
    'CTO / AI Architect': ('ml','nist','oecd','microsoft','strategy'),
    'CISO / AI Risk Officer': ('nist','oecd','ml','microsoft','strategy'),
    'Transformation / Program Leader': ('strategy','microsoft','oecd','nist','ml'),
}

class Review(NamedTuple):
    facts: str
    assumptions: str
    controls: str
    next_decision: str

def framework_review(case: dict) -> Review:
    """Deterministic teaching scaffold; not an organizational approval or factual observation."""
    return Review('Problem: '+case['problem']+' | Baseline: '+case['baseline'],
                  case['hypothesis'], case['guardrail'], case['outcome'])

def skill_check(answer: int, correct: int) -> bool:
    return int(answer) == int(correct)

def playbook_markdown(role: str, case_name: str) -> str:
    c = CASE_STUDIES[case_name]
    lines = ['# Decision Academy — Implementation Playbook', '',
             '**Original teaching scaffold; not a verified business case or regulatory certification.**',
             '', f'Persona: {role}', f'Illustrative case: {case_name}', '',
             '## Governed decision canvas',
             f'- Problem: {c["problem"]}', f'- Baseline: {c["baseline"]}',
             f'- Hypothesis: {c["hypothesis"]}', f'- Experiment: {c["experiment"]}',
             f'- Safety and oversight: {c["guardrail"]}', f'- Risks: {c["risk"]}',
             f'- Outcome and next decision: {c["outcome"]}', '',
             '## Launch readiness questions',
             '- Who is the business sponsor and independent risk reviewer?',
             '- Are baseline, target, source, measurement owner and observation period defined?',
             '- What alternatives were considered, and what is the no-go criterion?',
             '- Are intended use, privacy, fairness, security, performance and human review addressed?',
             '- What evidence and policy versions were in force at approval?',
             '- Are observed outcomes distinguished from modeled and self-reported estimates?',
             '', '## Primary source catalogue']
    lines += [f'- [{l.source}]({l.source_url}) — {l.framework}' for l in LESSONS]
    return '\n'.join(lines)+'\n'

def render_decision_academy():
    import streamlit as st
    st.markdown('''<style>
    .academy-hero{background:linear-gradient(115deg,#101c37,#16476a 70%,#126c71);color:#fff;padding:25px 28px;border-radius:20px;margin:8px 0 22px}
    .academy-hero h1{color:#fff;font-size:29px;margin:5px 0}.academy-hero p{color:#d4eaff;margin-bottom:0}
    .academy-node{background:#fff;border:1px solid #dae3ef;border-left:5px solid #4278ce;border-radius:13px;padding:13px 16px;color:#19304d;min-height:65px}
    .academy-arrow{text-align:center;color:#71849c;font-size:18px;margin:3px 0}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="academy-hero"><div style="font-size:12px;letter-spacing:.16em">DECISION OS / ENABLEMENT</div><h1>Decision Academy</h1><p>Learn only what your decision needs. Understand → Simulate → Apply → Review.</p></div>',unsafe_allow_html=True)
    st.info('Educational add-on. Scenarios are fictional. This screen does not write decisions, evaluate regulatory compliance or calculate verified business savings.')
    role=st.selectbox('Choose your role',list(ROLE_PATHS),key='academy_role')
    case_name=st.selectbox('Choose a practical case',list(CASE_STUDIES),key='academy_case')
    tabs=st.tabs(['Visual map','Microlearning','Case simulation','Apply at work','Sources'])
    with tabs[0]:
        st.subheader('The complete decision journey')
        for label,description in [
            ('1. Define value','Strategy, customer job, business case, economics'),
            ('2. Choose an AI approach','ML suitability, data quality, model evaluation'),
            ('3. Govern responsibly','NIST risk mapping and OECD values'),
            ('4. Pilot in the workflow','Adoption, human oversight, predeclared experiments'),
            ('5. Observe actual outcomes','Freshness, provenance, attribution, realized value'),
            ('6. Learn and decide again','Decision Replay, assumptions and next investment')]:
            st.markdown('<div class="academy-node"><strong>'+escape(label)+'</strong><div>'+escape(description)+'</div></div>',unsafe_allow_html=True)
            if not label.startswith('6.'):st.markdown('<div class="academy-arrow">↓</div>',unsafe_allow_html=True)
        st.caption('This map is an original synthesis of the referenced sources, not any provider’s course diagram.')
    with tabs[1]:
        st.subheader('Role-based pathway')
        slug=st.selectbox('Select one concept',ROLE_PATHS[role],format_func=lambda k:next(x.title for x in LESSONS if x.slug==k),key='academy_lesson')
        l=next(x for x in LESSONS if x.slug==slug)
        a,b=st.columns(2)
        with a:
            st.markdown('**Explain it in 30 seconds**');st.write(l.beginner)
            st.markdown('**Executive decision rule**');st.write(l.executive)
        with b:
            st.markdown('**Practice**');st.write(l.practice)
            st.markdown('**Apply in Decision OS**');st.write(l.next_step)
        with st.expander('Check your understanding',expanded=True):
            st.write(l.scenario)
            answer=st.radio('Choose the best action',range(len(l.alternatives)),format_func=lambda n:l.alternatives[n],key='quiz_'+slug,index=None)
            if st.button('Check reasoning',key='check_'+slug):
                if answer is None:st.warning('Select an answer first.')
                elif skill_check(answer,l.correct):st.success('Correct — '+l.explanation)
                else:st.warning('Not quite. '+l.explanation)
        st.caption(l.framework)
    with tabs[2]:
        case=CASE_STUDIES[case_name];rev=framework_review(case)
        st.subheader(case_name+' — Decision simulation')
        for heading,value in [('Customer / business problem',rev.facts),('Hypothesis to test',rev.assumptions),('Risks and safeguards',case['risk']+' | '+rev.controls),('Experiment',case['experiment']),('Outcome review',rev.next_decision)]:
            with st.expander(heading,expanded=heading=='Customer / business problem'):
                st.write(value)
        st.warning('Not a live scenario. All observations, confidence and claimed benefits remain unverified until real measurements are linked.')
    with tabs[3]:
        st.subheader('Convert the lesson into an implementation plan')
        st.download_button('Export practical implementation playbook',playbook_markdown(role,case_name),file_name='decision_academy_playbook.md',mime='text/markdown',key='academy_download')
        st.markdown('**Use the existing Decision OS modules to execute it:**')
        st.markdown('1. **Strategy & Outcomes R5.5:** Declare objective, KR, measurement and assumptions.\n2. **Executive Decision Ledger:** Record alternatives and funding rationale.\n3. **AI Risk & Regulatory Office:** Assess context, evidence and accountable reviewers.\n4. **Enterprise Transformation Execution:** Track governed work, not outcome claims.\n5. **Strategy-to-Outcomes Review:** Compare observed versus expected results.')
    with tabs[4]:
        st.subheader('Official original references')
        for l in LESSONS:
            st.markdown(f'**{l.source}** — [{l.source_url}]({l.source_url})')
            st.caption(l.framework)
        st.caption('Independent original educational synthesis. No ISB/Google/Microsoft/NIST/OECD affiliation, approval, accreditation or certification is implied.')
