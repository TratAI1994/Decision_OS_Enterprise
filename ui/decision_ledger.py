"""Decision OS — Decision Infrastructure / Evidence Graph.
Read-only authenticated ledger. All snapshots are sourced from the R5.6 API;
local digest checks are integrity demonstrations, NOT approval signatures.
"""
from __future__ import annotations
import hashlib
import html
import json
from dataclasses import dataclass
from typing import Any, Callable

try:
    import streamlit as st
except ImportError:  # pure logic usable without Streamlit
    st = None


@dataclass(frozen=True)
class EvidenceLink:
    claim_id: str
    claim: str
    source_id: str
    source_system: str
    evidence_status: str  # missing | submitted | reviewer_attested | verified
    verifier: str | None = None
    captured_at: str | None = None
    limitations: str = ''


def canonical_digest(record: dict) -> str:
    """Content digest: tamper detection only when checked against a trusted anchor."""
    payload = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def version_tag(major: int, minor: int) -> str:
    if major < 1 or minor < 0:
        raise ValueError('Invalid version')
    return f'v{major}.{minor}'


def next_draft_version(tag: str) -> str:
    if not tag.startswith('v'):
        raise ValueError('Expected vMAJOR.MINOR')
    major, minor = (int(x) for x in tag[1:].split('.'))
    return version_tag(major, minor + 1)


def evidence_coverage(links: list[EvidenceLink]) -> tuple[int, int]:
    """Count source-backed attested/verified links; never infer confidence %."""
    return sum(x.evidence_status in ('reviewer_attested', 'verified') for x in links), len(links)


def normalize_items(result: Any) -> list[dict]:
    if isinstance(result, list):
        return [x for x in result if isinstance(x, dict)]
    if isinstance(result, dict):
        for k in ('items', 'decisions', 'evaluations', 'results'):
            if isinstance(result.get(k), list):
                return normalize_items(result[k])
    return []


def get_value(record: dict, *fields: str, default='Not recorded'):
    for field in fields:
        v = record.get(field)
        if v not in ('', None):
            return v
    return default


def decision_graph_for_record(decision: dict, evaluation: dict | None = None) -> list[EvidenceLink]:
    """Only source actual attached claims; no fabricated supplier or ERP records."""
    links = []
    items = decision.get('evidence') or decision.get('evidence_links') or []
    if isinstance(items, list):
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            status = str(item.get('status') or 'submitted').lower()
            # Never elevate 'verified' absent reviewer identity and immutable source id.
            source_id = str(item.get('source_id') or item.get('id') or '')
            verifier = str(item.get('verified_by') or '')
            if status == 'verified' and not (source_id and verifier):
                status = 'submitted'
            if status not in {'missing', 'submitted', 'reviewer_attested', 'verified'}:
                status = 'submitted'
            links.append(EvidenceLink(
                claim_id=str(item.get('claim_id') or f'claim-{i+1}'),
                claim=str(item.get('claim') or decision.get('title') or 'Unspecified claim'),
                source_id=source_id,
                source_system=str(item.get('source_system') or item.get('source') or 'Unspecified'),
                evidence_status=status, verifier=verifier or None,
                captured_at=item.get('captured_at'),
                limitations=str(item.get('limitations') or '')
            ))
    return links


def _safe(x) -> str:
    return html.escape(str(x), quote=True)


def _call(api: Callable, method: str, path: str, body=None):
    try:
        return api(method, path, body) if body is not None else api(method, path)
    except Exception as ex:
        return {'_error': type(ex).__name__}


def _graph(links: list[EvidenceLink], title: str):
    if not links:
        st.info('No claim-to-source links available in the authorized response. Evidence coverage and confidence are not assessable.')
        st.graphviz_chart('digraph G { rankdir=LR; a [label="Decision",shape=box]; b [label="Evidence not available",shape=box,style=dashed]; a -> b [style=dashed]; }', use_container_width=True)
        return
    # Graphviz identifier safety: graph nodes are internal indices only; labels escaped.
    import graphviz
    graph = graphviz.Digraph(graph_attr={'rankdir':'LR','bgcolor':'transparent','fontname':'Arial'})
    graph.node('decision',title[:90],shape='box',style='rounded,filled',fillcolor='#F3F3EF')
    for i, x in enumerate(links):
        graph.node(f'claim{i}', x.claim[:90],shape='box')
        graph.node(f'source{i}', f'{x.source_system}: {x.source_id or "No source ID"}\n{x.evidence_status}',shape='box',style='rounded')
        graph.edge('decision',f'claim{i}')
        graph.edge(f'claim{i}',f'source{i}',style='solid' if x.evidence_status == 'verified' else 'dashed')
    st.graphviz_chart(graph, use_container_width=True)


