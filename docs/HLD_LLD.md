# Decision OS Consolidated Architecture: HLD / LLD

## HLD

**Presentation:** Vite/React with light-first enterprise styles, context guidance, and feature workspaces.
**Client models:** Pure JS functions (`strategy-engine.js`, `portfolio-model.js`, `transformation-assessment.js`, `ledger-model.js`, `enterprise-domain.js`). They calculate only illustrative/advisory projections from explicit inputs.
**HTTP adapters:** `enterprise-client.js`, `api.js`, and existing per-workspace GET adapters. All routes are bound to `/api` Vite proxy to the authoritative local FastAPI server.
**Authority:** Existing FastAPI R7–R9.9 identity, policy, event, finance, source-authentication and observation services; PostgreSQL records (no trust uplift in browser).
**Development:** local-first Node and Docker Compose; no SaaS dependencies required for the MVP beyond obtaining OSS npm packages.

## LLD contracts

### Assessment

Input: `{objective: one of 5 identifiers, scores: {strategy, data, risk, architecture, delivery, people, operations, finance}}` where values must be explicit integers `0..4`. Missing score produces `INCOMPLETE`, `score:null`. Full input computes `round(sum(score * adjustedWeight)/sum(4 * adjustedWeight)*100)`. Adjusted weight is a declared capability weight +2 for objective focus areas. Ranked actions for scores <3; equal rank is ordered by stable ID. Status `ASSESSED_SELF_REPORTED`, never verified/certified. Results are not persisted or treated as authoritative approval.

### Portfolio

`portfolio-model.js`: bounded branch-and-bound selection under budget, team capacities and prerequisites; explicit orphan labeling, invalid input and dependency cycle rejection; no production work-item edits or autonomous planning approval.

### Ledger, finance, risk, engineering

`DecisionLedger.jsx`, `EnterpriseWorkspaces.jsx`: use fixed read routes and backend's signed/integrity or finance attestation states. Client does not compute privileged attestations or independent verification.

### User interface

`main.jsx` navigation and layout; `enterprise-light.css` must load after existing styles to win CSS specificity; `assessment.css` only styles new readiness area. `PortfolioStudio.jsx` imports its own `portfolio.css`, but the light-theme stylesheet includes `!important` overrides for core portfolio selectors.

## Threat model

- **Identity spoofing:** not trusted from browser; backend token and tenant check required.
- **Evidence forgery:** self-entered data marked non-verified; server must bind evidence IDs to authenticated source.
- **Approval bypass:** do not implement writes without backend policy, independent roles, CSRF/session and idempotency validation.
- **XSS:** avoid injecting unsafe HTML; React JSX text encoding remains default.
- **Sensitive data:** browser token input, if used, is ephemeral React component state and should be replaced with an enterprise identity proxy; never hard-code secrets in JS.
- **DoS:** portfolio search is bounded to small feature counts; enterprise-scale optimization moves server-side.
- **Tamper/evidence retention:** only PostgreSQL test suite + external signing/anchoring can substantiate strong integrity claims.

## SOLID rationale

Single-responsibility for calculations, adapters, and UI. Model extension through catalogue entries. Presentation depends on backend contracts rather than internal database tables. No new vendor service dependency added. Runtime schemas and external API contract integration require future strengthening.

## Quality gates

`npm test` + `npm run build` mandatory. Browser smoke test covering all workspaces and missing-backend paths. On real installation run the R9.9 negative-control suite against isolated disposable PostgreSQL and archive outputs; do not run mutating DB tests against production. All enterprise readiness claims must be evidence qualified.
