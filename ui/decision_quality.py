"""Decision OS — read-only Decision Quality & Assumption Intelligence.

All data comes from existing tenant-authorized FastAPI endpoints. Local scenario
inputs are expressly hypothetical and never saved as business evidence.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import streamlit as st

WEIGHTS = {'Evidence': .20, 'Economics': .15, 'Risk': .15,
           'Counterfactual': .15, 'Alternatives': .10,
           'Accountability': .15, 'Measurement': .10}

@dataclass(frozen=True)
class QualityResult:
    score: float | None
    covered_weight: float
    missing: tuple[str, ...]
    details: tuple[tuple[str, float | None, float], ...]
    governance_warning: bool


def finite_score(value: Any) -> float | None:
    """Normalize only pre-assessed control results, not narrative text."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and 0 <= result <= 100 else None


def quality_score(controls: dict[str, float | None], approvals_complete: bool | None = None) -> QualityResult:
    """Weighted process-rigor score. Absent assessments remain unknown.

    This is not a business outcome score or an independent control audit.
    We do not extrapolate incomplete assessment into a misleading percentage.
    """
    details = tuple((name, finite_score(controls.get(name)), weight) for name, weight in WEIGHTS.items())
    missing = tuple(name for name, value, _ in details if value is None)
    coverage = sum(weight for _, value, weight in details if value is not None)
    result = round(sum(value * weight for _, value, weight in details), 1) if not missing else None
    return QualityResult(result, round(coverage, 3), missing, details, approvals_complete is not True)


def assessment_state(expected: float | None, actual: float | None, *,
                     observed_at: str | None, stale_after_days: int | None,
                     evidence_ref: str | None = None,
                     reviewed_status: str = 'unknown',
                     now: datetime | None = None) -> dict[str, Any]:
    """Never infer support or invalidation from an arbitrary variance threshold.

    A reviewed status is reported separately from metric divergence, and
    freshness trumps any apparent target attainment.
    """
    now = now or datetime.now(UTC)
    outcome = {'state': 'NOT MEASURED', 'variance_pp': None, 'deviation_pct': None,
               'reviewed_status': reviewed_status, 'basis': 'No verified evaluation of the assumption'}
    if expected is None or actual is None or not evidence_ref or not observed_at:
        return outcome
    try:
        dt = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        age_days = (now - dt).total_seconds() / 86400
        if stale_after_days is None or stale_after_days <= 0 or age_days > stale_after_days:
            outcome.update(state='STALE', basis='Measurement stale or freshness policy undefined')
            return outcome
        delta = float(actual) - float(expected)
        if not all(map(math.isfinite, [delta, float(expected), float(actual)])):
            return outcome
        outcome.update(state='OBSERVED — HUMAN REVIEW REQUIRED',
                       variance_pp=round(delta, 2),
                       deviation_pct=round(abs(delta) / abs(float(expected)) * 100, 1) if expected else None,
                       basis='Difference alone does not establish whether an assumption is invalidated')
        return outcome
    except (ValueError, TypeError, OverflowError):
        return outcome


def fetch_context(api: Callable, decision_id: str) -> dict[str, Any]:
    """Existing endpoints enforce tenant scope. Do not pass tenant IDs from UI."""
    decisions = api('GET', '/v1/intelligence/decisions', quiet=True) or []
    if not isinstance(decisions, list):
        return {'error': 'Decision records unavailable'}
    decision = next((d for d in decisions if str(d.get('id')) == str(decision_id)), None)
    if not decision:
        return {'error': 'Selected decision not available to this identity'}
    assumptions = api('GET', '/v1/strategy/assumptions', quiet=True) or []
    links = api('GET', '/v1/strategy/decision-links', quiet=True) or []
    krs = api('GET', '/v1/strategy/key-results', quiet=True) or []
    packets = api('GET', '/v1/decisions-governed/packets', quiet=True) or []
    if not all(isinstance(x, list) for x in (assumptions, links, krs, packets)):
        return {'error': 'Incomplete API response; cannot assess decision'}
    kr_ids = {str(x.get('key_result_id')) for x in links if str(x.get('decision_id')) == str(decision_id)}
    return {'decision': decision,
            'assumptions': [x for x in assumptions if str(x.get('decision_id')) == str(decision_id)],
            'krs': [x for x in krs if str(x.get('id')) in kr_ids],
            'packets': [x for x in packets if str(x.get('decision_id')) == str(decision_id)]}


