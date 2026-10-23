"""Architecture Mastery — guided, vendor-neutral reference patterns and test plans."""
from __future__ import annotations
from dataclasses import dataclass
import json
import streamlit as st
from ui.context_copilot import render as render_copilot

@dataclass(frozen=True)
class Blueprint:
    name:str
    summary:str
    steps:tuple[str,...]
    controls:tuple[str,...]
    tests:tuple[str,...]
    references:tuple[tuple[str,str],...]

BLUEPRINTS={
 'Microsoft CAF + Responsible AI':Blueprint('Microsoft CAF + Responsible AI','Business outcomes, platform adoption, identity and human accountability.',('Discover measurable customer problem and baseline','Classify data and harms before model choice','Design Entra identities, least privilege and evidence retention','Run model, human impact and adoption evaluations','Gate rollout with signed accountable review','Observe KPIs and revisit assumptions'),('Enterprise identity and delegated access','Impact assessment and traceability','Policy enforcement and retention'),('Unauthorized user cannot retrieve decision','Reviewers cannot approve own packet','Business metric is not achieved from task completion'),(('Microsoft Cloud Adoption Framework','https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/'),('Microsoft Responsible AI','https://www.microsoft.com/en-us/ai/responsible-ai'))),
 'AWS Well-Architected + Responsible AI':Blueprint('AWS Well-Architected + Responsible AI','Reliability, security, operational ownership and shared-responsibility boundaries.',('Scope use case and environment','Map shared-responsibility owners','Threat-model Bedrock/model integrations','Establish guardrails, key management and network controls','Run resilience and failure-injection evaluations','Review releases and operational SLOs'),('IAM least privilege and audit trail','Guardrail evaluation','Rollback policy and cost ceilings'),('Denied IAM scope fails safely','Rollback operates in test environment','Exceeded cost ceiling triggers review'),(('AWS Well-Architected','https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html'),('Responsible AI Lens','https://docs.aws.amazon.com/wellarchitected/latest/responsible-ai-lens/responsible-ai-lens.html'))),
 'Google SAIF + Model Evaluation':Blueprint('Google SAIF + Model Evaluation','Secure AI development with evaluation-driven evidence and feedback loops.',('Specify failure modes and hypotheses','Inventory data, model and application supply chain','Build representative evaluation sets','Measure accuracy, robustness, fairness and leakage','Conduct red-team tests and threat review','Launch with drift and outcome monitors'),('Data and model provenance','Prompt injection isolation','Evaluation dataset versions'),('Prompt injection cannot access private tools','Repeated stochastic tests retain distributions','Causal claims require valid identification'),(('Google SAIF','https://saif.google/'),('Google ML Crash Course','https://developers.google.com/machine-learning/crash-course'))),
 'NIST AI RMF + OECD':Blueprint('NIST AI RMF + OECD','Translate policies into applicable tests and named, reviewable evidence.',('Govern: name owners and context','Map: identify affected groups and harms','Measure: define controlled evidence tests','Manage: assign risk response and release authority','Observe: retest on changes','Replay: preserve decision-time policy versions'),('Policy catalog with versioned controls','Human impact and appeal mechanisms','No self-certification'),('Unknown remains unknown','Waiver requires independent reviewer','Snapshot replays original policy version'),(('NIST AI RMF','https://www.nist.gov/itl/ai-risk-management-framework'),('OECD AI Principles','https://oecd.ai/en/ai-principles'))),
 'Enterprise LangGraph + Ollama':Blueprint('Enterprise LangGraph + Ollama','Bounded local agent workflow with evidence-first tool contracts.',('Define tool capabilities and denied actions','Use stateful graph: retrieve → validate → plan → guard → human review','Enforce tenant-scoped queries server-side','Evaluate deterministic policy and stochastic answer faithfulness','Record tool and model versions, prompts and evidence','Deploy with timeout, fallback, red-team and kill switch'),('No arbitrary code or SQL from model','Typed tool schemas and approval tokens','Offline evaluation and human rollback'),('Tenant crossover attack fails','Prompt-injected source cannot redirect tools','Agent cannot raise permissions or commit finances'),(('LangGraph docs','https://docs.langchain.com/oss/python/langgraph/overview'),('Ollama docs','https://docs.ollama.com/'))),
}

def render(api=None,navigate=None):
    st.title('Architecture Mastery')
    st.caption('Implementation blueprints · threat boundaries · verification plans · source references')
    framework=st.selectbox('Framework or architecture',list(BLUEPRINTS),key='arch_framework')
    b=BLUEPRINTS[framework]
    st.write(b.summary)
    st.subheader('Reference architecture')
    # native Streamlit graphviz, with fixed static content (no user-provided DOT)
    labels=['Business outcome','Evidence contract','Secure platform','Evaluation gate','Human approval','Observe & replay']
    rows=['digraph G {','rankdir=LR;','node [shape=box style="rounded,filled" fillcolor="#F4F5F7" color="#697386" fontname="Arial"];']
    for i,label in enumerate(labels):rows.append(f'n{i} [label="{label}"];')
    for i in range(len(labels)-1):rows.append(f'n{i} -> n{i+1};')
    rows.append('}')
    st.graphviz_chart('\n'.join(rows),use_container_width=True)
    a,bcol=st.columns([3,2])
    with a:
        st.subheader('Implementation roadmap')
        for i,item in enumerate(b.steps,1):st.markdown(f'**{i:02d}.** {item}')
    with bcol:
        st.subheader('Non-negotiable controls')
        for item in b.controls:st.markdown('• '+item)
        st.subheader('Acceptance tests')
        for item in b.tests:st.markdown('• '+item)
    with st.expander('Official resources and methodology boundaries'):
        for label,url in b.references:st.markdown(f'[{label}]({url})')
        st.info('These are original mapping recommendations, not official vendor certification or independently verified deployment patterns.')
    st.download_button('Export implementation checklist',data=json.dumps({'framework':framework,'steps':b.steps,'controls':b.controls,'tests':b.tests,'references':b.references},indent=2),file_name='architecture_mastery_plan.json',mime='application/json')
    render_copilot(api,workspace='Architecture Mastery',tab=framework,key='mastery_copilot')
