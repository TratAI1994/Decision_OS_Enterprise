"""Decision OS R9.7 — guided observation window control plane.
Integrate using render(api), same authenticated api adapter as R9.5.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
import streamlit as st

STEPS=('Select decision','Inspect frozen criteria','Submit observation','Assess window')
HELP={
'Select decision':('Which decision should I examine?', 'Select an authorized decision ID from Trust & Audit. Only your tenant records are accessible.'),
'Inspect frozen criteria':('Why must criteria be frozen?', 'Only criteria captured in the trust snapshot can be assessed. Adding new criteria does not rewrite old decisions.'),
'Submit observation':('Will submitted data trigger a stop?', 'No. A user-submitted measurement is unverified and cannot authorize a halt or be promoted to validated telemetry.'),
'Assess window':('Why is a breached reading not enough?', 'A time-window requirement needs independently verified, timestamped observations with adequate coverage, and separate reviewer approval.'),
}

def render(api):
    st.markdown('''<style>
    .kw-hero{padding:24px 28px;border-radius:14px;background:linear-gradient(125deg,#111d32,#1b2c48);color:#f7f9ff;border:1px solid #354861}
    .kw-hero h1{font-size:1.75rem;font-weight:550;letter-spacing:-.03em;margin:.2rem 0;color:#f7f9ff}
    .kw-hero p{color:#b7c9df;margin:0}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="kw-hero"><small>DECISION INFRASTRUCTURE / TRUST CONTROL PLANE</small><h1>Kill-Window Assurance</h1><p>Observe → validate provenance → assess the window → request human review</p></div>',unsafe_allow_html=True)
    st.info('R9.7 is an advisory observation ledger. Source-system verification, sustained-condition proof, and automatic intervention are NOT enabled.')
    st.graphviz_chart('''digraph Workflow { rankdir=LR; bgcolor="transparent"; node [shape=box,style="rounded,filled",fillcolor="#172A46",fontcolor="#FFFFFF",color="#59769A",fontname="Arial",fontsize=11]; edge[color="#7796B8"]; F [label="Frozen\ncriterion"]; O [label="Unverified\nobservation"]; V [label="Source verifier\nNOT CONNECTED",fillcolor="#544333"]; R [label="Human review\nrequired"]; F->O->V->R; }''',use_container_width=True)
    stage=st.segmented_control('Current step',STEPS,default=STEPS[0],key='r97_step') if hasattr(st,'segmented_control') else st.radio('Current step',STEPS,horizontal=True,key='r97_step')
    left,right=st.columns([2,1],gap='large')
    with left:
        did=st.text_input('Decision ID',key='r97_decision',placeholder='Existing tenant-scoped Decision ID')
        if not did:
            st.info('Enter an existing Decision ID before proceeding.')
            return
        try:
            response=api('GET',f'/v1/trust-foundation/{did}/snapshots',quiet=True)
            snaps=response.get('snapshots',[]) if isinstance(response,dict) else []
        except (ValueError,KeyError,TypeError):
            snaps=[]
        if not snaps:
            st.warning('No accessible trust snapshot found. Complete independent R7 attestation and R9.5 freeze first.')
            return
        options={f"Version {s.get('decision_version','?')} · {s.get('id','')[:12]}":s for s in snaps}
        selected=st.selectbox('Frozen trust snapshot',list(options),key='r97_snap')
        snap=options[selected]
        sid=snap['id']
        criteria=snap.get('snapshot',{}).get('baseline',{}).get('kill_criteria',[])
        st.caption('Snapshot integrity: '+str(snap.get('integrity',{}).get('assurance','NOT VERIFIED')))
        if stage==STEPS[0]:
            st.write('This workflow uses your existing Decision OS identity and R9.5 snapshot. An external signature is not implied.')
        elif stage==STEPS[1]:
            if not criteria:st.warning('No criteria were recorded in this frozen evaluation version.')
            else:st.dataframe([{'metric':c.get('metric'),'operator':c.get('operator'),'threshold':c.get('threshold'),'window_days':c.get('window_days'),'required_action':c.get('required_action')} for c in criteria],hide_index=True,use_container_width=True)
        elif stage==STEPS[2]:
            if not criteria:st.error('Cannot submit observation without a frozen criterion.')
            else:
                metrics=sorted({str(c.get('metric')) for c in criteria if c.get('metric')})
                metric=st.selectbox('Metric',metrics)
                value=st.text_input('Observed value (decimal)',placeholder='e.g. 8.7')
                ref=st.text_input('Source reference',placeholder='Evidence reference, not proof of verification')
                obs_at=st.datetime_input('Measurement timestamp',value=datetime.now(timezone.utc).replace(tzinfo=None)) if hasattr(st,'datetime_input') else None
                if st.button('Append unverified observation',type='primary',disabled=not value.strip() or len(ref.strip())<5):
                    payload={'snapshot_id':sid,'metric':metric,'value':value.strip(),
                             'observed_at':(obs_at.replace(tzinfo=timezone.utc) if obs_at else datetime.now(timezone.utc)).isoformat(),
                             'source_ref':ref,'request_id':'r97_'+uuid.uuid4().hex}
                    try:
                        result=api('POST',f'/v1/kill-windows/{did}/observations',payload)
                        if result:st.success('Recorded as SUBMITTED_UNVERIFIED. No policy action executed.')
                        else:st.error('Backend did not confirm an append.')
                    except (ValueError,TypeError,KeyError) as exc:st.error(f'Observation was not recorded: {exc}')
        else:
            try:
                result=api('GET',f'/v1/kill-windows/{did}/assessment/{sid}',quiet=True)
            except (ValueError,TypeError,KeyError):result=None
            if isinstance(result,dict):
                st.dataframe(result.get('assessments',[]),hide_index=True,use_container_width=True)
                st.caption(result.get('note',''))
            else:st.warning('Assessment unavailable. Verify that the R9.7 API migration and route are installed.')
    with right:
        st.subheader('Screen Guide')
        st.caption('Suggestions change with the active stage.')
        q,a=HELP[stage]
        st.button(q,key='r97_hint',on_click=lambda:st.session_state.update({'r97_q':q}))
        query=st.text_area('Ask about this step',key='r97_q',placeholder='Ask about evidence, timestamps or approvals')
        if st.button('Explain',disabled=not query.strip()):
            st.write(a if any(word in query.lower() for word in ['why','what','how','evidence','metric','approval','step','threshold','source','window','review']) else 'I can only explain the current verification step and its required evidence. I cannot infer a causal result or approve an action.')
        st.caption('Answers are deterministic guidance, not inspection of private source-system records.')
