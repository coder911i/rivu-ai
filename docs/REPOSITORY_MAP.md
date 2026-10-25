# Repository Map

This document is the practical entry point for navigating the Rivu AI codebase. Keep source files in their existing application boundaries; avoid broad file moves unless imports, deployment configuration, tests, and CI are updated together.

## Top-level layout

| Path | Responsibility |
|---|---|
| `app/` | Next.js App Router pages and page-level UI |
| `lib/` | Shared frontend primitives and authenticated API client |
| `backend/app/api/v1/endpoints/` | HTTP route handlers for auth, projects, datasets, insights, transformations, and reports |
| `backend/app/ai/` | AI provider interface, Groq implementation, and transformation planner |
| `backend/app/core/` | Settings, database sessions, security, email, logging, storage, and exceptions |
| `backend/app/ingestion/` | File format detection, validation, and parsing |
| `backend/app/profiler/` | Dataset and column profiling; quality score and issue detection |
| `backend/app/cleaning/` | Deterministic, allowlisted data transformations |
| `backend/app/models/` and `backend/app/schemas/` | SQLAlchemy models and Pydantic request/response schemas |
| `backend/app/workers/` | Background dataset processor and durable database-backed job runner |
| `backend/alembic/` | Database migration history |
| `backend/tests/` | Backend unit, security, ingestion, migration, and launch-gate tests |
| `e2e/` | Playwright browser and full refinery flow tests |
| `.github/workflows/` | Frontend, backend, E2E, and security automation |
| `docs/` | Architecture, data lifecycle, operations, and readiness documentation |
| `db/` | SQL reference schema |

## Request-to-data flow

1. The frontend calls the FastAPI API through `lib/api.ts`.
2. API routes authenticate the user and resolve organization/project/dataset access.
3. Upload routes validate the input and store the raw file plus dataset/version/job records.
4. The worker parses the stored file and persists dataset/column profiles and quality findings.
5. The AI planner receives compact profile facts and returns a validated, allowlisted plan; it should not receive the complete raw dataset.
6. Users review the proposed operations and approve execution.
7. The deterministic cleaning engine applies the approved plan and stores a new version.
8. Insights/report endpoints expose quality results, downloadable artifacts, and PDF reports.

## Where to start debugging

- Login, signup, email verification, reset, token/session lifecycle: `backend/app/api/v1/endpoints/auth.py` and `backend/app/core/security.py`
- Upload and dataset endpoints: `backend/app/api/v1/endpoints/datasets.py`
- Parsing: `backend/app/ingestion/parser.py`
- Profile metrics and semantic types: `backend/app/profiler/engine.py`
- Quality scores/issues: `backend/app/profiler/quality.py`
- AI plan validation: `backend/app/ai/planner.py`
- Transform execution: `backend/app/cleaning/engine.py`
- Job lifecycle/recovery: `backend/app/workers/runner.py` and `backend/app/workers/processor.py`
- Dataset intelligence API: `backend/app/api/v1/endpoints/insights.py`
- Report generation: `backend/app/api/v1/endpoints/reports.py`
- Dashboard integration: `app/dashboard/page.tsx` and `app/dashboard/dataset/[id]/page.tsx`

## Change discipline

- Keep business logic out of page components and HTTP route handlers where a focused service/module already exists.
- Do not duplicate API paths, auth-header logic, or transformation allowlists without a documented reason.
- Never commit real environment files, credentials, customer datasets, generated reports, or build output.
- Preserve raw dataset versions; approved refinements should create new versions.
- Add or update tests with every behavior change.
- Run the relevant backend test subset, frontend build, and E2E tests before claiming a change is verified.
- For deployment-only tests, confirm `E2E_BASE_URL` and `E2E_API_URL` are configured as required.
- Prefer small pull requests that isolate one fix; do not merge a broad cleanup and a behavior change together.
