# Rivu AI — Data Refinery & Intelligence

Rivu turns messy business data into cleaned, validated and explainable datasets plus intelligence reports.

## Product flow

Upload → Validate → Profile → Quality → AI Plan → Review/Approve → Deterministic Transform → Re-profile → Validate → Download → Report

## Architecture

- Web: Next.js + TypeScript
- API: FastAPI + SQLAlchemy async
- Processing: Polars + pandas/openpyxl
- Database: PostgreSQL
- Storage: S3-compatible object storage
- AI: provider abstraction with Groq support
- Auth: JWT + PBKDF2-SHA256 password hashing
- CI: GitHub Actions, CodeQL, dependency auditing

## Repository

app/ — Next.js product UI
lib/ — frontend API and brand utilities
backend/app/ — FastAPI application
backend/tests/ — backend tests
backend/alembic/ — production migrations
db/ — database reference schema
.github/workflows/ — CI and security

## Production configuration

Production secrets must be supplied through the deployment platform secret/environment store. Never commit .env files, customer datasets or credentials.

Production requires:
- APP_ENV=production
- DEBUG=false
- strong JWT_SECRET
- PostgreSQL
- TLS-enabled object storage
- production ALLOWED_ORIGINS
- AI provider configuration
- AUTO_CREATE_SCHEMA=false
- Alembic migrations

## Data integrity

Raw version 1 is immutable. AI only produces a structured transformation plan. The deterministic cleaning engine executes approved operations. Every refinement creates a new version.

Malformed CSV input is rejected rather than silently dropping fields.

## Scale

150,000 requests/second is a deployment-level target, not something source code alone can prove. Before launch, run staged load tests and measure p50/p95/p99 latency, errors, CPU/memory, database connections, queue depth and storage throughput.

At very high traffic, heavy profiling/refinement must run on durable queue-backed workers rather than process-local request background tasks.

## Security

Keep secrets out of Git, enforce least-privilege CI permissions, run dependency/security scanning and protect production deployments. GitHub recommends dependency review and short-lived cloud credentials such as OIDC where supported.

## Release gate

A production release requires passing frontend build, backend tests, security scans, auth/tenant isolation tests, dataset-format tests, transformation tests, complete E2E tests and deployed load tests.

Proprietary — WaterTing © 2026
