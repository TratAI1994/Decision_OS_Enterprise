"""Trust & Audit Console: guided review, never a substitute for server enforcement."""
from __future__ import annotations
import json
import secrets
from typing import Callable
import streamlit as st

STEPS=('Review recorded decision','Verify event history','Freeze reviewed evaluation','Monitor approved thresholds','Readiness certification')
QUESTIONS={
 0:['What must be present before approval?','Is an evaluation approval the same as deployment approval?'],
 1:['How is tampering detected?','What does a hash chain prove?'],
 2:['Who is authorized to freeze this version?','What does an unsigned snapshot mean?'],
 3:['Will a breached threshold stop production?','Why does the evaluation window matter?'],
 4:['Why is the certification not passing?','What evidence is needed for production readiness?'],
}
def guidance(q:str,step:int)->str:
    q=q.lower()
    if any(v in q for v in ('sign','hash','tamper','immutable')):
        return ('R7 hashes detect local chain inconsistency. R9.5 also hashes the frozen snapshot and optionally verifies an Ed25519 signature using a separately configured public key. '
                'This does not establish externally anchored immutable storage or identity-bound funding approval.')
    if any(v in q for v in ('threshold','window','stop','kill')):
        return ('A single submitted metric breach is only a review candidate. The system cannot enforce a sustained time window or halt production until authenticated telemetry, scheduled evaluation, '
                'policy hooks, and human-authorized stop actions have been integrated.')
    if any(v in q for v in ('who','review','approv','freeze')):
        return ('A separate reviewer/risk/admin identity may freeze an independently attested evaluation version. The author and decision owner cannot self-attest. '
                'This is NOT equivalent to funding or deployment approval.')
    if any(v in q for v in ('certif','ready','pass','evidence','production')):
        return ('The certification endpoint explicitly lists each control. An absent production deployment, independent GL reconciliation, signature anchor, or end-to-end replay yields NOT TESTED / NOT IMPLEMENTED, never pass.')
    return ('This workspace is scoped to '+STEPS[step]+'. Check the decision event stream, captured source references, independent actor, and readiness checklist. '
            'No external evidence or policy outcome is inferred by the UI.')

def call(api:Callable,method:str,path:str,payload=None):
    try:
        result=api(method,path,payload) if payload is not None else api(method,path)
        if isinstance(result,dict) and result.get('error'):
            st.error(str(result['error']));return None
        return result
    except Exception as exc:
        st.error('API request failed; see server logs and check the identity/tenant configuration.')
        return None

def render(api:Callable):
    st.markdown('''<style>
    .ta-hero{background:#071325;border:1px solid #273e61;border-radius:13px;padding:23px 27px;color:#f5f8fc}
    .ta-hero h1{color:#fff;font-size:1.7rem;margin:3px 0 7px}
    .ta-hero p{color:#bdcfe8;margin:0}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="ta-hero"><small>DECISION OS / TRUST & AUDIT CONTROL PLANE</small><h1>Prove the decision record.</h1><p>Independent evaluation · Frozen context · Evidence integrity · Recorded uncertainty</p></div>',unsafe_allow_html=True)
    st.caption('Readiness statements reflect authenticated backend records. This workspace is not a funding/deployment approval engine.')
    did=st.text_input('Decision ID',key='r95_did',placeholder='Paste a Decision OS decision ID')
    if not did.strip():
        st.info('Start with an existing tenant-accessible Decision ID from Decision Ledger. No record is created by this page.')
        return
    base=f'/v1/trust-foundation/{did.strip()}'
    col1,col2=st.columns([3,2])
    with col1:
        step=st.radio('Workflow stage',list(range(5)),format_func=lambda x:f'{x+1:02d}  {STEPS[x]}',horizontal=True,key='r95_step')
        if step in (0,1):
            if st.button('Load R7 event history',key='r95_read'):
                st.session_state['r95_history']=call(api,'GET',f'/v1/decision-events/{did.strip()}')
            h=st.session_state.get('r95_history')
            if h:
                check=h.get('verification') or {}
                st.metric('Recorded events',check.get('event_count','Unknown'))
                st.write('Event-chain verification:', 'Locally consistent' if check.get('valid') else 'Not verified')
                state=h.get('state') or {}
                st.write('Evaluation state:',state.get('status','Unknown'))
                with st.expander('Event history and approval-time evaluation assertions'):
                    st.json(h)
        elif step==2:
            st.warning('Freeze requires the **latest independently attested R7 evaluation**. It is not an authoritative investment approval.')
            seq=st.number_input('Expected event sequence',min_value=2,step=1,value=2,key='r95_seq')
            att=st.text_input('R7 attestation event ID',key='r95_att')
            confirm=st.checkbox('I understand this snapshot captures R7 evaluation assertions, not verified external evidence or funding approval.',key='r95_confirm')
            if st.button('Freeze evaluation snapshot',disabled=not(att.strip() and confirm),key='r95_freeze'):
                st.session_state['r95_last_frozen']=call(api,'POST',base+'/freeze',{
                    'expected_seq':int(seq),'attestation_event_id':att.strip(),'request_id':secrets.token_hex(12)})
            if st.session_state.get('r95_last_frozen'):st.json(st.session_state['r95_last_frozen'])
            if st.button('List & verify snapshots',key='r95_list'):
                st.session_state['r95_shots']=call(api,'GET',base+'/snapshots')
            if st.session_state.get('r95_shots'):st.json(st.session_state['r95_shots'])
        elif step==3:
            st.info('This records a **single reported observation**, not a verified sustained kill-criterion breach.')
            sid=st.text_input('Frozen snapshot ID',key='r95_sid')
            metric=st.text_input('Metric name (must match approved criterion)',key='r95_metric')
            value=st.number_input('Observed value',value=0.0,key='r95_val')
            source=st.text_input('Source record reference',key='r95_source')
            if st.button('Evaluate review candidate',disabled=not(sid and metric and len(source)>=5),key='r95_signal'):
                result=call(api,'POST',base+'/kill-signal',{'snapshot_id':sid,'metric':metric,'value':value,
                                                            'source_ref':source,'request_id':secrets.token_hex(12)})
                if result:st.json(result)
        else:
            if st.button('Run decision-readiness checks',key='r95_certify'):
                st.session_state['r95_cert']=call(api,'GET',base+'/certification')
            report=st.session_state.get('r95_cert')
            if report:
                st.error('NOT PRODUCTION CERTIFIED') if not report.get('certified') else st.success('All controls reported passed')
                st.dataframe([{'control':k,'result':str(v)} for k,v in report.get('checks',{}).items()],hide_index=True,use_container_width=True)
                st.download_button('Export certification JSON',json.dumps(report,indent=2),file_name='decision_readiness.json',mime='application/json')
    with col2:
        st.subheader('Screen guide')
        st.caption('Active function: '+STEPS[step])
        for q in QUESTIONS[step]:
            if st.button(q,key=f'r95_question_{step}_{q}'):
                st.session_state['r95_question']=q
        question=st.text_area('Ask about this step',value=st.session_state.get('r95_question',''),key=f'r95_input_{step}')
        if st.button('Ask Trust Copilot',disabled=not question.strip(),key=f'r95_ask_{step}'):
            st.info(guidance(question,step))
        st.caption('Deterministic workflow help only. No external system access, approvals, automatic execution, or speculative evidence.')
