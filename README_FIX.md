# Decision OS R9 — stage initialization hotfix

## Root cause
In `ui/outcome_economics.py`, `render()` called `_pipeline_graph(stage, count)` before defining `stage`, producing `UnboundLocalError`. This can occur for valid sessions, not only unusual status values. The new code resolves and validates the saved `r8_stage` before rendering the graph.

## Changes
- `ui/outcome_economics.py`: initialize/validate stage before graph; preserve existing R8 API integration and UI.
- `tests/test_r9_render_regression.py`: execute `render()` with missing, invalid and valid saved stage and assert the actual graph receives a valid value.
- Existing R8 and R9 tests included.

## Local validation
21 tests passed (18 prior + 3 new rendering cases). `python -m py_compile ui/outcome_economics.py` succeeded. This test suite stubs Streamlit and uses test API data; live Windows Docker/browser verification remains to be done.

## Install
1. Back up `<project>/ui/outcome_economics.py`.
2. Copy the ZIP's `ui/outcome_economics.py` into `<project>/ui/outcome_economics.py`.
3. Optionally copy tests to your project's tests folder.
4. From the Decision OS root run `python -m pytest tests/test_r9_render_regression.py -q`.
5. Run `docker compose up -d --build ui`; refresh `http://127.0.0.1:8502`.

No backend/database modification. This hotfix does not implement autonomous agent execution, live Jenkins, or additional cryptographic approval features.

## Lint guidance
Do **not** blindly run `ruff check --fix .` on a legacy FastAPI tree with B008 and BLE001 warnings. Apply baseline-scoped linting/new-file policy first and review each fix. In FastAPI, `Depends(...)` defaults are an established framework pattern; configure appropriate per-file ignores or modern `Annotated` dependency syntax in a dedicated refactor.
