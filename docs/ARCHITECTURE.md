# Rivu Architecture

## Request path

`Browser → Next.js → FastAPI → domain services → PostgreSQL/object storage`

AI planning is an advisory path:

`Profile + Quality + Schema → AI provider → TransformationPlan`

Execution is deterministic:

`Approved TransformationPlan → Cleaning Engine → New DatasetVersion`

## Domain boundaries

- **API** owns authentication, tenant authorization and HTTP contracts.
- **Ingestion** owns parsing and input validation.
- **Models** represent persisted business state.
- **AI** generates plans and intelligence from measured facts.
- **Transformation** executes approved operations.
- **Storage** owns raw/refined artifacts.
- **Workers** own asynchronous processing.
- **Reports** expose measured intelligence and export artifacts.

## Versioning rule

Never overwrite raw version 1. A refinement produces a new version with its own profile, quality state and artifacts.

## Production direction

For large datasets and high concurrency, move expensive profiling/refinement to durable queue-backed workers and measure database, storage and worker bottlenecks with staged load tests.
