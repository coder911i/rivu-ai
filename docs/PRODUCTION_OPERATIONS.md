# Rivu production operations and capacity

## Durable dataset processing

CSV uploads are committed to PostgreSQL as jobs. The separate rivu-worker Render background worker claims jobs with PostgreSQL row locks using FOR UPDATE SKIP LOCKED, processes them from object storage, and recovers jobs left in processing after a worker interruption. Keep the API and worker connected to the same PostgreSQL database and S3-compatible bucket.

## Email verification and password recovery

The API supports these endpoints:
- POST /api/v1/auth/verify-email
- POST /api/v1/auth/resend-verification
- POST /api/v1/auth/password-reset/request
- POST /api/v1/auth/password-reset/complete

Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL on the web/API service. Set FRONTEND_URL to the deployed frontend. Once SMTP delivery is verified, set REQUIRE_EMAIL_VERIFICATION=true to require verification for new signups. It remains false by default so deployments without SMTP do not lock out new accounts. Password reset and resend endpoints return a service-unavailable response until SMTP is configured. Reset and verification tokens are stored as SHA-256 hashes and expire after 30 minutes and 24 hours respectively.

## Session security

Access tokens carry a token version; refresh tokens are rotated and carry a separate version. Refresh replay is serialized with a database row lock. /auth/logout and password reset increment version counters to invalidate outstanding tokens. The frontend refreshes sessions through /auth/refresh.

## Capacity testing — do not assume 150,000 RPS

No source change can responsibly certify 150,000 requests/second. That target requires a defined workload, distributed load generators, horizontally scaled API instances, connection-pool and PostgreSQL sizing, caching, observability, and a measured test against production-like infrastructure. A single Render web service plus one worker is not a demonstrated 150k-RPS architecture.

Run a safe baseline against staging (not production) with k6 installed:

    API_BASE_URL=https://your-staging-api.example.com/api/v1 VUS=10 DURATION=1m k6 run tests/load/rivu-api.js

To include authenticated login load, supply a dedicated staging test account using LOGIN_EMAIL and LOGIN_PASSWORD. The script checks health, error rate, p95 and p99 latency; it is a baseline smoke test, not proof of 150k RPS. Increase load gradually and use a distributed k6 setup for capacity work.
