# Production Load & End-to-End Test Plan

## Target

Validate the hosted Rivu application against the declared **150,000 requests/second** target and realistic data-refinery workloads.

## Test lanes

### L0 — Static
TypeScript build; Python compile; dependency audit; CodeQL; secret scan; migration validation.

### L1 — Unit
Authentication/token validation; parser format detection; CSV delimiter/encoding; malformed-row rejection; JSON shape handling; every transformation operation; quality scoring; report serialization.

### L2 — Contract
Signup/login/refresh; project CRUD; upload lifecycle; profiling lifecycle; AI plan validation; approve/execute lifecycle; dashboard/report payloads; export authorization.

### L3 — Dataset matrix

Run every supported format: CSV, XLSX, XLS, JSON, Parquet.

Sizes and adversarial cases:
- 200-byte file
- 1 KB file
- 200-character cell
- 1,000-character cell
- empty file
- 1 row
- 1,000 rows
- 100,000 rows
- maximum columns
- maximum rows
- near 500 MB
- malformed encoding
- malformed quoting
- ragged CSV
- duplicate rows
- null-heavy data
- mixed types
- extreme numeric values
- Unicode/emoji
- formula/macro-containing workbooks where applicable

### L4 — Invariants

For every successful refinement:
- output parses again;
- source version is unchanged;
- every removed row has a recorded reason;
- schema changes are explainable;
- checksum is recorded;
- repeated execution is deterministic;
- quality is re-profiled after transformation.

### L5 — Security

Cross-tenant access must fail; viewers cannot mutate; expired/invalid tokens fail; refresh tokens cannot authenticate access endpoints; malformed JWT claims fail; oversized uploads fail; invalid MIME/extension combinations fail; signed URLs are short-lived; secrets/raw customer data never enter logs.

### L6 — Load

Test public pages, authenticated reads, upload initialization, dashboard/report reads, signed-object downloads, queue submission and worker throughput.

Measure p50/p95/p99 latency, error rate, CPU, memory, database connections, queue depth, object-store latency and AI-provider latency.

Do not label the product production-ready until the dependency chain has headroom and failure/recovery tests pass.