def render(api: Callable, navigate: Callable | None = None) -> None:
    st.markdown('''<div class="hero"><div class="eyebrow">DECISION INTELLIGENCE · R5.6 FOUNDATION</div>
    <h1>Decision Quality & Assumption Intelligence</h1><p>Is the decision well-supported? Are its assumptions holding? What needs human review?</p></div>''', unsafe_allow_html=True)
    st.caption('READ ONLY · Authenticated FastAPI records · No simulated observations presented as facts · No autonomous approvals')
    decisions = api('GET', '/v1/intelligence/decisions', quiet=True) or []
    if not isinstance(decisions, list):
        st.error('Decision API returned an unexpected response.'); return
    if not decisions:
        st.info('No authorized decisions available. Create a Decision in the existing Ledger.'); return
    choice = st.selectbox('Executive decision', decisions, format_func=lambda d: str(d.get('title', 'Untitled decision')), key='dq_selected')
    context = fetch_context(api, str(choice['id']))
    if 'error' in context:
        st.error(context['error']); return
    decision, assumptions, krs, packets = (context[x] for x in ('decision','assumptions','krs','packets'))
    t_quality, t_assumption, t_queue, t_replay = st.tabs(['01 · Decision rigor', '02 · Assumption signals', '03 · Executive queue', '04 · Replay & learning'])
    with t_quality:
        st.subheader('Evidence & Process Quality')
        st.caption('Scores are withheld until required control assessments are available. A high score would measure process rigor, NOT whether the decision was strategically correct.')
        st.info('Verified control assessments are not exposed by current R5.5 APIs. Decision Quality: NOT ASSESSABLE.')
        result = quality_score({}, approvals_complete=None)
        left, right, third = st.columns(3)
        left.metric('Auditable process score', 'N/A')
        right.metric('Assessed rubric domains', f'{7-len(result.missing)} / 7')
        third.metric('Required approval assurance', 'Not verified')
        with st.expander('Seven-domain scoring rubric and formula'):
            st.dataframe([{'Domain': n, 'Weight': f'{w:.0%}', 'Verified control score': 'Not available'} for n,w in WEIGHTS.items()], hide_index=True, use_container_width=True)
            st.code('DQS = SUM(domain_weight × independently assessed_domain_score)\nOnly when every applicable domain is assessed; missing required review blocks readiness.')
        st.caption('Manual sliders have been retired. Structured rubric responses require evidence references and independent validation.')
        render_evaluation_workflow(api, str(choice['id']))
    with t_assumption:
        st.subheader('Living Assumption Register')
        if not assumptions:
            st.info('No assumptions recorded for this decision. Register testable assumptions in Strategy & Outcomes R5.5.')
        counts = {key: sum(str(x.get('validation_status','unknown')).lower()==key for x in assumptions) for key in ('supported','under_test','invalidated','unknown')}
        cols = st.columns(4)
        for col,(key,count) in zip(cols,counts.items()):col.metric(key.replace('_',' ').title(),count)
        for a in assumptions:
            status=str(a.get('validation_status','unknown')).upper()
            with st.container(border=True):
                st.markdown(f"**{a.get('statement', 'Untitled assumption')}**")
                st.caption(f"Reviewed status: {status} · Evidence: {a.get('evidence_ref') or 'NOT PROVIDED'} · Version: {a.get('version','?')}")
                if status=='INVALIDATED':st.error('Executive reassessment indicated. This status was recorded through the review workflow.')
                elif status in ('UNKNOWN','UNDER_TEST'):st.warning('Unresolved: do not treat this premise as proven.')
        st.divider()
        st.subheader('Linked outcome observations')
        if not krs: st.info('No Key Results are linked to this decision.')
        for kr in krs:
            measurement = kr.get('measurement') or {}
            obs = measurement.get('observation') or {}
            with st.container(border=True):
                st.markdown(f"**{kr.get('title','Key Result')}**")
                c1,c2,c3 = st.columns(3)
                c1.metric('Target', f"{kr.get('target','—')} {kr.get('unit','')}")
                c2.metric('Observed', f"{obs.get('value','Not measured')} {kr.get('unit','')}")
                c3.metric('Data state', measurement.get('state','UNKNOWN'))
                st.caption(f"Attribution: {obs.get('attribution','unattributed')} · Confidence: {obs.get('confidence','unknown')} · Source: {obs.get('source_ref','not recorded')}")
                if obs.get('limitations'):st.write('Limitations:',obs['limitations'])
                if measurement.get('state') in ('STALE','NO_DATA'): st.warning('Metric is stale or missing; no assumption validation can be inferred.')
                else:st.info('A measured KR is not automatically proof that any linked assumption is valid.')
        with st.expander('Variance analysis — hypothetical, never saved'):
            st.caption('Explore a scenario without creating fake telemetry or changing assumption status.')
            expected=st.number_input('Hypothetical expected improvement (%)',value=20.0,key='dq_hyp_expected')
            actual=st.number_input('Hypothetical observed improvement (%)',value=15.0,key='dq_hyp_actual')
            scenario=assessment_state(expected,actual,observed_at=datetime.now(UTC).isoformat(),stale_after_days=7,evidence_ref='SCENARIO-ONLY')
            st.metric('Scenario difference',f"{scenario['variance_pp']:+.1f} percentage points")
            st.info('Interpretation: ' + scenario['basis'])
    with t_queue:
        st.subheader('Requires Executive Attention')
        invalidated=[a for a in assumptions if str(a.get('validation_status','')).lower()=='invalidated']
        missing=[k for k in krs if (k.get('measurement') or {}).get('state') in ('NO_DATA','STALE')]
        if invalidated:st.error(f'{len(invalidated)} invalidated assumption(s) linked to this Decision. Review before continued investment.')
        if missing:st.warning(f'{len(missing)} Key Result(s) with stale or missing observations.')
        if not invalidated and not missing:st.info('No assumption invalidations or stale linked metrics found. This is NOT a certification of overall readiness.')
        st.caption(f'Action Packets visible to current identity: {len(packets)}. Reviewer authorization is enforced by the API, not by this screen.')
        if navigate and st.button('Open governed Action Center',key='dq_action_nav'):
            navigate('Decision Action Center')
    with t_replay:
        st.subheader('Decision Replay & Learning')
        st.write('**Current decision:**', decision.get('title','Untitled'))
        st.caption('Original evidence snapshots, formal historical review and causal attribution require the linked governance records. Current status is not a historical snapshot.')
        if navigate and st.button('Open Decision Replay & Memory',key='dq_replay_nav'):
            navigate('Decision Replay & Memory')
        st.download_button('Download sourced review summary (Markdown)', data=(
            f"# Decision Intelligence Review\n\nDecision: {decision.get('title','')}\nDecision ID: {decision.get('id','')}\n"
            f"\n## Assumptions\n" + '\n'.join(f"- [{a.get('validation_status','unknown')}] {a.get('statement','')} (evidence: {a.get('evidence_ref') or 'not provided'})" for a in assumptions) +
            "\n\n## Key Results\n" + '\n'.join(f"- {k.get('title','')}: {(k.get('measurement') or {}).get('state','UNKNOWN')}" for k in krs) +
            '\n\n## Quality assessment\nNot assessable without verified domain-level control evidence and independent approvals.\n'
        ).encode('utf-8'),file_name='decision-quality-readonly-review.md',mime='text/markdown',key='dq_export')


