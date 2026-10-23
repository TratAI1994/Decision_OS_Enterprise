# Decision OS Enterprise — Demo Seeder & Executive Board Foundation (R1, part 1)

## Scope
This update changes `backend/api.py`, `ui/app.py`, and adds `seed_demo.py` and `tests/test_seed_demo.py`. The existing project is preserved. Existing PostgreSQL volumes, `.env`, secrets, ports and `docker-compose.yml` must not be overwritten. Database schema is unchanged.

## Apply on Windows
1. Back up your four existing Python source files, then copy the new `backend/api.py`, `ui/app.py` and `seed_demo.py` into `D:\Users\atmm1\Decision_OS_Enterprise` in their corresponding folders. Optionally copy the additional test to `tests`.
2. Open Command Prompt or PowerShell from the project root.
3. Rebuild containers: `docker compose up -d --build` (without `down -v`).
4. Check `docker compose ps`; the host API endpoint is `http://127.0.0.1:8001` only if you retained your earlier 8001 host mapping. The UI remains at `http://127.0.0.1:8502` if you retained 8502.
5. Run **on the host**, using the same Python environment in which requests are not required (seed script uses only standard library):
   `python seed_demo.py --base http://127.0.0.1:8001`
6. Refresh Streamlit; select **Executive Board Scorecard** or **Command Center**.
7. Rerun the same seeder to confirm it skips all three existing demo initiatives and eight existing benefit periods.

### Alternative if host Python is unavailable
Inside the API container the service port is 8000; use:
`docker compose exec api python seed_demo.py --base http://127.0.0.1:8000`

Only if `seed_demo.py` was copied into project root **before** Docker rebuilt its image.

## Data integrity
All seeded scenario names start with `[DEMO • SYNTHETIC]`; benefits carry `SYNTHETIC-DEMO-ONLY/` references and remain **self-reported**, not independently reconciled. Seeder **does not create, verify or approve any workflow evidence**, nor does it populate authenticated release approvals. It refuses tenant IDs other than `local-demo`.

## Test
Run `python -m pytest -q tests/test_api.py tests/test_workspaces.py tests/test_seed_demo.py` if pytest is installed. An offline test using the project's SQLite test adapter passed. No live PostgreSQL or Docker smoke test was performed in the build environment.

## R1 still to build
The board scorecard is an honest aggregate of current stored benefits; there is no reconciliation workflow yet. R1 should add typed value claims, source system provenance, adjustment/reversal entries, finance-only review, and independent verification before showing recognized value. The bootstrap bearer token architecture is for local demos and must be replaced with SSO/JWT validation before real customer deployments.
