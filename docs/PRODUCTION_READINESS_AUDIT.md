# Rivu AI — Production Readiness & Code Audit

Date: 2026-09-21
Repository: coder911i/rivu-ai
Branch: main

## Executive summary

Rivu has a real data-refinery foundation: FastAPI, PostgreSQL/SQLAlchemy, S3-compatible storage, Polars profiling, deterministic transformations, AI planning, versioned datasets, quality scoring, reports, frontend dashboards and CI/security workflows.

It is not yet defensible to certify 150,000 requests/second from source inspection alone. That capacity requires a deployed load-test environment and measured infrastructure results.

## Release blockers

1. Heavy dataset work currently uses FastAPI BackgroundTasks. Production scale needs durable queue-backed workers, retries and idempotency.
2. Several ingestion paths materialize complete files in memory. A 500 MB upload limit is not a concurrency-safe memory strategy.
3. Exact legacy .xls round-trip is not implemented; current canonical output maps legacy xls to xlsx.
4. No evidence yet of 150k RPS load testing.
5. Tenant context is not centralized; some helpers select the first membership instead of an explicit workspace context.
6. Auth lifecycle needs complete refresh-token revocation/logout, email verification and password reset flows.
7. Production must use Alembic migrations and must not rely on schema auto-creation.

## Security findings

- Environment files are ignored and must remain outside Git.
- Production validation requires DEBUG=false, a strong JWT secret, migration-only schema management and TLS storage.
- CI should use least-privilege permissions and dependency review.
- Customer data must never be committed to the repository.
- The repository cannot prove that any credential previously exposed outside Git is safe; that is an operational risk even when the current tree contains no secret.

## Data integrity finding fixed in this pass

CSV ingestion previously used silent error recovery and ragged-line truncation. That can hide malformed input or discard fields. The parser is now strict: malformed/ragged CSV input is rejected instead of silently losing data.

## Test matrix for the production gate

Auth: signup, login, wrong password, inactive user, token validation, long passwords.

Tenant security: cross-org dataset/project/report access and role boundaries.

Upload: empty, 200-byte, 1 KB, 1 MB, 200 MB, 500 MB and over-limit files.

CSV: comma, semicolon, tab, pipe, UTF-8, BOM, quoted commas, malformed quotes and ragged rows.

JSON: array, object, nested records, invalid JSON and large payloads.

Excel: xlsx, malformed workbook, multiple sheets and large workbook.

Parquet: valid, empty and schema edge cases.

Cleaning: whitespace, case, dates, datetimes, numeric, boolean, currency, phone, email, nulls, duplicates, regex, clipping, rename and drop.

AI: malformed JSON, unknown columns, invalid operations and invalid parameters.

Integrity: zero-row output, schema drift, checksum/versioning and raw-version immutability.

E2E: upload → profile → quality → AI plan → approve → execute → new version → artifact download → dashboard → PDF report.

Performance: API latency, database pool saturation, object-storage latency, worker throughput, concurrency, retries and failure recovery.

## Production scale requirement

For a 150k RPS target, validate a deployed architecture with CDN/WAF, stateless autoscaled API workers, database pooling/read scaling, durable job queues, independently scaled data workers, object storage, caching and observability.

Do not label the system 150k-RPS-ready until load-test evidence records p50/p95/p99 latency, error rate, CPU/memory, DB connections, queue depth and storage throughput.

## Current status

Repository inspection: ongoing hardening.
CSV silent-loss issue: fixed.
Repository secret/data ignore hygiene: hardened.
Production certification: not yet claimed until executable E2E and load-test evidence exists.