def render_evaluation_workflow(api: Callable, decision_id: str) -> None:
    """Server-scoped R5.6 contract; no client-side claims of immutable approval."""
    import uuid
    st.markdown('### Decision Evaluation Contract')
    rubric=api('GET','/v1/decision-evaluation/rubric',quiet=True)
    if not isinstance(rubric,dict) or not rubric.get('weights'):
        st.info('Evaluation Contract API not available. Install the R5.6 backend migration to enable reviewed snapshots.')
        return
    st.caption(f"Rubric {rubric['version']} · Seven evidence-based domains · Independent reviewer required")
    labels={'evidence':'Evidence completeness','economics':'Economic rigor','risk':'Risk analysis','counterfactual':'Counterfactual examined',
            'alternatives':'Options compared','accountability':'Named accountability','measurement':'Outcome measurement plan'}
    with st.expander('01 · Draft structured evaluation',expanded=True):
        with st.form(f'eval_form_{decision_id}'):
            answers={}
            for key,weight in rubric['weights'].items():
                st.markdown(f'**{labels.get(key,key.title())} · {weight}%**')
                state=st.selectbox('Assessment', ['missing','provisional','verified','not_applicable'],
                   format_func=lambda x:{'missing':'Missing evidence','provisional':'Provisional / awaiting verification',
                   'verified':'Evidence verified by preparer (requires independent review)','not_applicable':'Not applicable · justification required'}[x],
                   key=f'eval_state_{decision_id}_{key}')
                ref=st.text_input('Evidence reference / linked record ID',key=f'eval_ref_{decision_id}_{key}',
                    help='Use an actual source ID. An entered ID is not itself proof of independent verification.')
                explanation=st.text_input('Review rationale / limitation',key=f'eval_expl_{decision_id}_{key}')
                answers[key]={'state':state,'evidence_ref':ref.strip(),'explanation':explanation.strip()}
            submit=st.form_submit_button('Save draft for independent review',use_container_width=True)
        if submit:
            response=api('POST','/v1/decision-evaluation/draft',{'decision_id':decision_id,'answers':answers,'request_id':uuid.uuid4().hex},quiet=True)
            if isinstance(response,dict) and response.get('id'):
                st.success(f"Draft saved: {response['id']}. No decision was approved or locked.")
            else:st.error('Draft was not accepted. Verify fields, authentication and API logs.')
    st.markdown('### 02 · Independently reviewed evaluation snapshots')
    records=api('GET',f'/v1/decision-evaluation/decisions/{decision_id}',quiet=True)
    if not isinstance(records,list):
        st.warning('No authorized evaluation records returned.');return
    for record in records[:15]:
        state=record.get('status','unknown')
        with st.container(border=True):
            st.markdown(f"**{state.upper()} · {record.get('id','unknown')}**")
            st.caption(f"Author: {record.get('author')} · Reviewer: {record.get('reviewer') or 'Pending'} · Rubric: {record.get('rubric_version')}")
            if state=='locked':
                st.metric('Frozen process score',f"{record.get('score')}/100")
                st.caption('Decision Quality is frozen for this evaluation. Outcome observations remain dynamic. This is NOT approval of an AI deployment.')
                st.write('SHA-256 snapshot digest:',record.get('content_hash'))
                st.write('Integrity of serialized record:',record.get('hash_valid'))
                st.download_button('Export frozen evaluation JSON',data=__import__('json').dumps(record,indent=2,default=str),
                       file_name=f"evaluation-{record['id']}.json",mime='application/json',key=f"eval_export_{record['id']}")
            else:
                st.info('This draft is not frozen. An independent reviewer must verify the evidence, an approved Action Packet must exist, and a different reviewer must authorize the lock.')
                if st.button('Lock reviewed evaluation (server validation)',key=f"eval_lock_{record['id']}"):
                    result=api('POST',f"/v1/decision-evaluation/{record['id']}/lock",{
                      'expected_status':'draft',
                      'confirmation':'I have independently reviewed the evidence and accept the limitations.'},quiet=True)
                    if isinstance(result,dict) and result.get('status')=='locked':st.success('Server-locked snapshot recorded. Refresh to view.')
                    else:st.error('Lock rejected. Check independent reviewer identity, verified evidence and approved Action Packet. Never bypass this control.')
    st.caption('Frozen scores are application-level append-only; WORM storage, external anchoring, SSO and production audit hardening remain required.')
