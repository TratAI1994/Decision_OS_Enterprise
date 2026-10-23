"""R8 Outcome Economics — guided AWS-console-inspired workspace.

Presentation and deterministic help only. Authoritative finance and tenant
controls remain in FastAPI; no client-side elevation or simulated approvals.
"""
from __future__ import annotations
import json
import re
import secrets
from decimal import Decimal, InvalidOperation
from typing import Any
import streamlit as st

STAGES = ("Overview", "1 · Plan", "2 · Measure", "3 · Finance review", "4 · Audit trail")
HELP = {
    "Overview": {
        "purpose": "See what is known about this decision's financial value and what is still missing.",
        "questions": ("Why is variance withheld?", "What does finance-attested mean?", "Does savings variance prove AI caused the change?"),
    },
    "1 · Plan": {
        "purpose": "Record the expected net benefit, currency, period, methodology, and business-case reference. This is an append-only baseline, not necessarily an original approval-time snapshot.",
        "questions": ("What amount should I enter?", "What is an acceptable evidence reference?", "Can I edit the plan later?"),
    },
    "2 · Measure": {
        "purpose": "Record a project team's observed benefit with measurement source and attribution limitations. This is a claim, not a finance-certified saving.",
        "questions": ("How do I measure realized savings?", "Which attribution method should I select?", "Can the team-reported number be called verified?"),
    },
    "3 · Finance review": {
        "purpose": "A separately authenticated Finance Controller reconciles a specific claim against financial records. The reporter cannot approve their own claim.",
        "questions": ("Who can perform finance attestation?", "What does Finance check?", "Does the attestation validate the GL automatically?"),
    },
    "4 · Audit trail": {
        "purpose": "Inspect append-only benefit events, actors, record hashes, and integrity limitations. A local hash chain does not establish external immutability.",
        "questions": ("Can an administrator tamper with this history?", "How is the chain checked?", "What should an auditor export?"),
    },
}


def explain(stage: str, question: str, facts: dict[str, Any] | None = None) -> str:
    """Bounded page-specific decision support. No LLM, no external lookups."""
    q = question.strip().lower()
    data = facts or {}
    if not q:
        return "Enter a question about the current step. I will explain only this workflow and the records currently available."
    if any(w in q for w in ("caus", "ai caused", "attribution")):
        return ("A difference from plan does not establish causality. Record the attribution method and confounders. "
                "Experimental and quasi-experimental claims require a separately reviewed study; selecting a label alone is insufficient.")
    if any(w in q for w in ("withheld", "variance", "pending")):
        status = "Finance attestation exists." if data.get("finance_verified") is not None else "No finance attestation is recorded."
        return status + " Verified variance appears only after an independently authorized finance attestation."
    if any(w in q for w in ("gl", "erp", "automatic", "reconcil", "finance check", "finance checks")):
        return ("Finance should check financial period, currency, general-ledger or FP&A evidence, adjustments, double counting, and exclusions. "
                "This R8 service records the controller's attestation and source pointer; it does NOT automatically query or validate ERP/GL records.")
    if any(w in q for w in ("who", "role", "controller", "permission", "approv")):
        return "Only a separately authenticated identity with the finance role can attest. The person who reported the claim cannot attest it. The FastAPI service enforces these rules."
    if any(w in q for w in ("evidence", "reference", "source", "auditor", "export")):
        return "Use a stable source identifier such as forecast revision, ledger posting or report reference, with period, owner, and methodology. Export the event history for review; a reference alone is not independently verified evidence."
    if any(w in q for w in ("edit", "change", "amend", "correct")):
        return "Historical baselines are append-only in this R8 stream. Corrections require a separately governed version/reversal workflow; do not overwrite prior events."
    if any(w in q for w in ("tamper", "hash", "chain", "immutab", "cryptograph")):
        return "The API checks event hashes and ordering. This detects inconsistency relative to the local chain, but privileged database actors may rewrite an unanchored stream. External signing and independent anchoring are not part of R8."
    if any(w in q for w in ("amount", "saving", "benefit", "roi", "measure")):
        return "Enter the net benefit for the selected financial period in the specified currency. Document costs, exclusions, baseline and collection method. Do not enter an ROI percentage into a monetary amount field."
    if stage == "1 · Plan":
        return "Start with the agreed financial period and an evidence-backed business case. Do not backdate or pretend this stream is the original decision-approval snapshot."
    if stage == "2 · Measure":
        return "Measure the observed benefit against the baseline and list known confounders. This step records a self-reported claim only."
    if stage == "3 · Finance review":
        return "An independent finance-role identity must perform reconciliation and submit evidence references. No UI control can bypass this gate."
    if stage == "4 · Audit trail":
        return "Check event order, actor IDs, timestamp and chain integrity. Missing signatures or external anchoring must be disclosed."
    return "Select a specific workflow step to get contextual guidance. This advisor cannot certify evidence, change records, or infer business causality."


