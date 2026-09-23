# Production Checklist

## Application
- [ ] Frontend build passes
- [ ] Backend tests pass
- [ ] Complete E2E flow passes
- [ ] Auth and tenant isolation verified

## Infrastructure
- [ ] PostgreSQL configured
- [ ] TLS object storage configured
- [ ] Production origins configured
- [ ] Strong JWT secret configured
- [ ] AI provider configured
- [ ] Migrations applied

## Reliability
- [ ] Worker/queue strategy validated for expected scale
- [ ] p50/p95/p99 measured
- [ ] Error rate measured
- [ ] Database connection usage measured
- [ ] Storage throughput measured
- [ ] Queue depth monitored

## Security
- [ ] No secrets committed
- [ ] Dependency/security scans pass
- [ ] CI permissions are least privilege
- [ ] Production deployment protection enabled
