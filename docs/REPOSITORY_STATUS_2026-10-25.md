# Repository Status Snapshot — 2026-10-25

**Repository:** `coder911i/rivu-ai`  
**Branch inspected:** `main`  
**Purpose:** Current evidence snapshot to supplement older production-readiness audits. This is not a claim that every function has been executed.

## Summary

The codebase is organized into a Next.js frontend, FastAPI backend, AI planner/provider layer, deterministic cleaning engine, profiling/quality modules, database-backed job worker, object storage adapter, and test/CI directories.

**Release status: NOT FULLY VERIFIED.** Source implementation exists for core flows, but available CI evidence includes a failed public smoke test and a skipped full refinery integration test.

## Current CI evidence

Workflow run: [GitHub Actions run 40125756814](https://github.com/coder911i/rivu-ai/actions/runs/40125756814)

- **Failed:** `e2e/public-smoke.spec.ts` could not find the exact visible text `AI-NATIVE DATA REFINERY` on the deployed homepage.
- **Skipped:** `e2e/rivu-full-flow.spec.ts` skips when `E2E_API_URL` is not configured. The recorded run had an empty `E2E_API_URL`.
- **Meaning:** The public UI smoke test needs to be aligned with the intended current copy, or the page needs to restore that copy. The core upload-to-report flow remains unverified by that run. A failed text assertion alone does not prove the entire website is down.

## Implemented in source; execution still needs evidence

| Area | Code entry points | Evidence needed before marking PASS |
|---|---|---|
| Authentication | `backend/app/api/v1/endpoints/auth.py`, `backend/app/core/security.py` | Signup/login, verification, reset, logout/refresh, expiry and invalid-token tests |
| Projects/workspaces | `backend/app/api/v1/endpoints/projects.py` | CRUD, role enforcement, active-workspace and cross-tenant tests |
| Ingestion | `backend/app/api/v1/endpoints/datasets.py`, `backend/app/ingestion/parser.py` | CSV/XLSX/XLS/JSON/Parquet fixtures, malformed inputs, size and concurrency tests |
| Profiling | `backend/app/profiler/engine.py` | Expected metrics on known datasets, empty/null-heavy and high-cardinality cases |
| Quality | `backend/app/profiler/quality.py` | Known-score fixtures and severity/count correctness |
| AI plan | `backend/app/ai/planner.py`, `backend/app/ai/groq_client.py` | Provider failure, invalid JSON, unknown columns and invalid-parameter rejection |
| Transformations | `backend/app/cleaning/engine.py`, `backend/app/api/v1/endpoints/transformations.py` | Per-operation tests, preview parity, approval enforcement, version immutability |
| Worker | `backend/app/workers/runner.py`, `backend/app/workers/processor.py` | Actual worker deployment, retry/recovery, duplicate-job/idempotency and failure-path tests |
| Reports/exports | `backend/app/api/v1/endpoints/reports.py` | Valid artifact contents, supported formats, expiry and generation-failure tests |
| Frontend | `app/`, `lib/api.ts` | Production build, route/navigation smoke tests and authenticated flow tests |

“Code entry points” means the implementation is present in the inspected source. It does **not** mean each row has passed a live functional test.

## Immediate actions, ordered

1. Fix the public smoke test mismatch using the intended homepage copy/accessible locator; do not merely weaken the assertion to make CI green.
2. Configure a dedicated test backend and the GitHub Actions secret `E2E_API_URL` so the full flow is actually executed.
3. Run backend tests and frontend build; retain the full logs and report failures without marking skipped tests as passed.
4. Verify the worker is deployed as a separate process and can read the same database/object-storage configuration as the API.
5. Exercise tenant isolation and role-boundary tests across every dataset, transformation, artifact and report endpoint.
6. Measure memory, latency, queue depth and concurrency with representative files before setting production scale claims.
7. Reconcile older audit documents with current code before treating their findings as current; older notes about missing worker/auth flows may have been superseded by subsequent changes.

## Scope limits

This snapshot was prepared from repository source and the cited workflow log. No production credentials were used, no customer data was accessed, and no deployed backend/API end-to-end run was completed as part of this snapshot. Do not treat any unexecuted test as a pass.
