# Rivu AI Repository Audit

**Repository:** `waterting/rivu-ai`
**Audited:** 2026-10-29
**Checkout:** `main` tracking `origin/main` at audit start; working tree clean.
**Scope:** application source, tests, database models/migrations, catalogue modules, and deployment configuration.

## Executive summary

Rivu is a Next.js 16 / React 19 TypeScript application backed by a FastAPI service. The existing product is an authenticated, organization-scoped data refinery: users upload datasets into projects, inspect profiles and quality, request AI transformation suggestions, preview them, approve execution, and download versioned output artifacts. The catalogue backend was already implemented and mounted at `/api/v1/catalogue`; the main missing piece was an interactive frontend. A new authenticated Catalogue Data Entry workflow now connects to those existing endpoints.

The application persists user, organization, membership, project, dataset, profile, quality, job, and transformation records in the Rivu SQLAlchemy/PostgreSQL database. Raw/refined dataset objects use configured S3-compatible storage. Catalogue Portal uses separate account/workspace tables, a separate SQLAlchemy engine/database URL, and an independent JWT signing key. Uploaded rows, mappings, products, and custom templates persist in that Catalogue database and are workspace-scoped. The Catalogue database must be separately provisioned and initialized; until then, Catalogue API calls return a setup-required 503.

## Frontend routes and actions

| Route | Main work | Backend connections / status |
|---|---|---|
| `/` | Public Rivu landing page, navigation and solution explorer | Static/interactive content; no data API calls |
| `/our-services` | Industry solutions, engagement plans, consultation form | Consultation form opens a prefilled WhatsApp URL; no silent form submission. E-commerce now links to `/our-solutions/catalogue-data-entry` |
| `/our-solutions/catalogue-data-entry` | Upload catalogue, map source columns, edit/search/filter products, inspect row issues, validate, choose template, preview and download | `/catalogue/upload`, `/catalogue/map`, `/catalogue/validate`, `/catalogue/templates`, `/catalogue/export/preview`, `/catalogue/export`; requires an access token |
| `/services` | Existing Data Studio upload, profile, AI plan, preview, approve/execute, artifact downloads | `/projects/`, `/datasets/projects/{id}/upload`, dataset profile/quality/jobs, AI plan and transform routes |
| `/dashboard` | Workspace overview, project/dataset management and reports | Project, dataset, and report API routes |
| `/dashboard/dataset/[id]` | Dataset profile, quality, row explorer, transformation and exports | Dataset intelligence and transformation API routes |
| `/login`, `/signup`, `/reset-password`, `/verify-email` | Authentication and account recovery | `/auth/*` routes |

The catalogue page keeps original uploaded rows in browser state for its session. It displays the source row beside mapped product values. The table currently renders at most 250 matches at a time and asks users to narrow searches for later rows; it does not use a virtualized grid.

## Backend routes and business logic

FastAPI registers `app.api.v1.router.api_router` under `/api/v1`; this router includes auth, projects, datasets, insights, reports, transformations, and catalogue.

Catalogue endpoints in `backend/app/catalogue/router.py`:

| Method and route | Behavior |
|---|---|
| `POST /catalogue/upload` | Authenticated catalogue parsing, column/sample inference, available-template response and full parsed rows for the client mapping session |
| `POST /catalogue/map` | Applies source mappings and deterministic type/format conversion, then validates records |
| `POST /catalogue/validate` | Revalidates submitted product rows after edits or target-template changes |
| `POST /catalogue/enrich` | Advisory AI enrichment using the configured Groq provider; now does not invent missing descriptions or categories in local fallback mode |
| `GET /catalogue/templates` | Built-in plus process-local organization custom templates |
| `POST /catalogue/templates` | Saves a process-local custom template |
| `DELETE /catalogue/templates/{template_id}` | Deletes a process-local custom template; built-ins are protected |
| `POST /catalogue/export/preview` | Previews template columns and sample output rows |
| `POST /catalogue/export` | Produces CSV, XLSX or JSON bytes |

The catalogue package contains separate parser, mapping, validator, template, exporter, and enrichment modules. File parsing uses pandas/openpyxl/xlrd, pypdf text extraction, and existing CSV encoding/delimiter helpers. Scanned PDFs fail with an explicit no-extractable-text validation message; no OCR integration is configured. Mapping uses canonical field synonyms, fuzzy matching, value heuristics, and deterministic coercion. Validation covers required name/SKU, duplicate SKU, price/sale price, inventory, URLs, and template-required fields. Product attributes not mapped to canonical fields are retained in custom attributes.

