"""Decision OS: bounded, explainable strategic twin. No writes, no live data claims.

This module deliberately separates dependency exposure, scenario modeling, external
signals, and authorization. It does NOT infer causality from a graph edge or allocate
agent privileges based on performance.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import streamlit as st

VISION = "Map downstream dependencies, revisit rejected alternatives, and detect evidence gaps before approving consequential interventions."

@dataclass(frozen=True)
class Node:
    id: str
    name: str
    owner: str
    kind: str
    source: str = "illustrative"

@dataclass(frozen=True)
class Dependency:
    source: str
    target: str
    mechanism: str
    evidence_ref: str = ""
    strength: str = "unverified"

@dataclass(frozen=True)
class Signal:
    name: str
    observed_at: datetime
    value: float
    unit: str
    source_ref: str
    verified: bool

DEMO_NODES = (
    Node("azure", "Azure capacity reduction", "Cloud Platform", "Infrastructure"),
    Node("crm", "Agentforce response latency", "Sales Operations", "AI workflow"),
    Node("retention", "Customer retention", "Revenue Operations", "Business outcome"),
    Node("incident", "ServiceNow support volume", "IT Operations", "Operational demand"),
    Node("margin", "Operating margin", "Finance", "Financial outcome"),
)
DEMO_EDGES = (
    Dependency("azure", "crm", "Capacity constraints may affect inference latency"),
    Dependency("crm", "retention", "Slow responses may affect customer experience"),
    Dependency("crm", "incident", "Latency may drive service escalations"),
    Dependency("retention", "margin", "Retention changes may affect revenue and margin"),
)

def blast_radius(start: str, nodes: tuple[Node,...], edges: tuple[Dependency,...], max_depth: int = 5) -> list[dict]:
    """Find reachable dependencies, with path and depth; never assert causality."""
    known = {n.id:n for n in nodes}
    if start not in known: return []
    adjacency: dict[str,list[Dependency]] = {}
    for edge in edges:
        if edge.source in known and edge.target in known:
            adjacency.setdefault(edge.source,[]).append(edge)
    found = []
    queue = [(start,0,[start])]
    best = {start:0}
    while queue:
        current,depth,path = queue.pop(0)
        if depth >= max_depth: continue
        for edge in adjacency.get(current,[]):
            if edge.target in path: continue
            nd=depth+1
            if best.get(edge.target,math.inf) <= nd: continue
            best[edge.target]=nd
            nxt=path+[edge.target]
            found.append({"node":edge.target,"name":known[edge.target].name,"depth":nd,
                          "path":nxt,"mechanism":edge.mechanism,"evidence_ref":edge.evidence_ref,
                          "status":"dependency hypothesis" if not edge.evidence_ref else "documented dependency (not proof of causality)"})
            queue.append((edge.target,nd,nxt))
    return sorted(found,key=lambda x:(x["depth"],x["name"]))

def compare_alternatives(cost_active: float, benefit_active: float, cost_shadow: float, benefit_shadow: float) -> dict:
    """Comparison of user-entered comparable-horizon projections; NOT actual returns."""
    values=[cost_active,benefit_active,cost_shadow,benefit_shadow]
    if not all(math.isfinite(float(x)) and float(x)>=0 for x in values):
        raise ValueError("All figures must be finite and nonnegative")
    active=Decimal(str(benefit_active))-Decimal(str(cost_active))
    shadow=Decimal(str(benefit_shadow))-Decimal(str(cost_shadow))
    return {"active_net":float(active),"shadow_net":float(shadow),"modeled_delta":float(shadow-active),
            "attribution":"scenario comparison only; no verified counterfactual"}

def simulate_shadow(active_cost:float,active_benefit:float,shadow_cost:float,shadow_benefit:float,
                    uncertainty_pct:float=15, trials:int=3000, seed:int=42)->dict:
    if not 0 <= uncertainty_pct <= 100 or not 100<=trials<=50000: raise ValueError("Invalid simulation inputs")
    base=compare_alternatives(active_cost,active_benefit,shadow_cost,shadow_benefit)
    rng=random.Random(seed)
    spread=uncertainty_pct/100
    # Shared shock across scenarios, plus independent implementation risk.
    deltas=[]
    for _ in range(trials):
        common=rng.uniform(-spread,spread)
        a=(active_benefit*(1+common+rng.uniform(-spread/2,spread/2)) - active_cost*(1+rng.uniform(-spread/2,spread/2)))
        b=(shadow_benefit*(1+common+rng.uniform(-spread/2,spread/2)) - shadow_cost*(1+rng.uniform(-spread/2,spread/2)))
        deltas.append(b-a)
    deltas.sort()
    return {**base,"p10":deltas[int(.10*(trials-1))],"p50":deltas[int(.50*(trials-1))],
            "p90":deltas[int(.90*(trials-1))],"shadow_better_fraction":sum(d>0 for d in deltas)/trials,
            "seed":seed,"trials":trials,"assumption":"illustrative uniform shocks, not empirically calibrated probabilities"}

def evaluate_signal(signal: Signal | None, threshold:float, max_age_days:int, today: datetime | None=None)->dict:
    now=today or datetime.now(UTC)
    if signal is None:return {"status":"UNKNOWN","reason":"No source observation available"}
    if not signal.source_ref or not signal.verified:return {"status":"UNVERIFIED","reason":"Source was not independently verified"}
    if signal.observed_at.tzinfo is None:return {"status":"UNVERIFIED","reason":"Observation timestamp has no timezone"}
    age=(now-signal.observed_at).total_seconds()/86400
    if age < 0:return {"status":"UNVERIFIED","reason":"Observation timestamp is in the future"}
    if age>max_age_days:return {"status":"STALE","reason":f"Observation is {age:.1f} days old (limit {max_age_days})"}
    if signal.value>threshold:return {"status":"REVIEW REQUIRED","reason":"Threshold exceeded; hypothesis requires human assessment, not automatic invalidation"}
    return {"status":"WITHIN THRESHOLD","reason":"No threshold breach observed; this does not validate the causal assumption"}

def autonomy_gate(action:str,scope:set[str],required_approval:bool,approved:bool,policy_current:bool)->dict:
    blockers=[]
    if action not in scope:blockers.append("Action outside approved scope")
    if required_approval and not approved:blockers.append("Independent human approval missing")
    if not policy_current:blockers.append("Fresh policy evaluation missing")
    return {"permitted":not blockers,"blockers":blockers,"notice":"Advisory gate only; backend must enforce all controls immediately before execution"}

def proposal_packet(subject:str,findings:list[dict],scenario:dict | None=None)->dict:
    packet={"kind":"DECISION_TWIN_REVIEW_DRAFT","subject":subject,"status":"NOT SUBMITTED / NOT APPROVED / NOT EXECUTABLE",
            "created_at":datetime.now(UTC).isoformat(),"findings":findings,
            "proposed_actions":["Validate dependency evidence and accountable owners", "Evaluate alternatives with comparable assumptions", "Request independent policy and risk review"],
            "human_review_required":True,"caveats":["Graph reachability does not establish causality", "Scenario estimates are not realized financial results"]}
    if scenario:packet["scenario_assumptions"]=scenario
    canonical=json.dumps(packet,sort_keys=True,separators=(",",":"),default=str)
    packet["draft_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    return packet

def render(api=None,navigate=None):
    st.markdown("<style>.stApp h1{letter-spacing:-.045em}.dt-caption{color:#7c8796;font-size:.81rem;letter-spacing:.13em;text-transform:uppercase}.dt-rule{border-bottom:1px solid rgba(128,128,128,.22);padding-bottom:10px}</style>",unsafe_allow_html=True)
    st.caption("DECISION OS  /  STRATEGIC INTELLIGENCE  /  DESIGN PARTNER PREVIEW")
    st.title("Enterprise Decision Twin")
    st.write(VISION)
    st.info("**Mode: Scenario laboratory.** All example dependency edges and modeled numbers are illustrative. No live vendor connectors, causal discovery, finance verification, or automated permission changes are claimed.")
    from ui.context_copilot import render as render_feature_copilot
    t1,t2,t3,t4=st.tabs(["Blast Radius","Shadow Alternatives","Assumption Signals","Autonomy & Review"])
    with t1:
        st.subheader("See what a decision could affect")
        start=st.selectbox("Proposed change",[n.id for n in DEMO_NODES],format_func=lambda s:next(n.name for n in DEMO_NODES if n.id==s),key="twin_start")
        results=blast_radius(start,DEMO_NODES,DEMO_EDGES)
        c1,c2=st.columns(2)
        c1.metric("Potentially connected systems",len(results))
        c2.metric("Deepest dependency hop",max((r['depth'] for r in results),default=0))
        for item in results:
            with st.container(border=True):
                st.markdown(f"**{item['name']}** · Hop {item['depth']}")
                st.caption(" → ".join(item['path']))
                st.write(item['mechanism'])
                st.caption(item['status'])
        st.warning("These are possible dependency pathways, not mathematically established causal relationships. Real analysis requires versioned graph edges, impact evidence and permissions.")
        render_feature_copilot(api=api,workspace='Strategic Twin Studio',tab='Blast Radius',key='twin_t1_copilot')
    with t2:
        st.subheader("Revisit the road not taken")
        st.caption("Use the same currency and valuation period throughout. Hypothetical values only.")
        a,b=st.columns(2)
        with a:
            st.markdown("**Approved path**")
            ac=st.number_input("Approved cost",min_value=0.0,value=50.0,key="tw_ac")
            ab=st.number_input("Approved benefit",min_value=0.0,value=80.0,key="tw_ab")
        with b:
            st.markdown("**Shadow alternative**")
            sc=st.number_input("Alternative cost",min_value=0.0,value=48.0,key="tw_sc")
            sb=st.number_input("Alternative benefit",min_value=0.0,value=82.0,key="tw_sb")
        unc=st.slider("Illustrative scenario uncertainty (%)",0,60,15,5)
        comparison=simulate_shadow(ac,ab,sc,sb,unc)
        x,y,z=st.columns(3)
        x.metric("Approved net",f"{comparison['active_net']:,.2f}")
        y.metric("Alternative net",f"{comparison['shadow_net']:,.2f}")
        z.metric("Modeled alternative − approved",f"{comparison['modeled_delta']:+,.2f}")
        st.write("**Simulated difference, P10 / P50 / P90:**",f"{comparison['p10']:.2f} / {comparison['p50']:.2f} / {comparison['p90']:.2f}")
        st.caption("The simulated fraction of outcomes where the alternative is higher is not a calibrated probability. No real-time pricing or market data is used.")
        st.session_state['twin_scenario']={"approved_cost":ac,"approved_benefit":ab,"shadow_cost":sc,"shadow_benefit":sb,"scenario_uncertainty_pct":unc,"comparison":comparison}
        render_feature_copilot(api=api,workspace='Strategic Twin Studio',tab='Shadow Alternatives',key='twin_t2_copilot')
    with t3:
        st.subheader("Turn external change into a review trigger")
        st.caption("A source record is required before a signal can be trusted. This demonstration does not fetch external data.")
        metric=st.text_input("Assumption metric",value="Cloud unit cost")
        limit=st.number_input("Review threshold — values above trigger review",value=120.0)
        observed=st.number_input("Observed value",value=128.0)
        source=st.text_input("Source record / immutable evidence reference",placeholder="e.g. approved telemetry snapshot ID")
        verified=st.checkbox("Evidence independently verified (demonstration attestation only)",value=False)
        age=st.number_input("Age of observation (days)",min_value=0,max_value=3650,value=2)
        freshness=st.number_input("Maximum permitted age (days)",min_value=1,max_value=3650,value=30)
        signal=Signal(metric,datetime.now(UTC)-timedelta(days=age),observed,"user-defined",source,verified)
        result=evaluate_signal(signal,limit,freshness)
        st.write(f"**{result['status']}** — {result['reason']}")
        st.caption("Independent verification must ultimately be performed by the backend; a checkbox is never proof.")
        st.session_state['twin_signal']={"metric":metric,"threshold":limit,"observed":observed,"source_ref":source,"assessment":result}
        render_feature_copilot(api=api,workspace='Strategic Twin Studio',tab='Assumption Review',key='twin_t3_copilot')
    with t4:
        st.subheader("Performance never grants new authority")
        st.write("Agent autonomy remains bounded by explicit scopes, independent human approval and a fresh backend policy decision. Strong past performance cannot widen permissions automatically.")
        action=st.selectbox("Proposed action",["prepare_review","send_notification","change_budget","deploy_agent"])
        scope=st.multiselect("Illustrative authorized scopes",["prepare_review","send_notification","change_budget","deploy_agent"],default=["prepare_review"])
        approved=st.checkbox("Independent approval recorded (simulation)",value=False)
        policy=st.checkbox("Fresh backend policy approval available (simulation)",value=False)
        gate=autonomy_gate(action,set(scope),True,approved,policy)
        st.write("**Illustrative policy check:**", "Conditions satisfied in simulation" if gate['permitted'] else "BLOCKED")
        for block in gate['blockers']:st.error(block)
        st.caption(gate['notice'])
        st.divider()
        st.markdown("**Generate a governed review proposal**")
        subject=st.text_input("Review subject",value="Cross-platform strategic change")
        packet=proposal_packet(subject,blast_radius('azure',DEMO_NODES,DEMO_EDGES),st.session_state.get('twin_scenario'))
        st.download_button("Download proposed action packet (JSON)",data=json.dumps(packet,indent=2),file_name="strategic_twin_review_draft.json",mime="application/json")
        st.caption("Download is not submission, approval, policy enforcement or execution. Existing Decision OS Trust Layer must remain authoritative.")

        render_feature_copilot(api=api,workspace='Strategic Twin Studio',tab='Governed Autonomy',key='twin_t4_copilot')
