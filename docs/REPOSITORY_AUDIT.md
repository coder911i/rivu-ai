# Rivu AI — Comprehensive Repository Audit

**Product:** Rivu AI by WaterTing  
**Repository:** [https://github.com/waterting/rivu-ai](https://github.com/waterting/rivu-ai)  
**Date:** October 2026  
**Auditor:** Principal Software & Systems Architect  
**Branch:** `feature/catalogue-data-entry` (branched from `main`)  

---

## 1. Executive Summary

Rivu AI is an AI-native Data Refinery platform developed by WaterTing designed to transform messy, inconsistent business spreadsheets and tabular data into clean, structured, and validated datasets.

The application is structured as a decoupled full-stack platform:
- **Frontend:** Next.js 16 (React 19, TypeScript, Vanilla CSS Modules and custom design system, Lucide icons).
- **Backend:** FastAPI (Python 3.13), async SQLAlchemy 2.0 with asyncpg/psycopg2, Pydantic v2, Polars for high-throughput vectorized data processing, Pandas + openpyxl/xlrd for Excel parsing, ReportLab for branded PDF reports, and Groq SDK (`openai/gpt-oss-120b` or `llama-3.3-70b-versatile`) for AI planning and advisory reports.
- **Storage:** S3-compatible object storage via `aioboto3` (MinIO in development, AWS S3 / Backblaze B2 in production).
- **Authentication & Security:** JWT-based access/refresh token system with server-side token version revocation, PBKDF2-SHA256 password hashing, tenant/organization membership checks on every endpoint, strict CSP and security headers.
- **Background Processing:** In-process task runner (`app.workers.runner`) monitoring a `jobs` table with state transitions (`queued`, `processing`, `profiling`, `completed`, `failed`).

### Baseline Findings & Quality Status
- **Python Test Suite:** **89 tests passing** out of 89 (`pytest` in `backend/tests/`).
- **TypeScript Typecheck:** **0 errors** (`npx tsc --noEmit` exits with code 0).
- **Frontend Production Build:** **Successful** (`next build` compiled all 10 routes cleanly with Turbopack).
- **Pre-existing Frontend Lint Warning/Error:** In `app/services/page.tsx:49:5`, calling `setSignedIn(Boolean(token))` directly inside a `useEffect` triggers React 19's `react-hooks/set-state-in-effect` error. This must be resolved.
- **Missing Ingestion Capabilities:** While `.csv`, `.xlsx`, `.xls`, `.json`, and `.parquet` are supported by `parser.py`, `.pdf` catalogue parsing is not yet implemented.
- **Feature Gap:** The "Catalogue to Product Data Entry" solution is referenced in marketing concepts (`app/page.tsx`, `app/our-services/page.tsx`) but does not yet exist as an interactive, fully integrated workspace with field mapping, editable table, validation engine, dynamic templates, and multi-format product exports.

---

## 2. Repository Structure

```
c:\Users\tanis\rivu-ai
├── app/                              # Next.js App Router (Frontend)
│   ├── dashboard/                    # Main user workspace
│   │   ├── dataset/[id]/             # Dataset inspection & transformation view
│   │   │   ├── dataset.module.css
│   │   │   └── page.tsx
│   │   ├── dashboard.module.css
│   │   └── page.tsx                  # Dashboard overview, projects, datasets
│   ├── login/                        # Authentication login screen
│   ├── signup/                       # User registration screen
│   ├── reset-password/               # Password recovery
│   ├── verify-email/                 # Email verification handler
│   ├── our-services/                 # Public Business Solutions & Consultation page
│   ├── services/                     # Data Studio / Refinery live interface
│   ├── globals.css                   # Global theme tokens, typography, dark mode
│   ├── layout.tsx                    # Root layout with Inter font
│   └── page.tsx                      # Landing page with interactive engine preview
├── backend/                          # FastAPI Backend Application
│   ├── alembic/                      # Database migrations
│   │   └── versions/                 # 6 migration scripts (initial schema to align types)
│   ├── app/
│   │   ├── ai/                       # AI providers (Groq adapter, planner, factory)
│   │   ├── api/v1/                   # FastAPI endpoints (auth, projects, datasets, insights, reports, transformations)
│   │   ├── cleaning/                 # Deterministic Polars transformation engine
│   │   ├── core/                     # Config, Database (AsyncEngine), Security (JWT), Storage (S3), Logging
│   │   ├── ingestion/                # Parser (CSV, XLSX, XLS, JSON, Parquet)
│   │   ├── models/                   # SQLAlchemy 2.0 mapped models (User, Org, Project, DataSource, DatasetVersion, etc.)
│   │   ├── profiler/                 # Polars-based dataset profiling & quality calculation
│   │   ├── schemas/                  # Pydantic v2 request/response models
│   │   ├── workers/                  # Background job processor & runner
│   │   └── main.py                   # FastAPI entrypoint, CORS, CSP middleware, error handlers
│   ├── tests/                        # 89 pytest unit and integration tests
│   ├── requirements.txt              # Pinned Python dependencies
│   ├── Dockerfile                    # Containerization for API and worker
│   └── alembic.ini                   # Migration configuration
├── docs/                             # Architecture & operations documentation
├── lib/                              # Shared frontend utilities & UI components
│   ├── api.ts                        # authFetch, API configuration, error parser
│   ├── BrandLogo.tsx                 # SVG/CSS Rivu mark & typography
│   ├── CursorField.tsx               # Ambient mouse follower
│   └── ProcessingRail.tsx            # Animated progress rail
├── e2e/                              # Playwright tests
├── package.json                      # Next.js 16, React 19, TypeScript
├── render.yaml                       # Render deployment manifest (API + Worker)
├── vercel.json                       # Vercel deployment manifest (Frontend)
└── docker-compose.yml                # Local services (Postgres, MinIO, API)
```

---

## 3. Frontend Route Inventory

| Route | Purpose | Major Components | Data Sources | User Actions | Backend Dependencies | Auth Guard | Status |
|---|---|---|---|---|---|---|---|
| `/` | Landing page & brand story | Logo, Hero, EngineArt, ServiceGrid, SolutionLab | Static data, dynamic typing effect | Explore refinery stages, navigate to services/login | None | Public | Verified Working |
| `/our-services` | Business solutions, industries & consultation | IndustryGrid, Toolkit, Plans, CaseStudies, ConsultationForm | Form state, WhatsApp URI generator | Select industry/plan, fill consultation inquiry | External WhatsApp API | Public | Verified Working |
| `/services` | Data Studio: Upload, AI plan, preview, transform | Sidebar, UploadGrid, PipelineSteps, OperationsList, PreviewJson | Projects API, Upload API, AI plan API | Upload file, generate plan, preview, approve & execute | `/api/v1/projects`, `/api/v1/datasets/...` | Authenticated (Token redirect) | Partial (React 19 lint error) |
| `/dashboard` | Workspace overview: projects, datasets, live intelligence | Sidebar, Kpis, ProjectPane, DataPane, IntelligenceCard, ReportStrip | Projects API, Datasets API, Reports API | Create project, upload file, inspect report, download PDF | `/api/v1/projects`, `/api/v1/reports` | Authenticated | Verified Working |
| `/dashboard/dataset/[id]` | Deep inspection: table, column profiles, quality, refinement | ColumnGrid, QualityBars, TableViewer, Search, Sort, Pager, ExportButtons | Profile API, Quality API, Table API, Transform API | Paginate/search rows, generate plan, preview, export | `/api/v1/datasets/[id]/...` | Authenticated | Verified Working |
| `/login` | User login | LoginForm, BrandLogo, OrbitVisual | Local form state | Enter email/password, sign in, store tokens | `/api/v1/auth/login` | Public | Verified Working |
| `/signup` | User registration | SignupForm, BrandLogo | Local form state | Register account, create default workspace | `/api/v1/auth/signup` | Public | Verified Working |
| `/reset-password` | Password recovery | ResetForm | URL token, form state | Request reset link, set new password | `/api/v1/auth/password-reset` | Public | Verified Working |
| `/verify-email` | Email verification | VerificationStatus | URL token | Verify email token | `/api/v1/auth/verify-email` | Public | Verified Working |

---

## 4. Backend API Inventory

| Method | Path | Handler | Input Schema | Output Schema | Auth | Tenant Isolation | Status |
|---|---|---|---|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | `auth.signup` | `SignupRequest` | `TokenResponse` / Dict | None | Creates new Org | Verified |
| `POST` | `/api/v1/auth/login` | `auth.login` | `LoginRequest` | `TokenResponse` | None | Scoped to active Org | Verified |
| `POST` | `/api/v1/auth/refresh` | `auth.refresh_token` | `RefreshRequest` | `TokenResponse` | Refresh Token | Validates TokenVersion | Verified |
| `GET` | `/api/v1/auth/me` | `auth.me` | None | `UserResponse` | Bearer Token | Scoped to User | Verified |
| `POST` | `/api/v1/auth/logout` | `auth.logout` | None | Dict | Bearer Token | Increments TokenVersion | Verified |
| `POST` | `/api/v1/projects/` | `projects.create_project` | `ProjectCreate` | `ProjectResponse` | Bearer (Editor+) | Scoped to Org | Verified |
| `GET` | `/api/v1/projects/` | `projects.list_projects` | Query params | `List[ProjectResponse]` | Bearer | Scoped to Org | Verified |
| `GET` | `/api/v1/projects/{id}` | `projects.get_project` | Project ID | `ProjectDetailResponse` | Bearer | Scoped to Org | Verified |
| `POST` | `/api/v1/datasets/projects/{id}/upload` | `datasets.upload_dataset` | Multipart Form | 202 Accepted | Bearer (Editor+) | Scoped to Org & Project | Verified |
| `GET` | `/api/v1/datasets/{id}/profile` | `insights.profile` | Dataset ID | `DataProfileResponse` | Bearer | Scoped to Org | Verified |
| `GET` | `/api/v1/datasets/{id}/quality` | `insights.quality` | Dataset ID | `QualityReportResponse` | Bearer | Scoped to Org | Verified |
| `GET` | `/api/v1/datasets/{id}/jobs` | `insights.jobs` | Dataset ID | Job status list | Bearer | Scoped to Org | Verified |
| `POST` | `/api/v1/datasets/{id}/ai-plan` | `insights.create_ai_plan`| Dataset ID | `PlanResponse` | Bearer (Editor+) | Scoped to Org | Verified |
| `POST` | `/api/v1/datasets/{id}/transform/preview` | `transformations.preview_plan` | `ExecutePlanRequest` | Preview JSON | Bearer (Editor+) | Scoped to Org | Verified |
| `POST` | `/api/v1/datasets/{id}/transform/approve` | `transformations.approve_plan` | Plan ID | Approval status | Bearer (Editor+) | Scoped to Org | Verified |
| `POST` | `/api/v1/datasets/{id}/transform/execute` | `transformations.execute_plan` | Plan ID | Artifact URLs | Bearer (Editor+) | Scoped to Org | Verified |
| `GET` | `/api/v1/reports/{id}/pdf` | `reports.report_pdf` | Dataset ID | PDF Stream | Bearer | Scoped to Org | Verified |
| `GET` | `/api/v1/reports/{id}/dashboard` | `reports.dashboard` | Dataset ID | Intelligence JSON | Bearer | Scoped to Org | Verified |

---

## 5. Database Architecture & Models

The database uses PostgreSQL accessed through SQLAlchemy 2.0 with asyncpg:
1. **`users`**: User identity, hashed passwords (PBKDF2-SHA256), email verification tokens, password reset tokens, `token_version` for session invalidation.
2. **`organizations`**: Multi-tenant isolation container with `owner_id`, `plan`, and JSONB `settings`.
3. **`memberships`**: Links `users` to `organizations` with roles: `owner`, `admin`, `editor`, `viewer`.
4. **`projects`**: Categorizes data assets within an organization.
5. **`data_sources`**: Ingested datasets with metadata, `file_format`, `status`, and `current_version`.
6. **`dataset_versions`**: Immutable versions of a dataset. Version 1 is the raw uploaded file; subsequent versions correspond to approved transformations.
7. **`data_profiles` & `column_profiles`**: Deep column-level and dataset-level profiling stats (null counts, uniqueness, min/max/mean, detected semantic types).
8. **`quality_reports` & `quality_issues`**: Multi-dimensional quality metrics (completeness, validity, consistency, uniqueness, integrity) and granular issues.
9. **`transformation_plans` & `transformation_runs`**: Advisory plans created by AI and deterministic execution runs with audit logs.
10. **`jobs` & `job_logs`**: Async queue execution tracking.

---

## 6. AI & Data Processing Pipeline Audit

1. **AI Provider:** Configured through `app/ai/factory.py` returning `GroqClient` with `openai/gpt-oss-120b` (or `llama-3.3-70b-versatile`). It uses structured prompting and JSON completion with fallback to default structures.
2. **Deterministic Processing Boundary:** The LLM is strictly advisory. It produces a `TransformationPlan` (list of operations with parameters and confidence). The deterministic `TransformationEngine` in `app/cleaning/engine.py` executes these operations with Polars without invoking the LLM during execution.
3. **Vectorized Engine:** Polars 1.17 provides sub-second operations for 100K+ rows.
4. **Export Artifacts:** CSV, XLSX, JSON, and PDF streaming.

---

## 7. Gaps & Prioritized Action Plan

| Gap ID | Area | Description | Severity | Remediation |
|---|---|---|---|---|
| GAP-01 | Frontend | `app/services/page.tsx:49:5` triggers `react-hooks/set-state-in-effect` during `npm run lint`. | Medium | Initialize `signedIn` state lazily or synchronize without synchronous setState inside `useEffect`. |
| GAP-02 | Ingestion | PDF files cannot currently be parsed into structured records. | High | Integrate `pypdf` with table/text extraction and structure inference. |
| GAP-03 | Feature | Missing "Catalogue to Product Data Entry" solution in navigation and application. | Critical | Build dedicated route `/our-solutions/catalogue-data-entry` reachable from `/our-services` and `/` with full workspace. |
| GAP-04 | Backend | No endpoints for product catalogue field mapping, product schema validation, and template-based e-commerce exports. | Critical | Implement `/api/v1/catalogue` endpoints for upload, schema detection, mapping, product CRUD, validation, template management, and export. |
| GAP-05 | Templates | No pre-configured e-commerce/ERP target schemas (Shopify, WooCommerce, ERP Master, Custom). | High | Implement dynamic template model and default industry templates. |
