"""Decision OS contextual, read-only, deterministic advisory layer.
No local DB access, LLM authority, persistence, or approval side effects.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import streamlit as st


@dataclass(frozen=True)
class Context:
    workspace: str
    tab: str
    purpose: str
    questions: tuple[str, ...]
    evidence: tuple[str, ...]

SPECIAL = {
 ('Strategic Twin Studio','Blast Radius'):('Analyze linked systems, distinguishing dependency from causality.',('What does blast radius mean here?','What evidence validates this dependency?','What should we do before changing capacity?'),('Tenant-scoped integration topology','Latency traces and link-specific tests','Source ID and review date')),
 ('Strategic Twin Studio','Shadow Alternatives'):('Compare rejected options with transparent, falsifiable assumptions.',('How is the shadow scenario calculated?','What does P90 mean?','Why is this not a causal estimate?'),('Frozen decision-time alternative set','Common currency and time horizon','Distribution assumptions and sensitivity')),
 ('Strategic Twin Studio','Assumption Review'):('Identify assumption revalidation needs from sourced signals.',('Why is the signal stale?','When should the assumption be revalidated?','Can you invalidate this assumption automatically?'),('Observation timestamp and source','Predeclared threshold','Accountable reviewer')),
 ('Strategic Twin Studio','Governed Autonomy'):('Prepare bounded interventions without executing them.',('Can the agent approve its own action?','Which controls block execution?','How is the action audited?'),('Policy version and approved scope','Distinct human approver','Fresh execution-time policy check')),
 ('Decision Operations','Value Realization'):('Distinguish finance-verified realization from modeled gains.',('What is modeled value?','Is a projected gap a real financial loss?','What evidence does Finance need?'),('Approved forecast and period','Reconciled GL evidence','Finance attestation')),
 ('Industry Intelligence','Decision Copilot'):('Answer industry-specific questions without invented benchmarks.',('Which evidence is required in this industry?','How can we evaluate an AI pilot?','What is a confounder?'),('Industry applicability review','Pilot baseline and population','Risk owner')),
 ('Decision Quality & Assumption Engine','Decision Quality'):('Explain reproducible evidence-based process scores.',('Why is quality not outcome success?','Why is my score not assessable?','What is independent review?'),('Scoring rubric version','Review attestations','Approved evidence references')),
}
DEFAULT = {
 'Strategy-to-Outcomes Review':('Explain strategic lineage and outcome measurement.',('Why is this KR stale?','What is missing from the evidence chain?','Does a completed task mean success?'),('KR observations and dates','Decision and strategy link IDs')),
 'Microsoft Transformation':('Guide transformation outcomes, adoption and responsible-AI review.',('What makes this rollout ready?','What adoption evidence is missing?','Which impact review is needed?'),('Business baseline','Impact assessment','Adoption telemetry')),
 'AWS Operational Readiness':('Guide architecture, security and operational readiness.',('What is shared responsibility?','What makes this release blocked?','What rollback evidence is needed?'),('Architecture assessment','Guardrail tests','Rollback and runbook')),
 'Google Evaluation & Safety':('Guide experiment design, evaluations and red-team evidence.',('What are deterministic evaluations?','What are non-deterministic evaluations?','What evidence establishes causality?'),('Evaluation dataset','Repeated test results','Predeclared acceptance criteria')),
 'Ecosystem Intelligence':('Differentiate integration plans from connected telemetry.',('Are our vendor feeds live?','What evidence validates the integration?','What is the blast radius?'),('Connector health and authorization','Source lineage','Tenant-scoped traces')),
 'Decision Operations':('Explain recorded signals and evidence-backed interventions.',('Which intervention needs review?','What counts as decision debt?','Is modeled value at risk a loss?'),('Signal records','Policy and action packet IDs','Measured evidence')),
 'Industry Intelligence':('Guide domain-specific use cases and credible evaluation.',('Which decisions matter in this industry?','What are likely confounders?','Can I prefill a decision draft?'),('Industry decision template','Applicable regulations and risks','Measured baseline')),
 'Architecture Mastery':('Translate reference architectures into implementation roadmaps.',('How do I implement Microsoft CAF?','What is the trust boundary?','What tests prove this architecture?'),('Requirements and threat model','Architecture decisions','Test evidence')),
}

def resolve(workspace: str, tab: str='Overview') -> Context:
    if (workspace,tab) in SPECIAL:
        p,q,e=SPECIAL[(workspace,tab)]
    elif workspace in DEFAULT:
        p,q,e=DEFAULT[workspace]
    else:
        p=f'Guide work in {workspace}, without inferring unseen records.'
        q=('What is the purpose of this workspace?','What evidence is missing?','What should I validate next?')
        e=('Authenticated source records','Evidence freshness','Responsible reviewer')
    return Context(workspace,tab,p,tuple(q),tuple(e))

def answer(question: str, ctx: Context, server: dict | None=None) -> str:
    """Pure closed-domain query planner/answerer, never claims unavailable evidence."""
    q=question.strip().lower()
    if not q: return 'Enter a question to assess.'
    # arithmetic is explicit and unit-neutral; no financial verification inferred
    m=re.fullmatch(r'(?:calculate\s+)?(-?\d+(?:\.\d+)?)\s*%\s+of\s+(-?\d+(?:\.\d+)?)\??',q)
    if m:
        try: return f'Result: {(Decimal(m[1])*Decimal(m[2])/100):,.2f}. Arithmetic only; no verified business impact is implied.'
        except (InvalidOperation, ValueError):return 'Invalid numeric inputs.'
    if re.search(r'caus|attribut|confound',q):
        return 'Attribution is UNKNOWN without an identified counterfactual and evidence supporting an experimental or defensible quasi-experimental design. A dependency, timing correlation, or simulation is not causal proof.'
    if re.search(r'financ|saving|loss|value at risk|realiz',q):
        return 'Modeled and projected value are not finance-verified realization or realized loss. Validate currency, time window, reconciliation basis, ledger source, and finance review before quantifying a loss.'
    if re.search(r'agent|authoriz|approv|execut|policy|autonom',q):
        return 'An agent may prepare an evidence-backed draft, but cannot grant itself authority. Enforce scoped tools, distinct approver identity, server-side policy and fresh authorization immediately before an irreversible action.'
    if re.search(r'stale|fresh|revalid|assumption',q):
        return 'Review the observation timestamp against the contract freshness limit. A stale or breached signal calls for reassessment; it does not independently prove the assumption false.'
    if re.search(r'why|missing|evidence|validat|verified|review|test|readiness|block|implement|framework|architecture|roadmap|how|purpose|score|metric|decision|pilot|risk|learn',q):
        evidence='; '.join(ctx.evidence)
        lines=f'**{ctx.workspace} → {ctx.tab}.** {ctx.purpose}\n\n**Required evidence:** {evidence}.\n\n**Next step:** identify a source record and accountable reviewer; do not mark a control complete from a free-text claim.'
        if isinstance(server,dict) and server.get('next_action'):
            lines+=f"\n\n**API-reported next action:** {server['next_action']} (not independently verified by this adviser)."
        return lines
    return f'No grounded answer for this query in **{ctx.workspace} → {ctx.tab}**. I cannot infer records or invent benchmarks. Ask about one of the suggested feature questions, evidence, architecture or arithmetic.'

def render(api=None, workspace='Overview', tab='Overview', key='ctx', expanded=False):
    ctx=resolve(workspace,tab)
    with st.expander(f'◈ Decision Copilot · {workspace} / {tab}',expanded=expanded):
        st.caption('Feature-scoped Python adviser · no write access · no claims of live integration')
        st.write(ctx.purpose)
        cols=st.columns(min(3,len(ctx.questions)))
        for i,item in enumerate(ctx.questions):
            if cols[i%len(cols)].button(item,key=f'{key}_q_{i}',use_container_width=True):
                st.session_state[f'{key}_query']=item
        question=st.text_area('Ask about this feature',key=f'{key}_query',height=80,placeholder='Ask an evidence, risk, method, or calculation question…')
        if st.button('Ask feature copilot',key=f'{key}_ask',type='primary'):
            server=None
            # Server fetch intentionally optional. Existing universal endpoint may be unavailable.
            if api is not None:
                server=api('GET','/v1/execution/copilot-context?page='+quote(workspace),quiet=True)
            st.markdown(answer(question,ctx,server))
        st.caption('This is a bounded deterministic adviser, not an AI assurance or verification service.')
