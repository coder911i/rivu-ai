# Rivu AI — Production Data Refinery

**Rivu AI** turns raw customer data into validated, explainable, decision-ready datasets and intelligence.

> **Deployment model:** hosted web application. Runtime secrets live in the deployment platform, never in Git.

## Product flow

`Upload → Validate → Profile → Quality → AI Plan → Review → Deterministic Transform → Re-profile → Analytics → Report → Export`

The LLM does **not** modify customer data. It proposes an allow-listed transformation plan; the deterministic refinery engine executes approved operations and creates an immutable new dataset version.

## Repository

```
app/                         Next.js web application
lib/                         shared frontend API/branding helpers
backend/app/                 FastAPI API + refinery engine
backend/alembic/             production database migrations
backend/tests/               backend unit/integration tests
.github/workflows/           build, security and CI gates
docs/                        architecture, security and load-readiness
db/                          legacy/reference SQL schema
```

## Production architecture

- **Web:** Next.js behind CDN/edge caching.
- **API:** FastAPI/Uvicorn, horizontally replicated.
- **Database:** PostgreSQL/Neon with pooling and Alembic migrations.
- **Object storage:** private S3-compatible bucket; short-lived signed exports.
- **Refinery:** Polars deterministic transformations.
- **AI:** provider abstraction; compact profiling/quality context rather than raw full files.
- **Workers:** CPU-heavy profiling/refinement and AI calls must run outside request processes.
- **Observability:** structured logs, health checks, security scanning and load-test gates.

FastAPI's deployment guidance treats replication, memory, startup work and migrations as separate production concerns. citeturn8search0turn8search3

## Security baseline

- Runtime `.env` files are ignored by Git.
- Production schema mutation is migration-driven.
- JWT verification requires `sub`, `iat`, `exp` and `type`.
- Uploads are size-, type-, extension-, row- and column-bounded.
- Malformed CSV rows are rejected instead of silently truncated.
- Original uploads are immutable and refined versions are separate objects.
- Object storage stays private and exports use short-lived signed URLs.
- CI runs CodeQL and dependency audits.

Signed URLs are bearer credentials; expiration, IAM scope and logging therefore need tight controls. citeturn0search0turn0search3

## Scale target

The stated target is **150,000 requests/second**. This repository has **not** demonstrated that throughput yet.

To support that target, production needs:

1. CDN/edge caching for public/static traffic.
2. Stateless horizontally scaled API instances.
3. Direct-to-object-storage uploads with scoped signed upload URLs.
4. A durable queue for profiling/refinement jobs.
5. Separate worker pools for CPU-heavy data processing and AI calls.
6. PgBouncer/database pooling and bounded per-instance connections.
7. Redis or equivalent for hot metadata, rate limits and coordination.
8. Per-tenant quotas/concurrency limits.
9. Distributed tracing, metrics, logs and alerting.
10. Load tests proving p50/p95/p99 latency, error rate, saturation and recovery.

A single web service using in-process background tasks is not evidence of 150k RPS capacity. That must be proven in a production-like load test.

## Data quality contract

Rivu must preserve the source **file type** and must never silently discard rows or columns.

Every refinement must verify:

- row-count delta and explicit reason for removed rows;
- schema/column delta and explicit reason for removed/renamed columns;
- null/duplicate/type/format changes;
- checksum/version lineage;
- deterministic repeatability;
- malformed-input rejection;
- output re-parseability;
- format-specific round-trip tests.

Legacy `.xls` and `.xlsx` are separate formats. Dataframe-based Excel refinement does not currently guarantee preservation of workbook styling, formulas, macros or multiple worksheets; that must be made explicit in the product contract until workbook-preserving transforms exist.

## CI gates

Production promotion should require:

- frontend build;
- Python compilation;
- unit/integration tests;
- dependency audit with no fixable vulnerabilities;
- CodeQL;
- parser boundary/fuzz tests;
- transformation invariant tests;
- authorization tests;
- browser E2E tests;
- load-test evidence;
- migration smoke test;
- recovery/rollback test.

## Credential exposure

A credential exposed outside the deployment secret store must be considered compromised. Hiding an environment variable in Git does **not** invalidate an already exposed credential. Before a real production launch, exposed credentials must be revoked/reissued by their provider.

## License

Proprietary — WaterTing © 2026