def render(api: Callable | None = None, navigate=None):
    if st is None:
        raise RuntimeError('Install Streamlit to display this workspace')
    st.title('Decision Infrastructure')
    st.caption('GitHub-style decision ledger · R5.6 source records · Evidence lineage · Explicit integrity boundaries')
    st.info('Source of truth: authenticated Decision OS API. A SHA-256 digest is not a signature and this UI cannot cryptographically lock or approve a record.')
    if api is None:
        st.warning('No authenticated API adapter supplied; no records are available.')
        return

    decisions_result = _call(api,'GET','/v1/intelligence/decisions')
    if isinstance(decisions_result, dict) and decisions_result.get('_error'):
        st.error('Decision API unavailable. No fallback or fabricated decisions displayed.')
        return
    decisions = normalize_items(decisions_result)
    query = st.text_input('Search decision ID, name or owner',placeholder='Search authorized records…',key='ledger_search')
    if query:
        term = query.casefold()
        decisions = [x for x in decisions if term in ' '.join(str(x.get(k,'')) for k in ('id','title','owner','decision_owner')).casefold()]
    if not decisions:
        st.info('No authorized decisions match this query.')
        return

    ids = {str(d.get('id')):d for d in decisions if d.get('id') is not None}
    if not ids:
        st.warning('Decision records have no stable server-generated IDs. Cannot provide a trustworthy ledger.')
        return
    selected_id=st.selectbox('Decision',options=list(ids),format_func=lambda x:f'{str(ids[x].get("title") or "Untitled")} · {x}',key='ledger_decision')
    d=ids[selected_id]
    col1,col2,col3=st.columns(3)
    col1.metric('Decision ID',str(selected_id)[:26]);col2.metric('Owner',str(get_value(d,'owner','decision_owner','created_by'))[:35]);col3.metric('Status',str(get_value(d,'status'))[:30])
    tabs=st.tabs(['Frozen context','Version history','Evidence graph','Review contract'])
    with tabs[0]:
        st.subheader('Approval-time decision context')
        st.write('Recommendation:',get_value(d,'approved_recommendation','recommendation','title'))
        st.write('Review schedule:',get_value(d,'review_schedule','next_review_at'))
        # Do not imply current metadata is an approval-time snapshot.
        frozen=d.get('approval_snapshot') or d.get('frozen_snapshot')
        if isinstance(frozen,dict):
            st.success('Snapshot present in decision response; verify server-side signature and original approval event before trusting historical integrity.')
            st.json(frozen)
        else:
            st.warning('Approval-time snapshot not supplied. Current fields are NOT a frozen historical record.')
        criteria=d.get('kill_criteria') or (frozen or {}).get('kill_criteria') if isinstance(frozen,dict) else d.get('kill_criteria')
        st.subheader('Predeclared kill criteria')
        if criteria: st.json(criteria)
        else: st.warning('No verifiable preapproval kill criteria attached. Post-hoc thresholds cannot be presented as original conditions.')
        st.caption('Reviewer-bound approval must be performed by the existing Trust Layer, not through this page.')
    with tabs[1]:
        st.subheader('Evaluations and version history')
        result=_call(api,'GET',f'/v1/decision-evaluation/decisions/{selected_id}')
        if isinstance(result,dict) and result.get('_error'):
            st.warning('Evaluation API not available. No history invented.')
            evaluations=[]
        else:
            evaluations=normalize_items(result)
            if not evaluations and isinstance(result,dict) and result.get('id'): evaluations=[result]
        if evaluations:
            for e in evaluations:
                lock=(e.get('locked_at') or e.get('status')=='locked' or e.get('state')=='locked')
                with st.expander(f"{get_value(e,'evaluation_version','version',default='Unversioned')} · {'Locked evaluation' if lock else 'Draft'} · {get_value(e,'id')}"):
                    st.json(e)
        else: st.info('No readable R5.6 evaluations supplied for this decision.')
        current=str(get_value(d,'version',default=''))
        st.caption(f'Proposal only: edit current v{current} by drafting a subsequent version. Historical approval records must never be rewritten.' if current else 'No verified version supplied; version-up requires backend support.')
        if st.button('Prepare amendment draft',key='ledger_amend'):
            st.session_state['ledger_amend_preview']={'base_decision_id':selected_id,'base_version':current or None,'status':'LOCAL_PREVIEW_NOT_SUBMITTED','change_reason':'Requires human input, backend validation and independent approval'}
        if st.session_state.get('ledger_amend_preview',{}).get('base_decision_id')==selected_id:
            reason=st.text_area('Reason for proposed amendment',key='ledger_reason')
            preview={**st.session_state['ledger_amend_preview'],'change_reason':reason.strip(),'no_database_write':True}
            st.json(preview)
            st.download_button('Download draft amendment',json.dumps(preview,indent=2),file_name='decision_amendment_preview.json',mime='application/json')
    with tabs[2]:
        st.subheader('Claim → Evidence → Verifier')
        links=decision_graph_for_record(d)
        _graph(links,str(d.get('title') or selected_id))
        reviewed,total=evidence_coverage(links)
        st.caption(f'Attested/verified source links: {reviewed}/{total} supplied links. This is a coverage count, not a confidence score.')
        if links:
            st.dataframe([{'Claim':x.claim,'Source':x.source_system,'Source ID':x.source_id or 'Missing','Status':x.evidence_status,'Verifier':x.verifier or 'Missing','Limitations':x.limitations or 'Not stated'} for x in links],use_container_width=True,hide_index=True)
        st.warning('No global confidence score is calculated: calibration, provenance and verified evidence are prerequisites.')
    with tabs[3]:
        st.subheader('Integrity verification contract')
        st.write('**Required proof:** reviewer identity, authorization, approval event, rubric version, evidence-content digests, WORM/append-only retention and an externally anchored signature.')
        payload={'decision_id':selected_id,'source':'authorized_api_response','decision_record':d}
        digest=canonical_digest(payload)
        st.code(digest,language='text')
        st.caption('Digest of this fetched response (computed in UI). It changes if response fields change; it is NOT a server-trusted approval hash.')
        if st.button('Verify against trusted server anchor',disabled=True,help='Disabled until the backend offers a signed snapshot verification endpoint'):
            pass
        st.info('Cryptographic lock: NOT VERIFIED. Independent reviewer sign-off and server-side tamper-evident storage are mandatory.')
    st.divider()
    st.caption('All data is scoped to the records returned by the authenticated API. No synthetic customers, scores, signed approvals or financial results are created.')

if __name__ == '__main__':
    st.set_page_config(page_title='Decision Infrastructure',layout='wide')
    render()
