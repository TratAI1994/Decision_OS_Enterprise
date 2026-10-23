# Decision OS R8 — Verified Outcome Economics (incremental release)

## Scope
A narrow, read/write finance benefit event stream tied to authorized Decision OS decisions. It **does not** replace authoritative funding approvals, independently authenticate GL records, or prove causal attribution. The backend requires a `finance` role for independent reconciliation; admin is **not** implicitly a controller.

Files to overlay in `D:\Users\atmm1\Decision_OS_Enterprise`:

- `backend/outcome_economics.py` — new finance benefit event API
- `backend/migration_r8.py` — additive `di_outcome_events` table and PostgreSQL UPDATE/DELETE rejection trigger
- `backend/api.py` — R7 baseline + two-line router registration
- `ui/outcome_economics.py` — new executive UI
- `ui/app.py` — R7 baseline + navigation/dispatcher
- `tests/test_outcome_economics.py` — focused FastAPI tests

**If you have modified `backend/api.py` or `ui/app.py` since R7, don't overwrite them.** Merge only:

```python
# append in backend/api.py after other routes:
from .outcome_economics import build_router as build_outcome_router
app.include_router(build_outcome_router(identity,session,require))

# ui/app.py: add 'Outcome Economics' to PAGES and Decision Infrastructure section;
elif page=='Outcome Economics':
    from ui.outcome_economics import render as render_outcome_economics
    render_outcome_economics(api=api,navigate=navigate_to)
```

## Windows install

Back up DB and files. Unzip into project root. Verify you have a `finance` identity configured in your server's `DECISION_OS_IDENTITIES` JSON registry. Never add an arbitrary fake finance credential or expose it to other users.

```powershell
cd D:\Users\atmm1\Decision_OS_Enterprise
docker compose up -d db
docker compose build api ui
docker compose run --rm --no-deps api python -m backend.migration_r8 --check
docker compose run --rm --no-deps api python -m backend.migration_r8 --apply
docker compose up -d --no-build api ui
```

At `http://127.0.0.1:8502` use **Decision Infrastructure → Outcome Economics**.

## API workflow

1. `POST /v1/outcome-economics/plan` — one immutable expected benefit baseline for an existing tenant-scoped decision, period, currency, methodology, source reference. This R8 baseline **is not yet bound atomically to original approval time**.
2. `POST /v1/outcome-economics/{id}/report` — authorized author appends self-reported outcome with provenance and attribution **label**; never finance-verified.
3. `POST /v1/outcome-economics/{id}/finance-attest` — only a separate authenticated `finance` role can append an independently reconciled benefit, with GL/ERP reference and explicit acknowledgment. Same user cannot report and attest. Verification is an **attestation**, not proof the claimed GL pointer was independently retrieved.
4. `GET /v1/outcome-economics/{id}` — deterministic replay, locally verified hash chain, and expected/reported/attested numbers. `variance` remains **null** until step 3.

## Precision, governance and limitations

- Money is parsed from finite **decimal strings** into integer cents; comparisons share the same currency and fiscal period. The expected amount uses a one-period plan. No silent FX conversion, annualization, financial double counting or ROI formulas are inferred.
- No self-reported savings can be labeled finance-verified, and admin isn't finance. Current auth uses configured bearer credentials, **not SSO/MFA**. Production must integrate SSO, scoped delegated identity, least privilege and controller authorization independent from general admins.
- Records and reviewers are *append-only through the R8 API*. The PostgreSQL trigger denies normal UPDATE/DELETE. The digest has **no external signature/anchor**, and a privileged DB operator can alter or suppress a whole record stream. WORM retention, cryptographic signatures, independent anchoring and backup/recovery must be added before attesting enterprise-grade immutability.
- Financial attestation records the controller's opinion and financial source pointer. It **doesn't validate a GL record through an ERP connector**; full provenance requires signed source retrieval, matching account/period/currency, duplicate-benefit controls, and independent controller documentation.
- **Attribution** is independent: `experimental`, `quasi_experimental`, `correlational`, `estimated`, `unknown`. A method label is not a validated causal design. Even a reconciled amount does not prove that AI caused the benefit.
- Root cause is captured as *notes/hypothesis*, not inferred truth.
- This slice permits one period per decision and one finance confirmation per period. Corrections, reversals, multi-period benefits, approval-time anchoring and revocation require a designed governed versioned workflow—not direct edits. Do not use against live financial ledgers without these protections.
- End-to-end PostgreSQL, security testing, browser testing and external signatures **have not been run**.

## Automated checks

In the isolated test environment (`SQLite` memory; no PostgreSQL triggers):

```bash
python -m pytest tests/test_outcome_economics.py -q
```

8 focused tests passed covering monetary precision, no premature verified benefit, variance, independence of controllers, tenant isolation, idempotency, stale sequence rejection, tampering and data constraints.

## Suggested next release

R7.1 approval-time **atomic** integrity snapshot; R7.2 external signing; R8.1 finance connector + trial-balance/GL reconciliation with audit-safe reversals and multi-period accounting; R9 policy-enforced governed agent actions.
