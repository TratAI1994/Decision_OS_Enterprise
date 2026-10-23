"""Decision OS — Ecosystem Intelligence and read-only Decision Operations.

Provider risk mappings are illustrative design prompts, NOT vendor attestations.
No approval, API POST, identity alteration, or financial-reconciliation claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Callable, Any
import json
import streamlit as st


@dataclass(frozen=True)
class Provider:
    key: str
    name: str
    group: str
    decision_surface: str
    signals: str
    checks: tuple[tuple[str, str, str], ...]  # category, risk, requested evidence

PROVIDERS = (
    Provider('azure', 'Microsoft Azure AI', 'Infrastructure AI', 'Model/region/cost selection', 'Usage, request logs, cost (when connected)', (
        ('Identity', 'Over-broad service permissions', 'Workload identity and API permission inventory'),
        ('Privacy', 'Sensitive information exposed in prompts or retrieval', 'Data-classification and regional-processing assessment'),
        ('Economics', 'Variable consumption exceeds forecasts', 'Spend cap, budget baseline, cost owner'),
        ('Safety', 'Untrusted content may redirect tool calls', 'Prompt-injection tests and scoped tool permissions'))),
    Provider('vertex', 'Google Vertex AI', 'Infrastructure AI', 'Model/evaluation/grounding choice', 'Evaluations, usage, traces (when connected)', (
        ('Data', 'Outdated or over-shared grounding sources', 'Grounding provenance and access evaluation'),
        ('Evaluation', 'Model quality unproven on real tasks', 'Versioned task-specific evaluation report'),
        ('Agent Security', 'External tools increase attack surface', 'Tool allowlist, blast radius and red-team evidence'))),
    Provider('bedrock', 'AWS Bedrock', 'Infrastructure AI', 'Model/agent/knowledge architecture', 'Invocation and evaluation data (when connected)', (
        ('Guardrails', 'Controls may not cover use-case harms', 'Use-case-specific safety evaluation'),
        ('Costs', 'Token and retrieval costs may vary', 'Spend forecast with sensitivity and alarms'),
        ('Knowledge', 'Knowledge-base content can become stale', 'Index refresh and document ACL tests'))),
    Provider('sap', 'SAP Business AI / Joule', 'Business Platform AI', 'Enterprise process/ERP decisions', 'Process events and finance records (when connected)', (
        ('ERP Authorization', 'Cross-role exposure of finance, procurement or workforce data', 'ERP authorization review and segregation-of-duties evidence'),
        ('Business Impact', 'Operational improvement has uncertain attribution', 'Baseline, comparison cohort and finance reconciliation plan'),
        ('Control', 'Automation might bypass approval chains', 'Process approval and rollback mapping'))),
    Provider('salesforce', 'Salesforce Agentforce', 'Business Platform AI', 'CRM-facing agent decisions', 'CRM/agent actions and service KPIs (when connected)', (
        ('Customer Privacy', 'Agents may expose customer or pipeline records', 'CRUD/FLS/sharing validation and test evidence'),
        ('External Actions', 'Outbound messages or CRM writes may have consequences', 'Allowed actions, approval thresholds and human escalation'),
        ('Attribution', 'Revenue gains may be correlated with human activity', 'Holdout/cohort methodology and confounders'))),
    Provider('servicenow', 'ServiceNow AI Platform / Control Tower', 'Business Platform AI', 'IT/HR/service workflow decisions', 'Incident, request and workflow events (when connected)', (
        ('Change Safety', 'Workflow actions may propagate across systems', 'Change governance, scoped permissions and rollback plan'),
        ('Automation', 'Silent failures may compromise service levels', 'SLO, escalation ownership and failure-injection tests'),
        ('Data Governance', 'Enterprise records may have differing entitlements', 'Record-level access and data retention mapping'))),
)
PROVIDER_BY_KEY = {p.key: p for p in PROVIDERS}


def required_checks(provider_key: str) -> tuple[tuple[str, str, str], ...]:
    if provider_key not in PROVIDER_BY_KEY:
        raise ValueError('Unsupported ecosystem')
    return PROVIDER_BY_KEY[provider_key].checks


def risk_signals(assumptions: list[dict], krs: list[dict], packets: list[dict],
                 *, decision_id: str | None = None) -> list[dict]:
    """Report known issues, never infer a cash loss from metric variance."""
    results: list[dict] = []
    for a in assumptions:
        if decision_id and str(a.get('decision_id')) != decision_id:
            continue
        state = str(a.get('validation_status') or 'unknown').lower()
        if state in {'invalidated', 'under_test', 'unknown'}:
            results.append({'type': 'Assumption', 'priority': 0 if state == 'invalidated' else 2,
                            'title': str(a.get('statement') or 'Unnamed assumption'),
                            'reason': f'Reviewed state: {state}', 'ref': str(a.get('id') or '')})
    for kr in krs:
        if not isinstance(kr, dict):
            continue
        s = kr.get('status')
        state = str((s.get('state') if isinstance(s, dict) else s) or kr.get('state') or 'UNKNOWN').upper()
        if state in {'STALE', 'NO_DATA', 'NOT MEASURED'}:
            results.append({'type': 'Measurement', 'priority': 1, 'title': str(kr.get('title') or 'Key Result'),
                            'reason': 'Measurement '+state, 'ref': str(kr.get('id') or '')})
    for p in packets:
        if decision_id and str(p.get('decision_id')) != decision_id:
            continue
        if str(p.get('status') or '').lower() == 'draft':
            results.append({'type': 'Approval', 'priority': 1,
                            'title': str(p.get('title') or 'Action Packet'),
                            'reason': 'Pending independent review', 'ref': str(p.get('id') or '')})
    return sorted(results, key=lambda item: (item['priority'], item['type'], item['title']))


def safe_source_bundle(api: Callable) -> tuple[list, list, list, list, str | None]:
    paths = ('/v1/intelligence/decisions', '/v1/strategy/assumptions',
             '/v1/strategy/key-results', '/v1/decisions-governed/packets')
    results = []
    errors = []
    for path in paths:
        try:
            value = api('GET', path, quiet=True)
            if not isinstance(value, list):
                errors.append(path + ': unavailable')
                results.append([])
            else:
                results.append(value)
        except Exception:
            errors.append(path + ': unavailable')
            results.append([])
    return (*results, '; '.join(errors) if errors else None)


def make_draft(name: str, sponsor: str, purpose: str, provider_key: str, tier: str) -> dict:
    if len(name.strip()) < 5: raise ValueError('Deployment name needs at least 5 characters')
    if len(sponsor.strip()) < 2: raise ValueError('Accountable sponsor is required')
    if len(purpose.strip()) < 40: raise ValueError('Intended use needs at least 40 characters')
    provider = PROVIDER_BY_KEY[provider_key]
    return {'type': 'LOCAL_PREVIEW_NOT_SUBMITTED', 'deployment': name.strip(), 'sponsor': sponsor.strip(),
            'intended_use': purpose.strip(), 'ecosystem': provider.name, 'preliminary_risk_tier': tier,
            'proposed_controls': [{'category': c, 'risk': r, 'required_evidence': e}
                                  for c,r,e in provider.checks],
            'disclaimer': 'This is a local preview, not an authorized Decision or Risk record.'}


def _styles():
    st.markdown('''<style>
    .ecos-hero{background:linear-gradient(110deg,#101d36,#183d63);color:#f9fbff;
      border-radius:20px;padding:28px 30px;margin:8px 0 20px}
    .ecos-hero h1{color:#fff;font-size:2rem;margin:0 0 6px}
    .ecos-hero p{color:#cee0f4;margin:0}
    .ecos-tile{border:1px solid #dce5f0;border-radius:14px;padding:17px;
      background:#fff;min-height:163px;margin-bottom:10px;color:#19304b}
    .ecos-tile .eyebrow{font-size:.72rem;letter-spacing:.1em;color:#53637b;text-transform:uppercase}
    .ecos-tile h3{font-size:1.05rem;margin:.5rem 0;color:#173450}
    .ecos-tile p{font-size:.85rem;color:#4a5b70}
    </style>''', unsafe_allow_html=True)


def _matrix():
    for group in ('Infrastructure AI', 'Business Platform AI'):
        st.markdown('#### ' + group)
        cols = st.columns(3)
        for col,p in zip(cols, [x for x in PROVIDERS if x.group == group]):
            with col:
                st.markdown(f'<div class="ecos-tile"><div class="eyebrow">{escape(p.group)}</div>'
                            f'<h3>{escape(p.name)}</h3><p>{escape(p.decision_surface)}</p>'
                            f'<p><b>Possible signals:</b> {escape(p.signals)}</p></div>', unsafe_allow_html=True)
    st.caption('This is an architectural registry, not a live integration inventory or evidence of connected vendor data.')


def _flow():
    st.markdown('#### From vendor telemetry to governed interventions')
    nodes = [
        ('01 · Ecosystem events', 'Model invocations, tickets, CRM actions and ERP transactions'),
        ('02 · Decision context', 'Existing decision, owner, alternatives, risk, baseline and assumptions'),
        ('03 · Measurement integrity', 'Freshness, source identity, evidence quality and attribution limitations'),
        ('04 · Decision Intelligence', 'Observed variance, assumption status and governance/economics checks'),
        ('05 · Decision Operations', 'Evidence-linked intervention draft → policy checks → independent review'),
        ('06 · Verified follow-through', 'Assigned action → independently observed outcome → decision replay'),
    ]
    for i,(label,detail) in enumerate(nodes):
        with st.container(border=True):
            st.markdown(f'**{label}**')
            st.caption(detail)
        if i<len(nodes)-1:st.markdown('<div style="text-align:center;color:#71859b">↓</div>',unsafe_allow_html=True)
    st.info('A difference between forecast and actual is not proof of financial loss or causality. Intervention recommendations require evidence and authorized review.')


def _route():
    st.markdown('#### Ecosystem-targeted deployment review')
    selected = st.selectbox('Target vendor ecosystem', PROVIDERS, format_func=lambda p:p.name,
                            key='ecos_provider', help='Shows preliminary integration risks; this selection does not classify regulatory risk.')
    st.caption('Risk considerations below are design prompts, not verified deficiencies in the selected vendor product.')
    for category, risk, evidence in selected.checks:
        with st.expander(category + ' · Evidence requirement'):
            st.write(risk)
            st.write('**Evidence to request:** ' + evidence)
    st.markdown('##### Prepare a decision-registration preview')
    name = st.text_input('Deployment name', key='ecos_name', placeholder='e.g. Claims Assistant Pilot')
    sponsor = st.text_input('Human accountable sponsor',key='ecos_sponsor',placeholder='e.g. VP Customer Operations')
    purpose = st.text_area('Purpose and affected stakeholders',key='ecos_purpose',
                           placeholder='Describe business outcome, users, and which actions the AI can take.')
    tier = st.selectbox('Preliminary risk tier',('unassessed','minimal','limited','high','critical'),key='ecos_risk_tier')
    if st.button('Prepare local draft',type='primary',key='ecos_prepare'):
        try: st.session_state['ecos_draft'] = make_draft(name,sponsor,purpose,selected.key,tier)
        except ValueError as e:st.error(str(e))
    draft=st.session_state.get('ecos_draft')
    if draft:
        st.warning('Local preview only. No API write, approval or Trust Layer registration has occurred.')
        st.json(draft)
        st.download_button('Download draft JSON',json.dumps(draft,indent=2),
                           file_name='decision-os-ecosystem-draft.json',mime='application/json',key='ecos_download')


def _radar(api: Callable | None):
    st.markdown('#### Enterprise Decision Radar')
    if api is None:
        st.info('Connect the existing authenticated API adapter to display the read-only executive queue.')
        return
    decisions, assumptions, krs, packets, error = safe_source_bundle(api)
    if error: st.warning('Partial data: ' + error + '. Missing source data is not treated as healthy.')
    st.caption('Signals are derived from authorized API results. No autonomous actions or monetary leakage claims.')
    a,b,c = st.columns(3)
    a.metric('Decisions visible',len(decisions))
    b.metric('Invalidated assumptions',sum(str(x.get('validation_status')).lower()=='invalidated' for x in assumptions))
    c.metric('Action packets awaiting review',sum(str(x.get('status')).lower()=='draft' for x in packets))
    if not decisions:
        st.info('No accessible decisions or the decision API is unavailable.')
        return
    chosen=st.selectbox('Inspect decision',decisions,format_func=lambda x:str(x.get('title') or x.get('id')),
                        key='ecos_decision')
    did=str(chosen.get('id'))
    links=[]
    try: links=api('GET','/v1/strategy/decision-links',quiet=True) or []
    except Exception:pass
    krids={str(x.get('key_result_id')) for x in links if str(x.get('decision_id'))==did}
    subset=[kr for kr in krs if str(kr.get('id')) in krids]
    signals=risk_signals(assumptions,subset,packets,decision_id=did)
    if not signals:
        st.info('No issues detected in the available records. This does not establish portfolio health or evidence completeness.')
    for item in signals[:30]:
        with st.container(border=True):
            st.markdown(f'**{item["type"]} · {item["title"]}**')
            st.caption(item['reason'] + (' · Record '+item['ref'] if item['ref'] else ''))
    st.caption('Value at risk: not calculated. Requires finance-approved baseline, accrual/realization method, period, and measured exposure.')


def render_ecosystem_intelligence(api: Callable | None = None, navigate: Callable | None = None):
    _styles()
    st.markdown('<div class="ecos-hero"><h1>Enterprise Ecosystem Intelligence</h1>'
                '<p>Vendor-neutral decision context · Evidence integrity · Governed intervention design</p></div>',
                unsafe_allow_html=True)
    tabs=st.tabs(['Ecosystem Matrix','Decision Flow','Decision Radar','Deployment Review','Integration Connections','Evidence Advisor'])
    with tabs[0]:_matrix()
    with tabs[1]:_flow()
    with tabs[2]:_radar(api)
    with tabs[3]:_route()
    with tabs[4]:_connections()
    with tabs[5]:_advisor(api)
    st.caption('All risk mappings are advisory and require human validation. No connected vendor feed, policy approval, compliance certification, or financial reconciliation is implied.')


def _connections():
    """Connection-intent inventory; toggles never represent successful authentication."""
    st.subheader('Integration Connections')
    st.caption('Connection preferences are local to this browser session. They DO NOT authenticate, configure credentials, create connectors or receive telemetry.')
    for provider in PROVIDERS:
        with st.container(border=True):
            a,b=st.columns([3,1])
            with a:
                st.markdown(f'**{provider.name}**')
                st.caption('Signals sought: '+provider.signals)
            with b:
                enabled=st.toggle('Plan connection',key='ecos_connect_'+provider.key,help='Planning marker only, not a vendor API connection.')
            st.write('Status: **Not connected · no telemetry verified**'+(' · Configuration requested' if enabled else ''))
            if enabled:
                st.caption('Next: establish server-side OAuth/service identity, scoped permissions, tenant mapping, health checks and evidence provenance. No credentials accepted by this prototype.')


def _advisor(api):
    from ui.decision_operations import evidence_advisor, debt_signals, load_evidence
    st.subheader('Deterministic Ecosystem Evidence Advisor')
    st.caption('Answers only from accessible API record fields and references. Unsupported questions are refused. No LLM, no vendor data simulation.')
    if api is None:
        st.info('Authenticated API adapter unavailable.');return
    data, warnings = load_evidence(api)
    if warnings:st.warning('Partial evidence: '+'; '.join(warnings))
    selected=st.selectbox('Decision context',data['decisions'],format_func=lambda d:str(d.get('title') or d.get('id')),key='ecos_advisor_decision') if data['decisions'] else None
    if not selected:
        st.info('No authorized decision records available.');return
    did=str(selected.get('id'))
    a=[x for x in data['assumptions'] if str(x.get('decision_id'))==did]
    k=[x for x in data['krs'] if str(x.get('decision_id'))==did]
    p=[x for x in data['packets'] if str(x.get('decision_id'))==did]
    signals=debt_signals(a,k,p)
    with st.container():
        for msg in st.session_state.get('ecos_advisor_chat', [])[-10:]:
            with st.chat_message(msg['role']):st.markdown(msg['content'])
        query=st.chat_input('Ask: Which assumptions need attention?')
        if query:
            ans=evidence_advisor(query,signals,selected)
            history=st.session_state.setdefault('ecos_advisor_chat',[])
            history.extend([{'role':'user','content':query},{'role':'assistant','content':ans['answer']}])
            st.rerun()