def progress(plan: dict | None, claims: list, verifications: list) -> tuple[int, str]:
    if verifications:
        return 3, "Finance-attested — verify source references and attribution separately"
    if claims:
        return 2, "Awaiting independent Finance Controller review"
    if plan:
        return 1, "Expected value recorded; next report observed benefit"
    return 0, "Start by recording the business-case baseline"


def validate_amount(value: str) -> str | None:
    s = value.strip()
    if not re.fullmatch(r"[+-]?\d+(?:\.\d{1,2})?", s):
        return "Enter a decimal monetary amount (e.g. 12000000.00), with at most two decimal places."
    try:
        d = Decimal(s)
        if not d.is_finite() or abs(d) > Decimal("9999999999999"):
            return "Amount must be finite and within the supported monetary range."
    except InvalidOperation:
        return "Amount is not a valid decimal."
    return None


def _styles():
    st.markdown('''<style>
    .r8-hero {padding:1.35rem 1.5rem;background:linear-gradient(110deg,#182331,#27384c);color:#fff;border-radius:13px;margin:0 0 1rem;}
    .r8-hero h2 {color:#fff!important;margin:0;font-size:1.55rem;font-weight:650;}
    .r8-hero p {color:#d6e1ed!important;font-size:.93rem;margin:.4rem 0 0;}
    .r8-step {border:1px solid rgba(130,146,163,.24);border-radius:9px;padding:.7rem 1rem;min-height:72px;}
    .r8-step strong {display:block;font-size:.87rem;}
    .r8-step small {font-size:.74rem;opacity:.75;}
    .r8-subtle {font-size:.86rem;opacity:.85;}
    @media(max-width:780px){.r8-hero{padding:1rem;} .r8-hero h2{font-size:1.25rem;}}
    </style>''', unsafe_allow_html=True)


def _help_panel(stage: str, summary: dict):
    with st.container(border=True):
        st.markdown("#### Screen guide · " + stage)
        st.caption(HELP[stage]["purpose"])
        st.markdown("**Ask this step's Copilot**")
        key = "r8_help_question_" + re.sub(r"\W", "_", stage)
        if key not in st.session_state:
            st.session_state[key] = ""
        for i, question in enumerate(HELP[stage]["questions"]):
            if st.button(question, key=f"r8_suggest_{key}_{i}", use_container_width=True):
                st.session_state[key] = question
        question = st.text_area("Your question", key=key, height=90, placeholder="Ask what to enter, what evidence is needed, or why the step is blocked...")
        if st.button("Explain this step", key="r8_answer_" + key, type="secondary", use_container_width=True):
            st.session_state["r8_answer"] = (stage, explain(stage, question, summary))
        answer = st.session_state.get("r8_answer")
        if answer and answer[0] == stage:
            st.info(answer[1])
        st.caption("Deterministic workflow guidance • Not an accounting certification or an LLM-generated claim")


