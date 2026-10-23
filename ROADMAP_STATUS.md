# Decision OS — Architecture status and prioritized product roadmap

**Evidence basis:** Earlier incremental ZIPs and the new UI changes; this is not a live production audit. 'Prototype' means code/artifacts available, not enterprise-scale certification.

| Capability | Status from available artifacts | Key gap |
|---|---|---|
| Strategy → objectives → KRs → observations | R5.5 prototype | Verified source ingestion and workflow usability |
| R4 execution and R5 Trust / Action Packets | Implemented prototype | Production SSO, policy invariants, tenant-isolation penetration testing |
| R5.6 Evaluation Contract | Prototype with reviewed locks | Freeze at original decision approval, external integrity anchoring and attested evidence sources |
| Assumption tracking | Basic data capture and analysis | Versioned dependencies, validation scheduling and reviewed alerts |
| Executive Briefing / Decision Operations | Read-only prototypes | Full evidence contracts, finance data, persistent operator signals |
| Academy / multi-cloud / 12-industry playbooks | Reference UI prototypes | Validated domain templates, lifecycle workflow integration |
| Enterprise Decision Twin / Strategic Twin | Scenario laboratory | Authenticated dependency graph, real counterfactual data, independent sensitivity validation |
| Decision Copilot | Page-specific deterministic guidance (this release) | Source-cited tenant retrieval, tool evaluations, page/tab registration across remaining modules |
| Architecture Mastery | New visual reference workspace | Hands-on runnable architecture labs, recorded mastery and formal framework review cycle |
| Agentic LangGraph / Ollama | Optional isolated prototype | Secure tool delegation, regression evaluations, human review, telemetry and rollback |
| Live SAP/Salesforce/Azure/etc. connectors | Not delivered in prior UI demos | OAuth/managed identity, least privilege, provenance, connector health and retries |
| AI FinOps reconciliation | Concept and read-only prototype | Finance-attested records and common-period/currency controls |
| Decision Integrity / Kill Criteria | Snapshot aspects exist; full stop criteria not yet proven | Approval-time immutable criteria, timed-window evaluator, waivers and enforcement |
| Organizational learning | Concept and sparse replay | Eligibility policy, de-identification, causal rigor, evaluated retrieval |

## Next releases by dependency, not ambition

1. **R6.A Integrity hardening**: decision-time immutable evidence, policy, reviewer, assumption and kill-criteria snapshots; server-side trigger evaluator; verified replay. This is the critical security and temporal-integrity dependency.
2. **R6.B Evidence and evaluation engine**: typed provenance, external observation connectors, source authentication, deterministic tests, repeated LLM safety/groundedness evals, measurement integrity. First deployment should be one tenant + one source.
3. **R6.C AI FinOps and Decision Debt**: currency/period alignment, finance-signoff workflow, staleness and unclosed-review signals; distinguish projected gap from cash loss.
4. **R6.D Copilot platform service**: feature contracts at API boundary, scoped retrieval citations, safe draft tools, offline golden-question tests, groundedness score, abstention quality, prompt-injection and authorization tests.
5. **R6.E Closed-loop pilot**: 2–3 real customer workflows; baseline time-to-decision, evidence completion, governance burden, interventions actually approved, and observed business value.
6. **R7/R8**: governed operator, network-scale dependency graph, evaluated shadow alternatives, explicit autonomy ceilings and non-self-modifying update policy. Build only after successful real pilots.

## CAIO-grade quality gates

- **Security:** Entra/SSO or equivalent identity; tenant isolation in backend queries; default-deny on tool calls; independent reviewer; encrypted secrets; append-only audit with tamper evidence; rollback.
- **Accuracy:** Observation ≠ assessment; quality ≠ outcome; unknown ≠ zero; causal labels only after design review; no fake verified evidence; time-aware sources; reproducible math and negative-value tests.
- **Reliability:** fail closed for approval, fail transparently for read-only analysis; graceful connector outages and stale handling; idempotency and concurrency tests.
- **Usability:** 90-second first meaningful value; progressive disclosure; meaningful empty states; page-specific suggestions; accessibility and contrast verified in light/dark themes.
- **Commercial proof:** Pilot with customer permissions; measurable reduction in evidence preparation burden, faster review, and reproducible executive decisions. Claims about top-1% maturity require empirical benchmarks.

## HLD feature service contract, future backend

`GET /v1/copilot/context?workspace=&tab=&record_id=` → tenant-authorized source references and allowed intent set. `POST /v1/copilot/query` → answer, citations, unknowns, confidence_basis, eval_trace_id and authorized capability. `POST /v1/copilot/drafts` → schema validated draft, requiring explicit user confirmation; no approvals. No new server endpoints in this UI delta.