The general ingestion parser additionally supports Parquet, but catalogue product import does not. The catalogue UI accepts CSV, XLSX, XLS, JSON and PDF. Shopify/WooCommerce template-shaped exports exist; these are file exports only, not native storefront integrations.

## Frontend action tracing and gaps

- Login/signup store access and refresh tokens; `lib/api.ts` adds bearer auth, retries after token refresh, and converts network/API failures into actionable errors.
- Data Studio actions are connected to real API routes and preserve the approve-before-execute refinement workflow.
- Catalogue upload previously returned only ten sample rows, making complete mapping impossible. Upload now returns all parsed records, and the catalogue UI maps those rows instead of the sample.
- Mapping previously substituted synthetic product names and SKUs for missing source values. Those substitutions are removed so required-field validation can report missing values.
- The catalogue table edits canonical product fields locally and sends all records to the real validation endpoint on explicit revalidation. The export preview excludes rows classified as errors; warning/valid rows are included.
- Custom target-template files can be parsed and their headers saved as workspace-owned templates in the separate Catalogue database.
- Existing `/services` accepts CSV/JSON/XLSX/XLS/Parquet; it is the data refinery and remains distinct from catalogue-specific PDF support.
- No native Shopify, WooCommerce, ERP API, OCR, saved mapping recipe, or durable catalogue job/session integration was found.

## Data, authentication, tenancy, and security

- SQLAlchemy models are in `backend/app/models/`; schema changes are maintained in `backend/alembic/versions/`, with `db/schema.sql` as reference material.
- Rivu organization membership roles include owner, admin, editor, and viewer. Catalogue has a separate account/workspace owner identity realm and its own JWT auth dependency; catalogue routes do not accept Rivu Data Refinery tokens.
- Catalogue APIs persist sessions and product records in the isolated Catalogue database. Session and template access is scoped to the signed-in Catalogue workspace.
- Catalogue upload validates extension, rejects empty files, and reads in bounded chunks up to configured `MAX_UPLOAD_SIZE_MB` (default 500 MB). Parsing still requires the complete byte buffer and dataframe in memory; returning all rows as JSON also makes large catalogues memory- and bandwidth-intensive. A streaming/persistent catalogue session is needed for genuinely large inputs.
- Parser failures represented as validation errors return 400. Unexpected catalogue parser failures are logged and return a generic message instead of echoing exception details. Existing global development error behavior still returns detail when `DEBUG` is enabled.
- CSV/XLSX/JSON export is generated in memory. There is no persistent catalogue export artifact or background job.
- `backend/app/core/security.py` implements Rivu JWT/password and organization access. `backend/app/catalogue/auth.py` signs Catalogue JWTs with the separate `CATALOGUE_JWT_SECRET`. Production security checks require non-default JWT and S3 configuration, TLS, disabled debug, and disabled automatic schema creation.

## Environment and deployment

Frontend configuration: `NEXT_PUBLIC_API_URL` (defaults to `http://127.0.0.1:8000/api/v1` in `lib/api.ts`). Next.js deployment is described in `vercel.json`.

Backend variables are documented in `backend/.env.example` (root `.env.example` is also present): database URLs, JWT configuration, `DEFAULT_AI_PROVIDER=groq`, `GROQ_API_KEY`, `GROQ_MODEL`, S3 endpoint/credentials/bucket/region/TLS, allowed origins, debug/logging, upload size, and worker/profile limits. Render API/worker setup is in `render.yaml`; local dependencies are in `docker-compose.yml`; backend image setup is in `backend/Dockerfile`.

## Tests, broken imports, and code-health findings

- Existing Python coverage includes authentication, workspace security, ingestion formats, catalogue parser/mapping/validation/templates/export, migrations, cleaning, and launch gate. The baseline at audit start had 102 passing tests.
- Existing Playwright coverage has public smoke coverage plus an end-to-end data-refinery flow. The latter skips unless `E2E_API_URL` is configured and a test backend/database/storage are available.
- `npm run lint` reports three existing warnings (dataset page hook dependency, dashboard internal `location.href`, anonymous load-test export); no errors.
- Current catalogue modules compile and their routes are registered. Prior documentation incorrectly claimed the catalogue backend and PDF parser were missing; the codebase already contains both (text PDF extraction only).
- Existing mapping conversion of unparseable numeric strings can coerce them to zero; zero price is a warning and can therefore lose the distinction between invalid input and a true zero. This remains a validation limitation.
- Custom templates are process-local and can disappear on worker restart or route to another worker. A persistent organization-scoped store is needed for reliable reuse.
- The full-row JSON upload response is suitable for moderate catalogues only. Limits on total record count/request size and a durable streaming or staged catalogue session should be considered before production use at large scale.
- No new parser dependency or database was introduced for this implementation.
