# Security Policy — Rivu AI

## Secrets

Never commit API keys, database URLs, JWT secrets, storage credentials or deployment tokens.

Production configuration is injected by the hosting platform. Repository files contain templates only.

If a credential appears in chat, logs, screenshots, tickets, browser history or another non-secret channel, treat it as compromised and revoke/reissue it before production. Removing it from source control is not sufficient.

## Data security

- Keep object-storage buckets private.
- Use tenant-scoped object keys.
- Generate short-lived download URLs.
- Never log signed URLs, access keys, authorization headers, passwords or raw customer data.
- Encrypt data in transit and at rest.
- Keep database credentials outside source control.

## Application security

- Enforce authentication and organization authorization on every dataset operation.
- Validate extension, content type, size and parsed shape.
- Reject malformed input rather than silently repairing it.
- Treat AI output as untrusted input and validate it against a strict allowlist.
- Never execute arbitrary model-generated code.
- Keep original uploads immutable and preserve transformation lineage.

## Reporting vulnerabilities

Do not open a public GitHub issue for a security vulnerability. Report it privately with reproduction steps, affected versions and impact.
