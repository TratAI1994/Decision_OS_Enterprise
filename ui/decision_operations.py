"""Decision OS — Decision Operations, read-only intervention design.

No invented monetary values, causal attribution, execution or finance verification.
Only authorized data from the caller-provided tenant-scoped FastAPI adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
import json
import re
import streamlit as st


@dataclass(frozen=True)
class FinancialEvidence:
    modeled: Decimal | None
    projected: Decimal | None
    realized: Decimal | None
    currency: str
    period: str
    finance_verified: bool
    verification_reference: str | None


def parse_financial_evidence(row: dict) -> FinancialEvidence:
    """Only an explicit finance verification with reference counts as realized value."""
    def amount(value):
        if value is None or isinstance(value, bool): return None
        try:
            d = Decimal(str(value))
            return d if d.is_finite() else None
        except (InvalidOperation, ValueError): return None
    f = row.get('financial_lifecycle')
    if not isinstance(f, dict): f = {}
    def block(key):
        v = f.get(key)
        return v if isinstance(v, dict) else {}
    m, p, r = block('modeled_value'), block('projected_value'), block('realized_value')
    curr = str(r.get('currency') or p.get('currency') or m.get('currency') or '')
    period = str(r.get('period') or p.get('period') or m.get('period') or '')
    ref = r.get('verification_reference') or r.get('verification_document_id')
    verified = bool(r.get('verified_by') and r.get('verified_at') and ref)
    # Incompatible currencies or periods must never be combined in a financial gap.
    components = [x for x in (m,p,r) if amount(x.get('amount')) is not None]
    if len({x.get('currency') for x in components}) > 1 or len({x.get('period') for x in components}) > 1:
        return FinancialEvidence(None,None,None,curr,period,False,None)
    return FinancialEvidence(amount(m.get('amount')),amount(p.get('amount')),
                             amount(r.get('amount')) if verified else None,curr,period,verified,
                             str(ref) if verified else None)


def financial_variance(f: FinancialEvidence) -> Decimal | None:
    if not f.finance_verified or f.projected is None or f.realized is None or not f.currency or not f.period:
        return None
    return f.projected - f.realized


def debt_signals(assumptions: list[dict], krs: list[dict], packets: list[dict],
                 decisions: list[dict] | None = None) -> list[dict]:
    """Count documented exceptions, not undocumented absence as success."""
    out = []
    for a in assumptions:
        state = str(a.get('validation_status') or 'unknown').lower()
        if state in ('invalidated','refuted','expired'):
            out.append({'kind':'Assumption','severity':'Critical' if state in ('invalidated','refuted') else 'Attention',
                        'label':str(a.get('statement') or a.get('id') or 'Assumption'),
                        'reason':f'Recorded status: {state}', 'ref':str(a.get('id') or '')})
    for kr in krs:
        raw=kr.get('status'); state=str(raw.get('state') if isinstance(raw,dict) else raw or kr.get('state') or '').upper()
        if state in ('STALE','NO_DATA','NOT MEASURED'):
            out.append({'kind':'Measurement','severity':'Attention',
                        'label':str(kr.get('title') or kr.get('id') or 'KR'),
                        'reason':f'Recorded measurement status: {state}', 'ref':str(kr.get('id') or '')})
    for p in packets:
        if str(p.get('status') or '').lower() in ('draft','pending_review','awaiting_approval'):
            out.append({'kind':'Review','severity':'Attention','label':str(p.get('title') or p.get('id') or 'Packet'),
                        'reason':'Awaiting authorized review','ref':str(p.get('id') or '')})
    return sorted(out,key=lambda x:(0 if x['severity']=='Critical' else 1,x['kind'],x['label']))


def evidence_advisor(query: str, signals: list[dict], decision: dict | None = None) -> dict:
    """Closed vocabulary, extractive advisor; never synthesizes unverifiable conclusions."""
    q=query.casefold().strip()
    if not q:
        return {'status':'REFUSED','answer':'Please specify a decision or evidence question.','sources':[]}
    allowed=('risk','assumption','stale','review','gap','recover','interven','decision','evidence','why','packet','next','status')
    if not any(w in q for w in allowed):
        return {'status':'NO_EVIDENCE','answer':'No verified evidence in the accessible records supports a response to that question. I cannot speculate.','sources':[]}
    if not signals:
        return {'status':'NO_EVIDENCE','answer':'No relevant recorded signals are available. This does not establish that the decision is healthy.','sources':[]}
    refs=[s['ref'] for s in signals if s.get('ref')]
    descriptions=[f"{s['kind']}: {s['label']} ({s['reason']}) [record: {s['ref'] or 'unavailable'}]" for s in signals[:8]]
    return {'status':'EVIDENCE_SUMMARY','answer':'Recorded issues requiring assessment:\n'+'\n'.join('- '+d for d in descriptions),
            'sources':refs[:8]}


def prepare_action_packet(query: str, signals: list[dict], decision: dict | None) -> dict:
    """Structured local preview; no privilege, approval or side effect."""
    if not decision or not signals:
        raise ValueError('A selected decision and at least one recorded signal are required.')
    if not any(w in query.casefold() for w in ('recover','address','review','resolve','investigate','plan','what next','interven')):
        raise ValueError('Ask for a review, investigation or recovery plan.')
    did=str(decision.get('id') or '')
    if not did: raise ValueError('Decision ID missing.')
    selected=signals[0]
    if not selected.get('ref'): raise ValueError('Signal lacks source record ID.')
    return {
        'artifact_type':'LOCAL_ACTION_PACKET_PREVIEW',
        'decision_id':did,'decision_title':str(decision.get('title') or 'Untitled decision'),
        'signal':selected,'drafted_by':'deterministic_decision_operator',
        'approval_state':'NOT_SUBMITTED','execution_state':'PROHIBITED',
        'alternatives':[
            {'name':'A — Investigate source and measurement','steps':['Assign the accountable evidence owner','Validate source integrity and measurement window','Document findings and limitations'],
             'estimated_impact':'UNKNOWN — NOT MODELED'},
            {'name':'B — Convene governance re-evaluation','steps':['Review frozen decision assumptions','Request independent risk and business review','Determine whether a revised decision is warranted'],
             'estimated_impact':'UNKNOWN — NOT MODELED'}],
        'escalation_path':'Existing Decision Action Center; assigned human decision owner and independent reviewer',
        'evidence_refs':[selected['ref']],
        'limitations':['No causal inference','No verified financial impact','No policy evaluation performed',
                       'No action executed or authorized'],
        'required_before_execution':['Backend authenticated draft submission','Independent human approval',
                                      'Fresh backend policy evaluation','Scoped execution authorization']
    }


def load_evidence(api: Callable) -> tuple[dict, list[str]]:
    routes={'decisions':'/v1/intelligence/decisions','assumptions':'/v1/strategy/assumptions',
            'krs':'/v1/strategy/key-results','packets':'/v1/decisions-governed/packets'}
    data={}; warnings=[]
    for key,path in routes.items():
        try:
            v=api('GET',path,quiet=True)
            if not isinstance(v,list):
                warnings.append(f'{key}: unavailable or wrong response type'); v=[]
            data[key]=v
        except Exception:
            warnings.append(f'{key}: source unavailable'); data[key]=[]
    return data,warnings


def _hero():
    st.markdown('''<style>
    .ops-hero{background:linear-gradient(120deg,#101c32,#204567);padding:30px;border-radius:18px;color:#fff;margin-bottom:18px}
    .ops-hero h1{color:#fff;margin:0;font-weight:650;letter-spacing:-.03em;font-size:2rem}
    .ops-hero p{color:#dce9f6;margin:8px 0 0}
    </style><div class="ops-hero"><h1>Decision Operations</h1>
    <p>Value integrity · Decision debt · Evidence-grounded intervention design</p></div>''',unsafe_allow_html=True)


def render(api: Callable | None = None, navigate: Callable | None = None):
    _hero()
    st.caption('Read-only intelligence with locally prepared intervention packets. No vendor connection, financial reconciliation, approval, or execution is implied.')
    if not api:
        st.warning('Authenticated API adapter is required.');return
    data,warnings=load_evidence(api)
    if warnings: st.warning('Incomplete API coverage: '+'; '.join(warnings)+'. Unavailable records are not treated as clear.')
    decs=data['decisions']
    if not decs:
        st.info('No accessible decisions. Operating metrics and interventions are unavailable.'); return
    choice=st.selectbox('Decision under review',decs,format_func=lambda d:str(d.get('title') or d.get('id')),key='ops_decision')
    did=str(choice.get('id'))
    assumptions=[a for a in data['assumptions'] if str(a.get('decision_id'))==did]
    packets=[p for p in data['packets'] if str(p.get('decision_id'))==did]
    # Only KR records carrying a directly explicit decision_id are attributable here.
    krs=[k for k in data['krs'] if str(k.get('decision_id'))==did]
    tabs=st.tabs(['Value Realization','Decision Debt','Decision Operator','Integrity & Limits'])
    with tabs[0]:
        st.subheader('AI value realization · Finance evidence first')
        f=parse_financial_evidence(choice)
        a,b,c=st.columns(3)
        def money(v): return f'{f.currency} {v:,.2f}' if v is not None and f.currency else 'Not available'
        a.metric('Modeled at approval',money(f.modeled))
        b.metric('Projected value',money(f.projected))
        c.metric('Finance-verified realized',money(f.realized))
        gap=financial_variance(f)
        st.metric('Projected less finance-verified realized',money(gap))
        if gap is None:
            st.info('Not assessable: a consistent period/currency and independently finance-verified realized amount are required. No “value at risk” or cash loss is claimed.')
        else:
            st.caption(f'Period: {f.period} · Verification reference: {f.verification_reference} · Difference is not a causal or realized-loss determination.')
        st.markdown('**Largest financial drivers**')
        st.info('Unavailable until source-linked, finance-reconciled drivers exist; no example amounts are mixed into live data.')
    with tabs[1]:
        st.subheader('Decision Debt Monitor')
        signal=debt_signals(assumptions,krs,packets,[choice])
        x,y,z=st.columns(3)
        x.metric('Recorded open signals',len(signal))
        y.metric('Critical signals',sum(i['severity']=='Critical' for i in signal))
        z.metric('Source completeness','Partial' if warnings else 'Endpoints accessible')
        st.caption('The count is a workload indicator, not an enterprise-wide debt index or scientifically calibrated score. Unknown dependencies are excluded and disclosed.')
        if not signal:st.info('No known signals in accessible linked records. Absence of signals is not evidence of sound decisions.')
        for item in signal:
            with st.container(border=True):
                st.markdown(f"**{item['severity']} · {item['kind']} — {item['label']}**")
                st.caption(f"{item['reason']} · Record {item['ref'] or 'unknown'}")
    with tabs[2]:
        st.subheader('Enterprise Decision Operator')
        st.caption('Deterministic evidence advisor. It cannot execute, approve, change assumptions or invent facts.')
        if 'ops_chat_history' not in st.session_state:st.session_state['ops_chat_history']=[]
        for entry in st.session_state['ops_chat_history'][-10:]:
            with st.chat_message(entry['role']):st.markdown(entry['content'])
        message=st.chat_input('Ask: What needs review? How do we recover this decision?')
        if message:
            st.session_state['ops_chat_history'].append({'role':'user','content':message})
            ans=evidence_advisor(message,signal,choice)
            st.session_state['ops_chat_history'].append({'role':'assistant','content':ans['answer']})
            st.rerun()
        st.markdown('**Prepare an evidence-linked recovery packet**')
        request=st.text_input('Intervention objective',value='Investigate and recover the recorded decision gaps',key='ops_request')
        if st.button('Generate local Action Packet preview',type='primary',key='ops_prepare'):
            try:st.session_state['ops_packet']=prepare_action_packet(request,signal,choice)
            except ValueError as exc:st.error(str(exc))
        packet=st.session_state.get('ops_packet')
        if packet and packet.get('decision_id')==did:
            st.warning('PREVIEW ONLY — NOT SUBMITTED, NOT APPROVED, NOT EXECUTABLE')
            st.json(packet)
            st.download_button('Export draft JSON',json.dumps(packet,indent=2),file_name='decision-operator-preview.json',mime='application/json')
            if st.button('Open governed Action Center',key='ops_open_action'):
                if navigate:navigate('Decision Action Center')
                else:st.info('Use your existing Decision Action Center for authorized actions.')
    with tabs[3]:
        st.markdown('**Integrity requirements for production**')
        st.write('A real lock must be backed by approval-time evidence snapshots, independent identities, append-only storage, durable audit and policy evaluation.')
        st.write('A real intervention requires a backend-created Action Packet, separation of duties and a fresh authorization check immediately before execution.')
        st.info('The page reads existing authorized records. No additional vendor API connections or financial reconciliation endpoints are created by this UI release.')
