"""Decision OS R7 — Event Ledger. Uses only authenticated server APIs."""
from __future__ import annotations

import json
import secrets

import streamlit as st


def _event_rows(result):
    return [{'Sequence':r['seq'],'Time (UTC)':r['occurred_at'],'Event':r['event_type'].replace('decision.','').replace('_',' ').title(),
             'Actor':r['actor_id'],'SHA-256':r['event_hash'][:22]+'…'} for r in result.get('events',[])]


def render(api, navigate=None):
    st.title('Decision Integrity · Event Ledger')
    st.caption('An auditable, append-only *evaluation-attestation slice*. Funding approvals and production actions remain governed by the existing Trust Layer.')
    st.info('Integrity labels mean the event hash chain is internally consistent—not cryptographically signed, externally anchored or immune to a privileged database administrator.')
    records=api('GET','/v1/intelligence/decisions',quiet=True)
    if isinstance(records,dict): records=records.get('items',records.get('decisions',[]))
    if not isinstance(records,list):
        st.warning('Authorized decisions are unavailable. No sample decisions will be substituted.');return
    labels={f"{str(d.get('title') or d.get('name') or d.get('id',''))[:65]} · {d.get('id','')}":d['id'] for d in records if d.get('id')}
    if not labels:
        st.info('No authorized decisions found. Create a decision first in the Executive Decision Ledger.');return
    chosen=st.selectbox('Decision',list(labels),key='r7_event_decision')
    did=labels[chosen]
    result=api('GET',f'/v1/decision-events/{did}',quiet=True)
    if not isinstance(result,dict):
        st.warning('R7 API not available or integrity verification failed. Check API logs and migration before continuing.');return
    state=result.get('state') or {};verification=result.get('verification') or {};events=result.get('events') or []
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Event count',len(events))
    c2.metric('Decision version',state.get('version','—'))
    c3.metric('Attestation state',str(state.get('status','unknown')).title())
    c4.metric('Hash-chain verification','Consistent' if verification.get('valid') else 'Not verified')
    tabs=st.tabs(['Decision at this moment','Event timeline','Propose baseline / amendment','Independent attestation','Evidence & audit'])
    with tabs[0]:
        snap=state.get('snapshot')
        if not snap:st.info('No baseline event has been recorded for this decision.')
        else:
            st.subheader('Preserved decision context')
            st.write('**Recommendation:**',snap.get('recommendation','Not captured'))
            st.write('**Rationale:**',snap.get('rationale','Not captured'))
            st.write('**Expected outcome:**',snap.get('expected_outcome','Not captured'))
            st.write('**Decision owner:**',state.get('owner_id','Not captured'))
            st.write('**Policy version:**',snap.get('policy_version','Not captured'))
            st.write('**Next review:**',snap.get('review_due','Not scheduled'))
            st.write('**Kill criteria (predeclared in recorded baseline):**')
            st.dataframe(snap.get('kill_criteria',[]),use_container_width=True,hide_index=True)
            st.write('**Assumptions:**',snap.get('assumptions',[]))
            st.write('**Evidence references:**',snap.get('evidence_refs',[]))
            if state.get('approved_by'):st.caption(f"Independent evaluation attested by {state['approved_by']} at {state.get('approved_at')}. Not deployment approval.")
    with tabs[1]:
        st.subheader('Reconstructed from the event stream')
        st.dataframe(_event_rows(result),use_container_width=True,hide_index=True)
        if events:st.code(verification.get('head_hash',''),language='text')
        st.download_button('Export event stream JSON',json.dumps(result,indent=2,default=str),file_name=f'decision_{did}_events.json',mime='application/json')
    with tabs[2]:
        st.subheader('Prepare a new recorded event')
        st.caption('The API checks tenant access, optimistic sequence, idempotency and the pre-existing decision. This does not alter the canonical decision approval.')
        if not events:
            with st.form('r7_begin_form'):
                owner=st.text_input('Accountable owner ID')
                recommendation=st.text_area('Recommendation',placeholder='Describe the specific proposed decision')
                rationale=st.text_area('Decision-time rationale')
                target=st.text_input('Expected outcome and measurement method')
                assumptions=st.text_area('Assumptions (one per line)')
                refs=st.text_area('Evidence record references (one per line)')
                metric=st.text_input('Kill criterion · metric ID')
                op=st.selectbox('Kill criterion · comparison',['gt','gte','lt','lte'])
                threshold=st.number_input('Kill criterion · numeric threshold',value=0.0)
                window=st.number_input('Evaluation window (days)',min_value=1,max_value=365,value=30)
                action=st.selectbox('Required action on breach',['review','escalate','propose_pause'])
                due=st.text_input('Review due date (YYYY-MM-DD)')
                policy=st.text_input('Applicable policy version',value='unverified-draft')
                submit=st.form_submit_button('Record baseline · append event',type='primary')
            if submit:
                missing=[n for n,v in [('owner',owner),('recommendation (≥10 chars)',recommendation if len(recommendation.strip())>=10 else ''),('rationale (≥10 chars)',rationale if len(rationale.strip())>=10 else ''),('outcome',target),('metric',metric),('review date',due)] if not v.strip()]
                if missing:st.error('Complete: '+', '.join(missing))
                else:
                    payload={'decision_id':did,'owner_id':owner,'recommendation':recommendation,'rationale':rationale,'expected_outcome':target,
                             'assumptions':[s.strip() for s in assumptions.splitlines() if s.strip()],
                             'evidence_refs':[s.strip() for s in refs.splitlines() if s.strip()],
                             'kill_criteria':[{'metric':metric,'operator':op,'threshold':float(threshold),'window_days':int(window),'required_action':action}],
                             'review_due':due,'policy_version':policy,'request_id':secrets.token_hex(20)}
                    r=api('POST','/v1/decision-events/begin',payload)
                    if isinstance(r,dict) and r.get('id'):st.success('Baseline event recorded');st.rerun()
        else:
            st.caption('Amendments append a new event and preserve all original versions. The existing attestation does not carry over.')
            with st.form('r7_amend_form'):
                reason=st.text_area('Why is the amendment necessary?')
                assumptions=st.text_area('Revised assumptions (one per line)',value='\n'.join(state.get('snapshot',{}).get('assumptions') or []))
                refs=st.text_area('Revised evidence refs (one per line)',value='\n'.join(state.get('snapshot',{}).get('evidence_refs') or []))
                submit=st.form_submit_button('Propose amendment · append event')
            if submit:
                if len(reason.strip())<10:st.error('An amendment requires a meaningful rationale.')
                else:
                    payload={'expected_seq':len(events),'rationale':reason,
                             'assumptions':[s.strip() for s in assumptions.splitlines() if s.strip()],
                             'evidence_refs':[s.strip() for s in refs.splitlines() if s.strip()],
                             'request_id':secrets.token_hex(20)}
                    r=api('POST',f'/v1/decision-events/{did}/amend',payload)
                    if isinstance(r,dict) and r.get('id'):st.success('New version event recorded');st.rerun()
    with tabs[3]:
        st.subheader('Independent review · evaluation attestation only')
        st.write('Current author:',state.get('author_id','—'))
        st.write('Current owner:',state.get('owner_id','—'))
        st.caption('The backend rejects author/owner self-attestation, duplicate attestations and stale event sequences. No reviewer identity can be selected in the UI.')
        confirmation='I independently reviewed this decision snapshot and its evidence limitations.'
        with st.form('r7_attestation_form'):
            acknowledged=st.checkbox('I have reviewed the decision-time context, supporting references, kill criteria and limitations.')
            submit=st.form_submit_button('Append independent attestation',type='primary')
        if submit:
            if not acknowledged:st.error('Explicit reviewer acknowledgment is required.')
            else:
                r=api('POST',f'/v1/decision-events/{did}/attest',{'expected_seq':len(events),'confirmation':confirmation,'request_id':secrets.token_hex(20)})
                if isinstance(r,dict) and r.get('id'):st.success('Attestation appended');st.rerun()
    with tabs[4]:
        st.subheader('Evidence lineage and independent verification')
        st.write('**Evidence references:**',(state.get('snapshot') or {}).get('evidence_refs',[]))
        st.info('References are pointers, not verified source documents. Proof requires controlled evidence retrieval, content hashing, authorized independent verification and protected retention.')
        st.write('**Current verification:**',verification.get('meaning','Not verified'))
        st.caption('Hash-chain verification catches many accidental/unauthorized edits, but a privileged adversary can rewrite a whole chain unless heads are signed and anchored externally.')
