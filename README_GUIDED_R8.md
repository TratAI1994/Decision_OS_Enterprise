# Decision OS — R8 Guided Outcome Economics UI

## What changed
UI-only replacement of `ui/outcome_economics.py`. Based on the existing R8 API contract; no database migrations and no backend changes.

- AWS-console-inspired dark executive hero (not a copy of AWS branding), clear breadcrumbs, responsive two-column layout.
- A visible three-step readiness flow: expected benefit → self-reported result → independent finance attestation.
- Explicit Overview / Plan / Measure / Finance / Audit navigation using reactive Streamlit `st.radio`, not tabs with inaccessible active-tab state.
- Per-screen contextual help, three suggested questions per screen, an editable question box and deterministic responses.
- Inline validations before submit, including finite decimal amounts and 2-decimal precision. Server still validates all submissions.
- A failed or missing API result never becomes a fictitious finance value.
- Clearly explains attribution, GL/ERP evidence limits and event-hash limits.

## Installation — safe overlay
Back up the file `ui/outcome_economics.py`, then copy only the `ui/outcome_economics.py` path from the ZIP into your root directory. DO NOT overwrite the original backend or `ui/app.py` because this patch does not need it.

```
cd D:\Users\atmm1\Decision_OS_Enterprise
python -m pytest tests/test_r8_guided_ui.py -q
docker compose up -d --build ui
```

Open `http://127.0.0.1:8502`, select **Decision Infrastructure → Outcome Economics**.

## Adoption walkthrough
1. Select an authorized decision and read Overview for existing evidence and missing steps.
2. On **1 · Plan**, record period, expected benefit, methodology and forecast source.
3. On **2 · Measure**, report actual observed benefit and provenance (not verified).
4. Switch to the authenticated **finance** role and complete **3 · Finance review**, using a GL/ERP source pointer. Reporter cannot approve own claim. A source pointer is not an ERP connector validation.
5. Open **4 · Audit trail** to inspect who appended each event, the ordered hashes, and limitations.
6. Use the **Screen guide** on the right. Clicking a suggested question populates the text box; use **Explain this step** for a bounded answer.

## Security / architecture review
- API enforces authorization, tenant-scoping, role/SoD gates and period/currency checks; the UI performs convenience validation only.
- Copilot is deterministic static guidance for this workflow. It does **not** retrieve external documents, read ERP ledgers, grant approvals or fabricate data.
- This R8 API records finance *attestation*, not fully independently verified financial transactions. Real ERP integration, cryptographic anchoring, approval-time frozen value snapshots and governed correction events remain needed.
- Do not embed bearer credentials in screenshots or exported JSON; the export contains event details and should be handled according to data policy.
- Presenting a financial variance does not prove attribution of savings to AI.

## Tests and limits
10 isolated helper tests passed in this environment; they do not constitute browser, PostgreSQL, WCAG audit or end-to-end security tests. Real form UX and API behavior must still be exercised against your Windows Docker deployment. Existing R8 API tests should remain in your original project's `tests` directory.

## Further priority
Separate follow-up hardening: add an approval-time R7.1 snapshot, then production-grade authenticated finance ERP connectors; patch any unverified labels and negative-base Monte Carlo issues remaining elsewhere in the UI. This UI patch does not claim to resolve those unrelated modules.
