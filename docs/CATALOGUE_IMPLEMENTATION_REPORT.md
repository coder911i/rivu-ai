# Catalogue Data Entry Implementation Report

**Date:** 2026-10-29
**Repository:** `waterting/rivu-ai`
**Branch:** `main` (separate-portal changes are uncommitted)

## Implemented

- Added `/our-solutions/catalogue-data-entry`, linked from the E-commerce & Retail solution card on `/our-services`.
- Added authenticated catalogue upload for CSV, XLSX, XLS, JSON, and text-based PDF files, with clear unsupported/scanned-PDF errors from the existing parser.
- Added workbook sheet selection for multi-sheet XLS/XLSX files.
- Connected automatic mapping suggestions to editable source-to-target mapping controls, deterministic mapping, row validation, and selectable built-in or custom target templates.
- Added optional target-template file upload. Its columns are parsed and saved as an organization-associated custom template for the current backend process.
- Added searchable/filterable product records, inline edits, explicit revalidation, row issues, and original-source versus mapped-value comparison.
- Added target export preview and CSV, XLSX, and JSON downloads. Rows with errors are excluded; warnings remain available in the output.
- Updated catalogue upload to return all parsed rows so full mapping/export flows can operate beyond the ten-row suggestion sample. Upload is read in bounded byte chunks and rejects payloads over configured `MAX_UPLOAD_SIZE_MB`.
- Removed synthetic names/SKUs for missing source fields. Added validation for required custom target fields.
- Corrected local AI enrichment fallback so it does not fabricate product claims when AI credentials are unavailable; fixed its missing `re` import.
- Updated `docs/REPOSITORY_AUDIT.md` with the actual repository architecture and findings. Added ESLint ignores for generated Playwright reports so test artifacts do not enter lint checks.
- Added independent Catalogue Portal accounts/workspaces, auth endpoints and JWT key, plus a separate PostgreSQL engine. Catalogue routes authenticate against this portal and persist uploads, mapped products, and custom templates in its database.
- Added a local `catalogue-postgres` service on port 5433 with its own Docker volume, environment placeholders, and an explicit schema initializer. API returns a setup-required 503 until the independent database and signing key are configured.
- Added workspace ownership checks and Catalogue-only sign-in/sign-up/token storage. Rivu Data Refinery credentials and database are not used for Catalogue requests.

## Frontend files

- `app/our-services/page.tsx`
- `app/our-solutions/catalogue-data-entry/page.tsx`
- `app/our-solutions/catalogue-data-entry/catalogue.module.css`
- `e2e/public-smoke.spec.ts`
- `eslint.config.mjs`

## Backend files

- `backend/app/catalogue/models.py`
- `backend/app/catalogue/router.py`
- `backend/app/catalogue/mapping.py`
- `backend/app/catalogue/validator.py`
- `backend/app/catalogue/ai_enrich.py`
- `backend/tests/test_catalogue.py`
- `backend/tests/test_catalogue_api.py`

The catalogue router was already registered in `backend/app/api/v1/router.py`; no new route registration or database migration was required.

## End-to-end flow

1. Create a Catalogue Portal account or sign in; the browser stores its token separately and calls `/catalogue/auth/*`.
2. Upload a supplier catalogue to `POST /api/v1/catalogue/upload`; choose a workbook sheet when offered.
3. Review suggested mappings or manually change them; `POST /catalogue/map` maps the full source rows and validates them.
4. Search/filter and edit product rows. Inspect source versus mapped values and row-level errors/warnings. `POST /catalogue/validate` runs when the user chooses Revalidate records.
5. Select a built-in template (Standard E-Commerce, Shopify CSV, WooCommerce CSV, ERP inventory) or upload target headers to create a custom template.
6. Preview the output through `POST /catalogue/export/preview`, then download CSV, XLSX, or JSON from `POST /catalogue/export`.

These Shopify/WooCommerce templates create import files only. No native platform API integration is claimed.

## Verification and actual results

- `python -m pytest` in `backend/`: **108 passed**, one upstream ReportLab deprecation warning and pytest-asyncio fixture-scope notice. Added tests confirm independent JWT signing keys and reject a Catalogue DB URL pointing at the Rivu database.
- `npm run lint`: **0 errors, 3 existing warnings** in the dataset page hook dependencies, dashboard internal navigation, and load-test export.
- `npx tsc --noEmit`: **passed**.
- `npm run build`: **passed**; includes static route `/our-solutions/catalogue-data-entry`.
- `npm run test:e2e` with the local Next dev server: **1 passed, 1 skipped**. The public smoke flow covers Our Services → Catalogue Data Entry → separate portal sign-in. The data-refinery E2E skips without `E2E_API_URL` and its test backend/database/storage.
- `docker compose config` could not run because Docker is not installed; both compose and Render YAML parsed successfully with PyYAML.
- `git diff --check`: **passed**.

## Known limitations and remaining work

- Catalogue rows are returned as a full JSON response and held client-side; parsing still materializes file bytes and a dataframe. The current 500 MB limit does not make large imports memory-safe. Production-scale catalogues need bounded record/request limits and durable staged or streaming sessions.
- The independent Catalogue database and `CATALOGUE_JWT_SECRET` must be provisioned before Catalogue sign-in works. No separate hosted database has been provisioned by this code change.
- Production schema creation is deliberately not automatic. Run the schema initializer against the separate database; Alembic migrations for this new schema are not included yet.
- Catalogue rows persist as JSONB after upload, but imports still materialize file bytes, parsed rows, and full JSON responses in memory. The 500 MB limit is not a production-scale streaming guarantee.
- The table displays at most 250 search results at a time; it is not virtualized.
- Numeric coercion can still turn malformed source prices into zero, which is currently treated as a zero-price warning. Preserve parse failures separately to distinguish invalid input from a true zero.
- No OCR integration is configured. Scanned PDFs receive an explicit no-extractable-text error.
- No AI enrichment control was added to the product editor; configured enrichment remains available through the existing secured API. The fallback is now fact-grounded.
- No browser-driven signup/login or catalogue upload/export against a live separate database was run. Docker is unavailable, and no hosted Catalogue database or credentials have been provisioned. API integration tests exercise upload, mapping, preview, and CSV/XLSX export; new unit tests cover token-key and database separation.

## Environment and setup

Frontend: install Node dependencies using the existing lockfile, set `NEXT_PUBLIC_API_URL` to the FastAPI `/api/v1` base URL if it is not `http://127.0.0.1:8000/api/v1`, then run `npm run dev` or `npm run build`.

Backend: install `backend/requirements.txt`; configure existing refinery variables plus a separate PostgreSQL `CATALOGUE_DATABASE_URL` and unique `CATALOGUE_JWT_SECRET` (at least 32 characters). For local development, `docker compose up -d catalogue-postgres` starts the isolated database. Production must provision its own Catalogue database and apply the schema explicitly; never point it at `DATABASE_URL`. Sign-in stays unavailable until these are configured.