def _metric(label, value, detail):
    with st.container(border=True):
        st.caption(label)
        st.markdown(f"### {value}")
        st.caption(detail)


def render(api, navigate=None):
    _styles()
    st.markdown('<div class="r8-hero"><h2>Outcome Economics · Value Realization</h2><p>From business case to Finance Controller attestation. Every amount has a status, source and accountable role.</p></div>', unsafe_allow_html=True)
    st.caption("DECISION INFRASTRUCTURE / OUTCOME ECONOMICS / R8 FINANCE WORKFLOW")
    with st.expander("Before you begin · 60-second orientation", expanded=False):
        st.markdown("**Project sponsor:** records expected value and benefit evidence. **Finance Controller:** independently reconciles the benefit. **Executive:** reads verified-versus-expected variance after attestation. **Auditor:** inspects event lineage. No team-reported claim is automatically finance-verified.")
    ds = api('GET', '/v1/intelligence/decisions', quiet=True)
    if isinstance(ds, dict): ds = ds.get('items', ds.get('decisions', []))
    if not isinstance(ds, list):
        st.error("Authorized decision list unavailable. Check connection and tenant permissions. No demonstration values will be substituted.")
        return
    opts = {f"{str(d.get('title') or d.get('name') or d.get('id'))[:75]} · {d['id']}": d['id'] for d in ds if isinstance(d, dict) and d.get('id')}
    if not opts:
        st.info("No authorized decisions found. Create a decision in the Strategy or Decision Ledger workspace first.")
        return
    did = opts[st.selectbox("Decision to reconcile", list(opts), key="r8_guided_choice")]
    payload = api('GET', f'/v1/outcome-economics/{did}', quiet=True)
    if not isinstance(payload, dict):
        st.error("The R8 finance service or migration is unavailable. Cannot reconcile without the authoritative API.")
        return
    state = payload.get('state') or {}
    plan = state.get('plan')
    claims = state.get('claims') or []
    verifications = state.get('verifications') or []
    summary = payload.get('summary') or {}
    events = payload.get('events') or []
    integrity = payload.get('integrity') or {}
    if not integrity.get('consistent'):
        st.error("Event-chain integrity check failed or could not be verified. Financial write actions are blocked. Investigate the backend event stream.")
        return
    count, stage_status = progress(plan, claims, verifications)
    with st.container(border=True):
        a,b = st.columns([1,3])
        a.metric("Stages completed", f"{count}/3")
        b.markdown("**Current status**")
        b.write(stage_status)
        st.progress(count/3)
        stages = ["Set expectation", "Report outcome", "Finance attests"]
        cols = st.columns(3)
        for idx,(col,label) in enumerate(zip(cols,stages)):
            col.markdown(f"{'✓' if count>idx else '○'} **{label}**")
    stage = st.radio("Workspace step", STAGES, horizontal=True, key="r8_stage", label_visibility="collapsed")
    main, side = st.columns([2.05, 1], gap="large")
    with main:
        if stage == "Overview":
            st.subheader("Financial value at a glance")
            currency = summary.get('currency') or (plan or {}).get('currency_code') or '—'
            m1,m2 = st.columns(2)
            with m1: _metric("Expected · business case",f"{summary.get('expected')} {currency}" if plan and summary.get('expected') is not None else "Not recorded", "Source: baseline reference / methodology")
            with m2: _metric("Observed · project report",f"{summary.get('self_reported')} {currency}" if summary.get('self_reported') is not None else "Not reported", "Source: team measurement — not finance-verified")
            m3,m4=st.columns(2)
            with m3: _metric("Finance-attested",f"{summary.get('finance_verified')} {currency}" if summary.get('finance_verified') is not None else "Pending", "Independent controller attestation, not direct ERP validation")
            with m4: _metric("Verified variance",f"{summary.get('variance')} {currency}" if summary.get('variance') is not None else "Withheld", "Shown only after finance attestation")
            st.write("**Financial period:**", summary.get('period') or 'Not available')
            st.write("**Attribution method:**", summary.get('attribution') or 'Unknown')
            if summary.get('variance') is None: st.warning("No finance-attested variance is available. Finish the Finance review step to establish the reconciled figure.")
            st.info("A shortfall against a forecast is not proof an AI initiative caused the shortfall. Evaluate attribution separately.")
            st.markdown("#### Next action")
            next_stage = STAGES[min(count + 1,3)]
            if st.button("Continue to " + next_stage, type="primary"):
                st.session_state['r8_stage']=next_stage
                st.rerun()
        elif stage == "1 · Plan":
            st.subheader("Establish the expected benefit")
            st.caption("Required: monetary benefit, fiscal period, economic methodology and baseline evidence reference.")
            if plan:
                st.success("An expected benefit event is recorded. This stage cannot silently overwrite it.")
                st.json(plan, expanded=False)
            else:
                expected=st.text_input("Expected net benefit", placeholder="12000000.00",key="r8_expected",help="Net monetary amount, not an ROI percentage")
                col1,col2=st.columns(2)
                currency=col1.selectbox("Currency",['INR','USD','EUR','GBP','SGD','AUD'],key='r8_currency')
                period=col2.text_input("Financial period · YYYY-MM",placeholder="2026-12",key='r8_period')
                method=st.text_area("Forecast methodology and assumptions",placeholder="Business case method, costs, exclusions, expected adoption...",key='r8_method')
                baseline=st.text_input("Baseline forecast / evidence reference",key='r8_baseline')
                errs=[e for e in [validate_amount(expected) if expected else 'Expected amount is required.', 'Enter a valid YYYY-MM period.' if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])",period.strip()) else None,'Methodology needs at least 12 characters.' if len(method.strip())<12 else None,'Evidence reference needs at least 3 characters.' if len(baseline.strip())<3 else None] if e]
                if errs:st.caption("Required before recording: " + " ".join(errs))
                if st.button("Record expected baseline",disabled=bool(errs),type="primary"):
                    result=api('POST','/v1/outcome-economics/plan',{'decision_id':did,'expected_amount':expected.strip(),'currency_code':currency,'period':period.strip(),'methodology':method.strip(),'baseline_ref':baseline.strip(),'request_id':secrets.token_hex(20)})
                    if isinstance(result,dict) and result.get('id'):st.success('Baseline event appended.');st.rerun()
        elif stage == "2 · Measure":
            st.subheader("Record observed value — self-reported")
            if not plan:st.warning("Prerequisite missing: first record expected value in step 1.")
            elif verifications:st.info("Finance has attested this period. Further corrections need a governed amendment process.")
            else:
                st.caption(f"Selected baseline: {plan.get('period')} · {plan.get('currency_code')}")
                reported=st.text_input('Observed net benefit',placeholder='8700000.00',key='r8_reported')
                method=st.text_area('Measurement methodology',key='r8_measure_method')
                evidence=st.text_input('Measurement source reference',key='r8_measure_evidence')
                attr=st.selectbox('Attribution method',['unknown','estimated','correlational','quasi_experimental','experimental'],key='r8_attribution')
                notes=st.text_area('Confounders / limitations',key='r8_confounders',help='Do not imply causality without reviewed study design.')
                errs=[e for e in [validate_amount(reported) if reported else 'Observed amount required.','Measurement method needs detail.' if len(method.strip())<12 else None,'A source reference is required.' if len(evidence.strip())<3 else None] if e]
                if errs:st.caption('Required before submission: '+ ' '.join(errs))
                if st.button('Append self-reported outcome',type='primary',disabled=bool(errs)):
                    result=api('POST',f'/v1/outcome-economics/{did}/report',{'period':plan['period'],'reported_amount':reported.strip(),'measurement_method':method.strip(),'source_ref':evidence.strip(),'attribution_method':attr,'attribution_notes':notes.strip(),'expected_seq':len(events),'request_id':secrets.token_hex(20)})
                    if isinstance(result,dict) and result.get('id'):st.success('Self-reported claim appended. Finance review required.');st.rerun()
        elif stage == "3 · Finance review":
            st.subheader("Finance Controller reconciliation")
            st.warning('Authenticated **finance** role is required. A project reporter cannot attest their own claim. Server enforces both rules.')
            if not claims: st.info('Prerequisite missing: record an observed claim in step 2.')
            elif verifications:
                st.success('A Finance Controller attested this claim. The GL reference remains an attestation, not an independently retrieved ERP record.')
                st.json(verifications[-1],expanded=False)
            else:
                claim=claims[-1]
                st.write('**Claim event:**',claim.get('event_id','Unavailable'))
                st.write('**Reported by:**',claim.get('actor_id','Unavailable'))
                if claim.get('reported_cents') is not None:st.write('**Self-reported amount:**',str(Decimal(str(claim['reported_cents']))/100),plan.get('currency_code',''))
                verified=st.text_input('Independently reconciled net amount',key='r8_verified',placeholder='8700000.00')
                method=st.text_area('Reconciliation method / accounting treatment',key='r8_reconcile_method')
                reference=st.text_input('General Ledger / ERP / FP&A source reference',key='r8_gl')
                notes=st.text_area('Adjustments, root-cause hypotheses and limitations',key='r8_finance_notes')
                acknowledged=st.checkbox('I independently reconciled the reported benefit against financial evidence.',key='r8_attestation')
                errs=[e for e in [validate_amount(verified) if verified else 'Reconciled amount required.','Reconciliation method needs detail.' if len(method.strip())<12 else None,'GL / ERP source reference required.' if len(reference.strip())<3 else None,'Controller acknowledgment required.' if not acknowledged else None] if e]
                if errs:st.caption('Required before submission: ' + ' '.join(errs))
                if st.button('Submit independent finance attestation',disabled=bool(errs),type='primary'):
                    result=api('POST',f'/v1/outcome-economics/{did}/finance-attest',{'claim_event_id':claim['event_id'],'verified_amount':verified.strip(),'reconciliation_method':method.strip(),'financial_source_ref':reference.strip(),'notes':notes.strip(),'expected_seq':len(events),'confirmation':'I independently reconciled this benefit against financial evidence.','request_id':secrets.token_hex(20)})
                    if isinstance(result,dict) and result.get('id'):st.success('Independent finance attestation appended.');st.rerun()
        else:
            st.subheader('Financial event and provenance trail')
            if events:
                st.dataframe([{'Seq':e.get('seq'),'Event':e.get('event_type'),'UTC timestamp':e.get('occurred_at'),'Actor':e.get('actor_id'),'Digest':(e.get('event_hash') or '')[:16]+'…'} for e in events],hide_index=True,use_container_width=True)
                st.download_button('Export event history (JSON)',json.dumps(payload,indent=2,default=str),file_name=f'outcome_{did}.json',mime='application/json')
            else:st.info('No benefit events recorded for this decision.')
            st.write('**Event chain:** locally consistent')
            st.code((integrity.get('head_hash') or 'Not available'),language=None)
            st.caption('The event chain is not externally signed or anchored. Privileged database changes remain a risk.')
    with side:
        _help_panel(stage,summary)
        with st.container(border=True):
            st.markdown('#### Who does what?')
            st.caption('Sponsor: business case and observed value. Controller: independent reconciliation. Auditor: source references and history. The API, not this page, enforces identity and separation of duties.')
            st.markdown('#### Data confidence')
            st.caption('Self-reported ≠ finance-attested ≠ independently ERP-verified. None of these by themselves proves causality.')
