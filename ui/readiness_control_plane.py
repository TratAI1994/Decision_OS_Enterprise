"""Guided dark-console UI for authenticated readiness evidence, never execution.
Requires backend.readiness_engine accessible to the UI image.
"""
from __future__ import annotations
import json
from typing import Callable
import streamlit as st
from backend.readiness_engine import CONTROLS, evaluate, from_trust_response, sample_manifest

QUESTIONS = {
 'identity': ('How is tenant isolation established?', 'What should the identity test prove?'),
 'approval': ('What is an atomic approval snapshot?', 'Does R9.5 attest funding approval?'),
 'ci': ('What proof is needed from Jenkins?', 'Do skipped security scans count as passes?'),
 'finance': ('What separates attested from ERP-verified?', 'Can we claim AI caused a saving?'),
 'anchoring': ('Does SHA-256 establish immutability?', 'How do signatures work?'),
}

def answer_question(q: str, control: str) -> str:
    q = q.strip().lower()
    if any(x in q for x in ('hash', 'signature','immutab','anchor')):
        return 'A local SHA-256 digest detects changes only relative to a trusted reference. Independent signature verification and separately held anchors are additional controls. No anchor is inferred.'
    if any(x in q for x in ('finance','saving','caus','erp','gl')):
        return 'Finance attestation requires an independent authorized actor and source references; reconciliation and causal attribution require separate evidence. A plan variance is not proof of AI causation.'
    if any(x in q for x in ('test','scan','jenkins','pipeline','skip')):
        return 'CI evidence must include the run identifier, commit, scanner outcomes and pass/fail status. A missing or skipped mandatory scan is NOT_TESTED, not PASS.'
    if any(x in q for x in ('approval', 'atomic','funding')):
        return 'The authoritative business approval, policy version and evidence bytes must be captured in one transaction. R9.5 freezes independently attested evaluation assertions, not funding approvals.'
    return f'For {control}, inspect the source event, authenticated reviewer, evidence reference, and completion criterion. This screen cannot certify external systems.'


def render(api: Callable | None = None) -> None:
    st.markdown('''<style>
    .readiness-hero{background:#091426;color:#f4f8ff;border:1px solid #263957;border-radius:16px;padding:1.5rem 1.8rem;margin-bottom:1rem}
    .readiness-hero h2{color:#fff;margin:.3rem 0;font-size:1.8rem}
    .readiness-hero p{color:#b6c7e0;margin:0}
    </style>''', unsafe_allow_html=True)
    st.markdown('<div class="readiness-hero"><small>DECISION OS / TRUST CONTROL PLANE</small><h2>Production Proof</h2><p>13 independent gates. No fictional PASS results. Every missing control stays visible.</p></div>',unsafe_allow_html=True)
    did = st.text_input('Decision ID', placeholder='Use an accessible R7 decision ID',key='proof_did')
    if not did.strip():
        st.info('Enter a decision ID to inspect its R9.5 certification evidence. This screen does not grant approvals.')
        return
    if 'proof_report' not in st.session_state or st.session_state.get('proof_cached_did') != did.strip():
        st.session_state['proof_report']=None
        st.session_state['proof_cached_did']=did.strip()
    a,b=st.columns([2,1])
    with a:
        if st.button('Inspect authenticated Trust Foundation',type='primary'):
            if api is None:
                st.warning('No authenticated API adapter. No server evidence was loaded.')
            else:
                try:
                    raw=api('GET',f'/v1/trust-foundation/{did.strip()}/certification')
                    if not isinstance(raw,dict) or raw.get('error'):
                        st.error('Trust service returned no valid response.')
                    else:
                        candidate=from_trust_response(raw)
                        st.session_state['proof_report']=evaluate(candidate)
                except Exception:
                    st.error('Unable to load Trust Foundation evidence. Check connectivity and access rights.')
        report=st.session_state.get('proof_report')
        if report is None:
            st.warning('NOT CERTIFIED — No service evidence loaded')
            report=evaluate(sample_manifest(did.strip()))
        elif report['certified']:
            st.success('All supplied gates pass authenticated checks; external proof validation still required.')
        else:
            st.error('NOT PRODUCTION CERTIFIED')
        st.metric('Passed controls',f"{report['summary']['PASS']} / {len(CONTROLS)}")
        st.dataframe([{'Gate':f['title'],'Result':f['status'],'Why':f['reason']} for f in report['findings']],hide_index=True,use_container_width=True)
        st.download_button('Export audit-ready assessment (advisory)',json.dumps(report,indent=2),file_name='readiness_report.json',mime='application/json')
        with st.expander('High-level architecture and evidence contracts'):
            st.graphviz_chart('''digraph G { rankdir=LR; bgcolor="transparent"; node [shape=box style="rounded,filled" fillcolor="#10223b" fontcolor="white" color="#508cd5"]; Decision -> Approval -> CI -> Deploy -> Observe -> Finance -> Intervention -> Replay; }''',use_container_width=True)
            st.caption('Dependency sequence, not proof that any stage completed.')
    with b:
        st.subheader('Screen Guide')
        choices=[x[0] for x in CONTROLS]
        control=st.selectbox('Help for specific control',choices,format_func=lambda v:dict(CONTROLS)[v])
        for q in QUESTIONS.get(control,('What evidence is required?', 'Why is this not yet certified?')):
            if st.button(q,key='ask_'+str(choices.index(control))+'_'+str(q)):
                st.session_state['proof_question']=q
        q=st.text_area('Ask the Trust Copilot',key='proof_question',height=92)
        if st.button('Explain this control'):
            st.info(answer_question(q,control))
        st.caption('Deterministic, feature-specific guidance. This assistant cannot amend approval records or execute actions.')
