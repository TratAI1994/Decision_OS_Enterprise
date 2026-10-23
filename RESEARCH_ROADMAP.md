# Decision OS: AI Leadership, AI Literacy & Responsible AI — Research-to-Product Roadmap

Research date: October 22, 2026. Scope: Five user-specified official primary sources. This is original curriculum mapping, not a provider course reproduction or certification.

## Core product thesis

**Teach at the point of decision, not before work can begin.** End users should see a guided decision canvas with plain-English explanations, required evidence, controls, a short illustrative example, and a recommended *next review step*, rather than being required to study AI theory first. Specialists can expand deeper lessons and primary references on demand.

## Primary-source mapping (verified official pages)

1. **ISB Online Leadership with AI:** Four advertised pillars: AI Leadership, Generative AI Leadership, Agentic AI Leadership, Responsible AI Leadership. Programme describes enterprise AI strategy, roadmaps, ML, business models, operating models, workforce, and responsible use. Decision OS lesson: value thesis, readiness, governance and executive accountability. URL: https://online-em.isb.edu/leadership-with-ai
2. **Google Machine Learning Crash Course:** Regression, classification, numerical/categorical data, overfitting, neural networks, embeddings, LLMs, production ML, AutoML and fairness. Decision OS lesson: choose model, dataset, threshold, error costs, validation and monitoring. URL: https://developers.google.com/machine-learning/crash-course
3. **Microsoft Learn:** Business leader pathway `Transform your business with AI`: leverage tools, create business value, embrace responsible AI, scale adoption. Also Microsoft Foundry GenAI evaluation guidance. Decision OS lesson: personas, adoption, unit economics, evaluation and change management. URLs: https://learn.microsoft.com/en-us/training/paths/transform-your-business-with-microsoft-ai and https://learn.microsoft.com/en-us/training/paths/evaluate-generative-ai-apps/
4. **NIST AI RMF:** Voluntary AI RMF Core functions Govern, Map, Measure, Manage; Playbook recommends context-specific actions. NIST states AI RMF 1.0 is under revision. Decision OS lesson: specific risk mapping and evidence, safety/security, human oversight and independent review. URLs: https://www.nist.gov/itl/ai-risk-management-framework and https://airc.nist.gov/airmf-resources/playbook/
5. **OECD AI Principles:** Updated May 2024. Five values-based principles: inclusive growth; human rights/fairness/privacy; transparency/explainability; robustness/security/safety; accountability. Decision OS lesson: transparent and human-centered oversight, international policy crosswalk. URL: https://oecd.ai/en/ai-principles

The user-provided ChatGPT shared link did not expose the full prior conversation through public browsing; it is not used as a source.

## Architecture audit: already present vs missing

This is an audit of available R5.5 delivered source and previous release notes, **not a running-user-instance verification**.

| Competency | Existing basis in Decision OS | Gap to enterprise product | Priority |
|---|---|---|---|
| Executive strategy | Focus Areas, Objective, KRs, Executive Decision ledger, Board briefing | In-context AI opportunity/value framing, documented change management and adoption forecasts | High |
| ML model selection | Modeling/fairness/quality workspaces; data-backed decisions | Explicit classification/ranking metric rubric, error-cost threshold wizard, drift validation and MLOps provenance | High |
| GenAI/agents | Action Packets, evaluation/evidence UI, model workbench | Formal agentic tool-policy registry, evaluation sets, injection/security regression harness and production trace audits | Critical before execution |
| Business adoption | Copilot Transformation Office, Workforce Transformation Office, reported unit economics | Cohort adoption, successful task rates, change-management playbook and measured realized value | High |
| NIST RMF | AI Risk & Regulatory Office, control evidence and approval framework references | Versioned NIST subcategory catalog, scoped control applicability, evidence-to-control lineage and independent assurance workflow | Critical |
| OECD principles | Responsible AI assessments and risk categories | Five-principle crosswalk, stakeholder/rights impact map, appeal/recourse evidence, monitoring | High |
| Learning enablement | Existing conceptual workspaces | Role-driven visual microlearning and practical case simulators | **Delivered now (Phase A)** |
| Outcome quality | Observation source, assessed confidence and attribution already in R5.5 | Validated causal methods, source provenance, stale-alerts and live connectors | High |
| Scale and portability | Docker + PostgreSQL + FastAPI | SSO, row-level security verification, tenant key management, AKS/EKS/GKE packaging, SLIs/SLOs | Critical before external enterprise deployment |

## Roadmap

### Phase A — Now: Visual Decision Academy (delivered)
Five source-mapped original lessons; explain-like-I'm-new and executive layer; role paths; six-step concept map; three case studies; quizzes; Markdown playbook. Static read-only content; no persistence.

### Phase B — Guided Framework Assistant (next)
Embed small “Why this question matters” guidance into existing Focus Area/Decision/AI Risk forms; map each decision to applicable controls; recommend *required evidence and human reviewer*, not strategy verdicts; configurable risk thresholds; measure completion and error rates. No unapproved AI writes.

### Phase C — Enterprise AI Governance Catalog
Versioned NIST AI RMF + GenAI profile and OECD mapping; link control ID to policy requirement, evidence checklist, test, owner, review date and disposition. Make jurisdictional overlays separate and legal-reviewed. Track current standard versions and effective dates.

### Phase D — Applied AI Engineering / Economics Lab
Interactive confusion matrix and threshold explorer, calibrated-model and drift demonstration, RAG groundedness/security test cards, unit economics, adoption and scenario sensitivity. Clear synthetic data stamps and reproducible seeded exercises.

### Phase E — Institutional Learning / Measurable Pilots
Persist user learning completion only with consent and identity; link practice cases to outcomes; add customer pilot instrumentation, guided board memo, measured decision-cycle reduction and training-effectiveness evaluation.

### Phase F — Enterprise Scale
Role/permission integration, security reviews, privacy/retention, WCAG testing, localization, shared platform service and deployment profiles for local Docker, AKS, EKS and GKE. Require real scale, reliability and cost evidence before claiming suitability for millions of users.

## Teaching design: rigorous but usable

For each concept: plain-English explanation -> why business cares -> annotated visual mechanism -> interactive choice -> testable hypothesis -> actual Decision OS artifact -> evidence required -> limitation -> primary source. Use graduate-level rigor through careful assumptions, counterfactuals, causal identification, sensitivity analysis, stakeholder impact and documented tradeoffs—not by claiming Oxford/Harvard/MIT affiliation.

## Case-study coverage

- Claims Triage Copilot: baseline, outcome contract, shadow experiment, fairness, human oversight, provenance, independent approval.
- Retail Fulfillment Promise: optimization objective, service constraints, measured cost-to-serve, exception handling.
- Enterprise Knowledge Assistant: retrieval and access boundaries, hallucination/grounding tests, prompt injection, outcome measurement.

All examples are synthetic teaching scenarios. Claims about actual results must come from verified organizational datasets and must show attribution limits.

## Product acceptance criteria

1. Learner completes a role-appropriate path without external course prerequisite.
2. Every lesson identifies an actionable Decision OS record or governance activity.
3. Every framework reference has a primary-source citation and explicit non-endorsement.
4. No lesson silently creates approvals, risk dispositions or financial outcomes.
5. All examples clearly distinguish synthetic scenarios, hypotheses, measured facts and business assumptions.
6. Tenant business data never leaves the authorized API boundary; academy currently performs no API calls.
7. UI imports safely; code compiles; pure learning-unit tests pass.
8. Before production: keyboard, screen-reader and contrast review; secure enterprise identity; user testing; content owner/change control; external-source license review.
