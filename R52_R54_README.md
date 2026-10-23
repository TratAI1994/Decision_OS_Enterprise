# Decision OS — R5.2–R5.4 governed decisions (delta)

## Compatibility and installation
Built on top of **R5.1.1**, including its migration. Back up your project and PostgreSQL first. Only the files inside this delta should be copied over the same paths. Do not overwrite `.env`, Compose configuration, secrets or PostgreSQL volumes.

Files:
- REPLACE `backend/api.py` — registers the governed-decision router.
- ADD `backend/decision_governance.py` — immutable decision snapshots (app-managed), deterministic policy checks, Action Packets, independent review, human accountable actions and decision replay.
- REPLACE `ui/app.py` — Action Center, Replay & Memory, structured geography selector in risk assessment.
- ADD `tests/test_decision_governance.py` — tenant, idempotency, independent approval, policy threshold and replay coverage.

## Windows local Docker
```powershell
cd D:\Users\atmm1\Decision_OS_Enterprise
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 api
```

Run a local development test (when pytest is installed):
```
python -m pytest -q tests/test_decision_governance.py tests/test_r511.py tests/test_trust.py tests/test_execution.py
```

`Base.metadata.create_all` creates **three new tables**: `di_decision_snapshots`, `di_action_packets`, `di_accountable_actions`; no existing table is dropped or migrated in this release. **Production use requires Alembic migrations and real PostgreSQL testing.** 

## Acceptance walkthrough
1. Go to **Executive Decision Ledger** and select an existing funded initiative decision.
2. Open **Decision Action Center**; select the same decision; use a referenced rationale with 20+ chars, one evidence ID and allowed proposal action. Submit.
3. The creator must NOT be able to approve their own packet. Use a separately configured reviewer identity to review via `/docs` (the default Streamlit UI token may be `lead` and cannot impersonate a reviewer). The UI shows review fields only for allowed roles.
4. Confirm approved packet creates exactly **one accountable action** but does **not** change an infrastructure, task status, budget or production system.
5. Open **Decision Replay & Memory**. Confirm the saved historical snapshot's SHA256 check and clearly labeled limitations.
6. In AI Risk & Regulatory Office, select geography from the controlled multiselect. For multi-region options, provide further details; review the reactive regulatory section.

## Security and correctness limitations
- There is **no autonomous execution** or optional LLM integration yet. The R5.3 Action Center is accountable human execution, not an autonomous worker.
- Draft-stage and approval-stage policy checks are persisted; a future real executor MUST re-check identity, budget, evidence and policy at execution time. There is no executor currently.
- The policy in this release contains a fixed illustrative threshold (budget proposals over $10k are denied); it is not a production-grade versioned tenant policy management system.
- Snapshots only begin at packet creation; records before this point cannot be historically reconstructed. A SHA256 hash in the same DB is integrity detection, not tamper-proof audit evidence. Signing and external anchoring are required for higher assurance.
- Evidence references are identifiers supplied by users; this release does not independently attest document contents. Memory is deterministic keyword retrieval and provides no unsupported statistics.
- Approval does not spend money or move work into production. Review and action completion are self-reported unless independently verified elsewhere.
- Human identity still uses bootstrap bearer tokens in this local prototype; Entra SSO, real user sessions, tenant-scoped database RLS and schema migrations are not implemented here.
- No React, Kubernetes deployment or LangGraph orchestration is supplied in this release.

## Automated test results (isolated SQLite)
Targeted R4/R5/R5.1.1/R5.2–R5.4 suite: **7 passed**. Full suite: **14 passed, 1 legacy failure** (`tests/test_intelligence.py` expects an unlinked risk record; R3 correctly rejects it). The legacy test must be updated to use a valid initiative ID, rather than weakening foreign-key validation.
