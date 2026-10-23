# Decision OS R5.5 — additive Strategy-to-Outcomes release

## Compatibility and precise scope
Delta files only: `backend/api.py` (one new router registration), `backend/strategy_outcomes.py` (new), `backend/migration_r55.py` (new), `ui/app.py` (new workspace), `tests/test_strategy_r55.py` (new). Built against the delivered Action Center Guided UX update and the R5.4 snapshot-FK hotfix. Do not replace `.env`, existing `docker-compose.yml`, existing tables, previous migrations, or PostgreSQL volumes.

## Backup first
From `D:\Users\atmm1\Decision_OS_Enterprise`, store a backup outside the project folder. For example, after checking the `db` service and DB name in your actual `.env`: `docker compose exec -T db pg_dump -U decision -d decision_os -Fc > D:\Decision_OS_R55_before.dump`. The username/database in this example must match your running container. Also copy your existing `backend/api.py` and `ui/app.py` to a safe folder.

## Preflight and apply
Copy only the delta's relative file paths over your project. Then in Windows PowerShell:

```powershell
cd D:\Users\atmm1\Decision_OS_Enterprise
docker compose up -d db
docker compose build api ui
docker compose run --rm --no-deps api python -m backend.migration_r55 --check
docker compose run --rm --no-deps api python -m backend.migration_r55 --apply
docker compose run --rm --no-deps api python -m backend.migration_r55 --check
docker compose up -d --no-build api ui
docker compose logs --tail=80 api
```

Migration only creates seven `so_` tables, idempotently. It does not rewrite any existing row. **Caveat:** `api.configure()` also calls SQLAlchemy `Base.metadata.create_all` on startup; consequently, on a fresh API startup the new tables may already exist before the explicit migration. `--check` then reports nothing missing, which is expected. Schema inspection and backups remain important. For production, move to an Alembic-managed change process.

Visit `http://127.0.0.1:8502` and open **Strategy & Outcomes R5.5**.

## End-to-end acceptance
1. Create Focus Area, Objective, and KR with baseline / target / staleness threshold.
2. Link KR to an existing Executive Decision (which already links to an initiative and R4 tasks).
3. Record an observation older than the threshold; it must show **STALE** even if its value exceeds the target.
4. Record a recent below-target observation with `correlated`; status must show **IN_PROGRESS**, with attribution kept visible.
5. Pre-register an experiment with a threshold. Post a result below that threshold: **not_supported**. Second result is rejected.
6. A different-tenant credential must not read or link any tenant A entity.

## Tested locally
- `python -m pytest -q tests/test_strategy_r55.py tests/test_decision_governance.py tests/test_trust.py tests/test_r511.py tests/test_execution.py` — 9 passed.
- `python -m pytest -q tests` — 17 passed and 1 pre-existing failure (`test_intelligence.py` still expects an unlinked risk entry, rejected by R3 referential-integrity rules).
- Compiled `backend` and `ui` successfully.
- All tests ran against isolated SQLite, not your Windows Docker/PostgreSQL instance. No browser-level Streamlit verification was possible.

## Explicit boundaries
- No external Jira/GitHub/Prometheus ingestion yet. Observations are entered with a user-provided source reference; no automatic confidence certification.
- Experiment thresholds are immutable after creation; results are assessed deterministically. `causal` attribution is a claim requiring a documented method, not causal verification.
- No live LLM, policy executor or model training. New tables share existing bootstrap-token authentication (not production SSO/RLS).
- Not all legacy forms are redesigned. This release adds one guided strategy workspace and preserves existing workspaces.
