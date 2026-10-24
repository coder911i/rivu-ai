# Rivu AI — Production Readiness & Engineering Audit

**Audit date:** 2026-09-22
**Scope:** source tree, CI, ingestion, transformation, auth, storage, reporting and frontend integration.

## Executive result
Rivu has a real SaaS/data-refinery foundation, but the current repository is **not yet evidence-backed for a 150,000 requests/second production launch**. That target requires staged distributed load tests against the actual deployment, database, object storage, CDN and worker architecture.

## Verified strengths
- Next.js frontend + FastAPI API + PostgreSQL + S3-compatible storage.
- Immutable dataset-version model for raw/refined data.
- LLM produces plans; deterministic engine executes allowlisted operations.
- CSV parsing is strict: ragged rows are not silently truncated.
- AI transformation plans require explicit approval at the API layer.
- Production configuration rejects development JWT/S3 settings.
- CI contains Python tests, dependency audits, dependency review and CodeQL.
- Environment files are ignored by Git.

## Findings
### CRITICAL — release blockers
1. 150k RPS is not demonstrated by deployed load-test evidence.
2. Heavy processing still uses FastAPI BackgroundTasks; production scale needs durable queue-backed workers with retry, idempotency and backpressure.
3. Dataset processing materializes large files/dataframes; peak memory must be measured and bounded.
4. Organization selection is not consistently explicit; several endpoints select the first membership. Centralize tenant context before multi-tenant enterprise use.

### HIGH
5. CSV encoding/delimiter is detected but not persisted, so exact CSV presentation preservation is not guaranteed.
6. Legacy XLS previously collapsed into XLSX. This audit adds distinct XLS parsing/output support.
7. Refresh tokens lack persisted revocation/rotation families.
8. Email verification and password-reset workflows are absent.
9. CI is not a deployed end-to-end gate for upload → profile → AI plan → approval → transformation → artifact → report.

### MEDIUM
10. PDF report is branded text but does not embed the supplied visual logo asset.
11. Report generation calls AI synchronously.
12. Refinement generates multiple full artifact copies, increasing storage/CPU cost.
13. Presigned downloads need production audit logging, tenant-bound authorization and lifecycle validation.
14. Observability needs queue, processing, storage, DB-pool, AI-latency and error metrics.

## Data-format test matrix added
- CSV strict ragged-row rejection
- CSV delimiter detection
- UTF-8/non-ASCII values
- JSON records
- Parquet signature validation
- XLSX signature validation
- XLS format identification/parser path
- deterministic whitespace/lowercase cleaning
- duplicate removal
- invalid-column isolation without dataframe corruption

## Production architecture for the stated scale
`CDN/WAF → load balancer → stateless Next.js/API replicas → Redis/queue → dedicated ingestion/profile/refinement workers → PostgreSQL + pooling/read replicas → object storage/CDN`

Large-data processing should leave request workers. Prefer direct multipart object-storage uploads with short-lived upload URLs, then enqueue processing by object key.

## Release gates
- frontend build + lint
- backend unit/integration tests
- tenant-isolation tests
- auth/refresh/revocation tests
- malformed/malicious file tests
- all supported-format round trips
- transformation invariants
- artifact checksum/version tests
- deployed E2E
- staged 1k → 10k → 50k → 150k RPS tests
- p50/p95/p99 latency and error budgets
- DB/CPU/memory/queue/storage saturation measurements
- retry/idempotency/failure tests
- security and secret scanning
- rollback test

## Security
Secrets must remain outside Git and inside the production platform secret manager. GitHub recommends least-privilege workflow permissions and short-lived cloud credentials such as OIDC where supported.

## Current conclusion
**Engineering status: hardening / verification in progress.** Do not claim 150k RPS production readiness until deployed load-test evidence exists. The repository now has stronger format handling and deterministic cleaning tests, but the remaining architecture and tenant/security gates are material release requirements.