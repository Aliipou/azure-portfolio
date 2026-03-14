# Cloud Calibration Platform — Roadmap

## Phase 1 — Foundation (complete ✓)

- [x] Go 1.22 project scaffold (`cmd/api`, `internal/` packages)
- [x] Domain models: `Device`, `CalibrationRecord`, `Measurement`
- [x] Calibration engine: deviation %, expanded uncertainty (k=2), pass/fail logic
- [x] PostgreSQL store via `pgxpool` — devices, calibration_records, calibration_measurements
- [x] SQL migration (`001_init.sql`) applied at startup
- [x] REST API with Gin: devices CRUD, calibration submit & list, analytics
- [x] Tenant middleware (`X-Tenant-ID`), role middleware (`X-User-Role`), `RequireRole` guard
- [x] Analytics endpoints: summary stats, device calibration trend
- [x] Dark-theme dashboard (`web/index.html`) with 10-second auto-refresh
- [x] Multi-stage Dockerfile (builder → alpine:3.19)
- [x] Docker Compose: Postgres 16 + API with healthcheck
- [x] GitHub Actions CI: Go build + race-detector tests, golangci-lint
- [x] Graceful shutdown via `signal.NotifyContext`

## Phase 2 — Advanced Calibration

- [ ] PKI certificate signing for calibration records (X.509 operator certificates)
- [ ] PDF calibration certificate generation (ISO 17025 compliant layout)
- [ ] Batch recalculation: recompute pass/fail when device tolerance is updated
- [ ] Multi-point calibration curves with polynomial regression
- [ ] Due-date tracking: flag devices overdue for recalibration

## Phase 3 — Alerting

- [ ] Webhook dispatch on calibration failure (configurable per tenant)
- [ ] Slack/Teams notification integration via outgoing webhooks
- [ ] Calibration expiry reminders (N days before due date)
- [ ] Alert suppression and escalation policies
- [ ] Audit log for all state-changing operations

## Phase 4 — Scalability

- [ ] TimescaleDB hypertable migration for `calibration_measurements`
- [ ] Event sourcing: `calibration_events` append-only log
- [ ] Read replicas: route analytics queries to replica pool
- [ ] Horizontal API scaling behind a load balancer
- [ ] Redis caching layer for analytics summary (short TTL)

## Phase 5 — Cloud & AKS

- [ ] Helm chart for AKS deployment (values per environment)
- [ ] Azure Workload Identity for pod-to-Postgres auth (no static credentials)
- [ ] Azure Key Vault CSI driver for secret injection
- [ ] Namespace-per-tenant isolation in AKS
- [ ] Azure Front Door + WAF in front of AKS ingress
- [ ] Defender for Containers enabled on AKS cluster
- [ ] Geo-redundant Postgres with automated failover (RTO < 4 h, RPO < 1 h)
- [ ] 10-year retention policy for calibration records (ISO 17025)
