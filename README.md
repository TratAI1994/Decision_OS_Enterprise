# Decision OS — Integrated Enterprise Console (consolidated safe release)

## What is included

A complete, locally runnable **frontend source tree** assembling the latest R10.3–R10.6 modules, functional R7 Decision Ledger, R8 read-only Outcome Economics, Risk & Controls, R9.9 authenticated-source evidence viewer, Transformation Workbench, Strategy Lab (ten disciplines), Portfolio & Agile Delivery sandbox, and the reversible professional light theme. New in this package is an 8-dimension, 5-objective AI transformation maturity and framework-fitment workbench with explainable weighted priority actions.

**This is not full production implementation of every R10–R12 release.** The connected Journey, finance operations, execution, graph persistence, IAM and source-system integrations are limited by the existing backend APIs. Do not treat navigation or simulated data as completion. Human approval, finance attestation and tenant enforcement remain backend responsibilities.

## Safe install (Windows)

1. Back up your existing `D:\Users\atmm1\Decision_OS_Enterprise\frontend` folder.
2. Extract this archive in a **separate folder** first. It includes a `frontend/` folder; compare local modifications before replacing. This is an integrated baseline, not a merge against unseen Windows edits.
3. Copy or merge `frontend/` into your Decision OS project, preserving a backup.
4. Run from PowerShell:

```powershell
cd D:\Users\atmm1\Decision_OS_Enterprise\frontend
npm install
npm test
npm run build
npm run dev
```

5. Open http://127.0.0.1:5173 and check **AI Readiness Assessment**, Portfolio & Agile Delivery, Decision Ledger, Outcome Economics, Risk, Engineering, Strategy Lab and Trust Validation.
6. Your existing API host port is `8001`; `vite.config.js` proxies browser `/api` requests there. If your Compose port differs, update the Vite proxy.

## One-command gate

From archive root (or project root after merging):

```powershell
node tools\verify-release.mjs
```

Tests and production build must both pass. A machine-readable `frontend/release-gate-report.json` is written with unverified external-system gates explicitly `NOT_TESTED`. `production_certified` remains false regardless of local frontend success.

## Results in this build environment

- `npm test`: **72 PASS**, 0 fail.
- Vite production compile: **not run here**, because dependencies are unavailable in this isolated container (no cached node_modules or npm registry access).
- Browser visual/keyboard testing, real API read-contract tests, PostgreSQL negative tests, concurrent ingestion, identity provider, Jenkins/SBOM/signing, finance ERP: **not tested here**.

## Important limitations and architectural boundaries

- Read-only React workspaces do not perform privileged backend changes.
- Imported test reports cannot self-certify. Signed collector ingestion does not verify business content.
- Maturity scores are **self-reported**, weightings are transparent advisory assumptions; no audited enterprise rating is implied.
- The portfolio planner supports a small bounded sandbox, **not** general enterprise MILP at scale.
- Sample portfolio plans are illustrations, not customer production records.
- No source-system connector was newly deployed, no production agent executor was enabled, no payments were automated.
- Reusing the frontend does **not** automatically connect R10–R12 Knowledge Graph persistence or historical finance data.

See `docs/HLD_LLD.md` and `docs/ROADMAP_GATES.md` for subsystem architecture and remaining integration gates.
