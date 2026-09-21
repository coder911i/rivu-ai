# Enterprise Audit Snapshot

Date: 2026-09-21

## Scope

Static inspection of the repository architecture, backend ingestion/refinery/auth/reporting paths, frontend application/API integration, deployment configuration, Alembic setup, CI workflows, dependency audit output and recent GitHub Actions results.

This document distinguishes source inspection from runtime proof. A line-by-line execution claim would be misleading: software is validated by behavior-focused tests, invariants, integration tests, fuzz/boundary tests and load tests.

## Confirmed findings

### Critical
1. A credential was previously exposed outside the deployment secret store. Production requires revocation/reissue; hiding .env is not sufficient.
2. Main dependency audit reported 39 known vulnerabilities across 7 Python packages.
3. The existing architecture does not prove 150k RPS.
4. Startup create_all() was used instead of a production migration lifecycle.

### High
- CSV parsing previously used permissive error/truncation behavior.
- Dataset processing uses in-process background execution rather than a durable worker queue.
- Several endpoints select the first organization membership instead of an explicit tenant context.
- JWT refresh tokens have no server-side revocation/session lifecycle.
- Browser tokens are stored in localStorage rather than httpOnly secure cookies.
- Dataframe-based Excel processing cannot guarantee preservation of workbook styling/formulas/macros/multiple worksheets.
- Large dataset processing materializes full files in memory in worker code.

## Hardening implemented in PR #2

- PyJWT migration.
- Dependency upgrades and removal of the incompatible direct boto3 pin.
- Production schema auto-creation disabled.
- Alembic initial baseline.
- Non-root API container.
- Strict parser with row/column/size bounds.
- XLS distinguished from XLSX.
- Parser and refinery invariant tests.
- Production architecture README.
- Security policy.
- Rigorous E2E/load-test plan.

## Required before production

- Green dependency audit and CodeQL.
- Green frontend/backend tests.
- Empty-database migration smoke test.
- Two-tenant authorization matrix.
- Full CSV/XLSX/XLS/JSON/Parquet round-trip matrix.
- Fuzz/adversarial data tests.
- Durable queue + isolated worker pools.
- Direct object-storage upload path.
- httpOnly secure session cookies.
- Rate limits/quotas/concurrency controls.
- Observability and alerting.
- Production-like load test at and above the 150k RPS target.
- Credential revocation/reissue.

## Buyer-facing position

Rivu can be presented as having a substantial working engineering foundation and an active production-hardening program. It should not be represented as having already proven enterprise-scale throughput until the load and recovery gates above have passed.