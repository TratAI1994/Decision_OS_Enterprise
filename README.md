# R9 Guided Control Plane — Decision OS

## What changed

This is an incremental, **UI-only replacement** for `ui/outcome_economics.py`. It is visually inspired by the dark workflow diagrams of managed pipeline consoles, not an AWS asset or a replica. It preserves the existing R8 API paths, finance-only attestation and reporter/attester separation of duties, as implemented in R8's backend. It does not change the backend, API routes, migrations or `ui/app.py`.

- Dark console header with status context and a connected Graphviz workflow map (expected value → observation → finance review → event replay)
- Clickable workflow stages, each backed by existing R8 forms and API calls
- Right-side contextual evidence advisor, questions and prerequisites
- Explicit assurance/readiness panel that **withholds** snapshot, kill-criteria and independently validated ERP/GL claims
- Deterministic stage-progress calculation based on retrieved authoritative events
- All navigational behavior uses Streamlit controls; the graph is a depiction, not a clickable editor

## Installation (existing R8 must already work)

1. Back up `D:\Users\atmm1\Decision_OS_Enterprise\ui\outcome_economics.py`.
2. Copy the contained `ui/outcome_economics.py` to that directory (retain your existing API/backend files).
3. In your Windows terminal:

```powershell
cd D:\Users\atmm1\Decision_OS_Enterprise
python -m pytest tests/test_r9_control_plane.py -q
# Tests require pytest installed in whichever Python environment runs them.
docker compose up -d --build ui
```

4. Navigate to **Decision Infrastructure → Outcome Economics** at http://127.0.0.1:8502.

If the Graphviz Python and native `dot` packages are missing, install them in the UI image (other Decision OS modules also use Graphviz). The new visual graph falls back to textual step navigation when Graphviz import fails; rendering availability depends on the deployed Streamlit runtime.

## Why this is not yet R9 governance-complete

This release improves discoverability and adoption. It does **not** implement the missing R7.1 atomic approval-time snapshot, predeclared kill criterion enforcement, independently trusted digital signatures or direct authenticated ERP/GL retrieval. The assurance panel says **Not verified** for controls not exposed by the R8 API. Existing R8 finance attestations record a finance user and source reference, not independent source-system retrieval.

### Recommended R9 backend gates

1. Atomic approval-time snapshot in one PostgreSQL transaction covering decision version, evidence digests, assumption versions, expected financial baseline, policy versions and preapproved kill criteria. Capture only during the actual authoritative approval operation.
2. Server-enforced kill criterion evaluation against consecutive verified observation periods; create policy-controlled review events, *not* automatic financial termination.
3. As-of replay plus database tests for mutation attempts, role separation, concurrent approvals, tenant isolation, missing observations and tampered source records.
4. Finance evidence reconciliation adapter with delegated identity and record hashes; avoid claiming verified savings from a free-text GL reference.
5. Controlled agent execution only after server-side authorization with fresh policy checks.

## Tests

18 local unit tests passed (the prior R8 UI test suite plus eight new tests). No live Windows Docker / PostgreSQL / browser test has been run here. The graph and CSS should be visually checked in both Streamlit dark and light settings and at narrow viewport widths.
