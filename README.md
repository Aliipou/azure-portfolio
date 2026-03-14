# Cloud Calibration Platform

> Multi-tenant ISO 17025 calibration records platform — device management, measurement ingestion, anomaly detection, and certificate generation on Azure.

[![CI](https://github.com/Aliipou/cloud-calibration-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Aliipou/cloud-calibration-platform/actions/workflows/ci.yml)
[![Security Scan](https://github.com/Aliipou/cloud-calibration-platform/actions/workflows/security-scan.yml/badge.svg)](https://github.com/Aliipou/cloud-calibration-platform/actions/workflows/security-scan.yml)
[![codecov](https://codecov.io/gh/Aliipou/cloud-calibration-platform/branch/main/graph/badge.svg)](https://codecov.io/gh/Aliipou/cloud-calibration-platform)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Problem & Requirements

### Functional Requirements

- Register and manage calibration instruments (pressure gauges, thermometers, electrical meters, flow instruments) per tenant
- Ingest calibration measurements with measured value, reference value, uncertainty, unit, and ambient conditions
- Evaluate each measurement against device-specific tolerance; flag anomalies before certificates are issued
- Store full calibration records with operator attribution and audit trail for every write operation
- Generate ISO 17025-formatted PDF calibration certificates on demand
- Expose aggregated analytics — pass/fail rates, device trend, anomaly counts — per tenant
- Enforce role-based access: Admin, Operator, Viewer with explicit permission boundaries

### Non-Functional Requirements

- **ISO 17025 data retention** — calibration records retained for 10 years minimum; implemented via Blob lifecycle (hot → cool → archive)
- **Multi-tenant isolation** — tenant data never accessible across tenant boundaries; enforced at query layer and validated in tests
- **Sub-100 ms API response (p99)** — synchronous device/analytics reads; measurement ingestion is async (202 Accepted + queue)
- **Zero cross-tenant data leaks** — every SQL query is predicated on `tenant_id`; store interface enforces it at the type level
- **Horizontal scalability** — stateless API and worker containers; KEDA scales workers to zero when idle
- **EU data residency** — all Azure resources provisioned in North Europe (primary) and West Europe (DR replica) only; required by GDPR and national metrology regulations
- **RTO < 4 hours, RPO < 1 hour** — zone-redundant PostgreSQL Flexible Server, geo-redundant Blob Storage

### Capacity Estimates

| Metric | Value |
|--------|-------|
| Tenants | 100 |
| Devices per tenant | ~1,000 |
| Calibrations per device per day | ~0.5 |
| Measurements per calibration | ~10 |
| Storage per tenant per year | ~50 MB |
| Total storage (100 tenants, 10 years) | ~50 GB |
| Read : write ratio | 10 : 1 |
| Peak ingestion rate | ~1,000 measurements/hour (0.28 RPS) |
| Average ingestion rate | ~10,000 measurements/day (0.12 RPS) |

Current architecture handles peak load on a single replica with significant headroom before KEDA triggers scale-out.

---

## Architecture

```
Clients (Web / API consumers / Instruments)
        │ HTTPS
        ▼
┌───────────────────────────────────────────┐
│         Azure Front Door Standard         │
│     WAF — OWASP 3.2 · Bot Manager        │
│         TLS termination · Global PoP      │
└───────────────────┬───────────────────────┘
                    │
┌───────────────────▼───────────────────────┐
│         Azure Container Apps              │
│  ┌─────────────────────────────────────┐  │
│  │       Ingestion + Analytics API     │  │
│  │  FastAPI · JWT middleware · RBAC    │  │
│  │  TenantContext · Rate limiter       │  │
│  └──────────┬──────────────────────────┘  │
│             │ 202 + enqueue               │
│  ┌──────────▼──────────────────────────┐  │
│  │       Processing Worker             │  │
│  │  Service Bus consumer · Z-score    │  │
│  │  anomaly detection · Blob upload   │  │
│  └──────────┬──────────────────────────┘  │
└─────────────┼─────────────────────────────┘
              │ Private endpoints only
┌─────────────▼─────────────────────────────┐
│              Data Layer                   │
│  PostgreSQL 16 Flexible Server (VNet)     │
│    devices · calibration_records          │
│    calibration_measurements · audit_log   │
│  Blob Storage — raw-measurements          │
│  Blob Storage — reports (PDF)             │
│  Azure Service Bus — calibration queue    │
└───────────────────────────────────────────┘
              │
┌─────────────▼─────────────────────────────┐
│         Identity & Secrets                │
│  Managed Identity (no static creds)       │
│  Entra ID App Registration (JWT/JWKS)     │
│  Key Vault RBAC — secrets at runtime      │
└───────────────────────────────────────────┘
```

### Request Flow — Measurement Ingestion

```
Client  →  HTTPS POST /api/v1/measurements  (Bearer JWT or X-Dev-User in dev)
        →  WAF inspection (OWASP ruleset)
        →  Ingestion API: auth · rate-limit · Pydantic validation
        →  202 Accepted  +  { measurement_id, status: "RECEIVED" }
        →  Enqueue to Azure Service Bus  (Redis in local dev)
        →  Worker: consume message
        →  Upload raw JSON to Blob Storage (audit trail)
        →  Z-score anomaly detection  (configurable threshold, default 3.0σ)
        →  INSERT AnalysisResult  →  UPDATE status: VALIDATED | ANOMALY
        →  Analytics API: trend data, anomaly list, summary stats
        →  POST /api/v1/reports/calibration-certificate  →  PDF  →  SAS URL
```

---

## Key Design Decisions

Each decision is stated as: **Choice — Reason — Trade-off**.

**1. Async ingestion via Service Bus (202 Accepted)**
The ingestion path decouples device upload latency from anomaly detection and DB writes. Devices get an immediate acknowledgment; slow or batch processing cannot block the ingest endpoint. Trade-off: eventual consistency — the caller must poll or subscribe for final status; acceptable for calibration workflows where humans review results.

**2. Worker scales to zero with KEDA**
The processing worker is triggered by Service Bus queue depth. At zero messages it consumes no compute. Trade-off: cold-start latency (~2–5 s) on first message after idle; acceptable because measurement processing is not latency-sensitive from the device's perspective.

**3. Tenant isolation via SQL predicate, not schema-per-tenant**
Every query carries `WHERE tenant_id = $1`. The repository interface enforces `tenant_id` as a required parameter on every method — it is impossible to forget at the type level. Trade-off: a single DB schema for all tenants simplifies migrations and ops. Migration to schema-per-tenant is the path at >10k tenants if query performance degrades.

**4. Managed Identity everywhere — zero stored secrets**
All Azure-to-Azure authentication (DB, Service Bus, Blob, Key Vault) uses Managed Identity. GitHub Actions CI/CD uses OIDC federated credentials. No client secrets, no rotation burden. Trade-off: local development requires a simulated identity layer (Azurite + local MI emulation or dev bypass headers).

**5. JWT dev bypass (`X-Dev-User`) disabled in production**
`X-Dev-User` header is accepted only when `DEV_MODE=true`. In Container Apps, `DEV_MODE` is never set. This removes the friction of Entra ID setup for local development without creating a production security hole. Trade-off: adds a code path that must be explicitly tested to remain inert in prod — covered by middleware tests.

**6. RFC 7807 error format**
All error responses include `type`, `title`, `status`, `detail`, `instance`, and `request_id`. Clients can distinguish validation errors, auth failures, and server errors programmatically without parsing free-form strings. Trade-off: slightly more verbose response bodies.

**7. Z-score anomaly detection with configurable threshold**
`z = |measured − reference| / uncertainty`. Default threshold 3.0σ (~99.7% confidence). Configurable via `ANOMALY_THRESHOLD` to support lab-specific instrument types or 2σ requirements. Trade-off: simpler than adaptive or ML-based detection; sufficient for the current measurement volume and explicit audit requirements.

**8. Blob lifecycle for 10-year retention (ISO 17025)**
Raw measurement JSON and generated PDFs use a lifecycle policy: hot (0–90 days) → cool (90–365 days) → archive (1–10 years). Storage cost for 50 GB over 10 years stays under €30 total at archive tier. Trade-off: archived blobs require rehydration (hours) before download; acceptable for compliance retrieval scenarios, not for active use.

**9. Private endpoints on all data resources**
PostgreSQL, Service Bus, Blob, and Key Vault have no public endpoints. Traffic from Container Apps flows through VNet-injected subnets to private endpoints. NSGs enforce deny-by-default. Trade-off: increased IaC complexity; required for enterprise compliance and ISO 27001 alignment.

**10. OIDC federated credentials for CI/CD**
GitHub Actions authenticates to Azure via workload identity federation — no `AZURE_CLIENT_SECRET` stored in GitHub Secrets. A compromised runner cannot leak a long-lived credential. Trade-off: requires one-time Terraform setup of the federated credential; slightly more complex than service principal secrets but eliminates an entire credential-rotation class of incidents.

---

## Data Model

```sql
-- Tenant-scoped device registry
devices
  id               TEXT        PRIMARY KEY
  tenant_id        TEXT        NOT NULL
  serial_number    TEXT        NOT NULL
  device_type      TEXT        NOT NULL        -- PRESSURE | TEMPERATURE | ELECTRICAL | FLOW
  tolerance_pct    FLOAT       NOT NULL DEFAULT 0.5
  manufacturer     TEXT
  model            TEXT
  is_active        BOOLEAN     NOT NULL DEFAULT TRUE
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
  UNIQUE (serial_number, tenant_id)            -- 409 on duplicate within tenant

-- One record per calibration session
calibration_records
  id               TEXT        PRIMARY KEY
  device_id        TEXT        REFERENCES devices(id)
  tenant_id        TEXT        NOT NULL        -- denormalised for predicate pushdown
  status           TEXT        CHECK (status IN ('pass','fail','pending','invalid'))
  overall_pass     BOOLEAN
  pass_count       INT
  fail_count       INT
  operator_name    TEXT        NOT NULL
  temperature_c    FLOAT
  humidity_pct     FLOAT
  measured_at      TIMESTAMPTZ NOT NULL
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Individual measurement points within a record
calibration_measurements
  id                    TEXT    PRIMARY KEY
  record_id             TEXT    REFERENCES calibration_records(id)
  measured_value        FLOAT   NOT NULL
  reference_value       FLOAT   NOT NULL
  unit                  TEXT    NOT NULL
  uncertainty           FLOAT   NOT NULL
  deviation_pct         FLOAT               -- (measured − reference) / reference × 100
  expanded_uncertainty  FLOAT               -- 2 × uncertainty (k=2, ISO GUM)
  is_pass               BOOLEAN
  status                TEXT    CHECK (status IN ('VALIDATED','ANOMALY','PENDING'))

-- Immutable audit trail (append-only)
audit_log
  id            TEXT        PRIMARY KEY
  tenant_id     TEXT        NOT NULL
  actor_sub     TEXT        NOT NULL    -- JWT sub claim
  action        TEXT        NOT NULL    -- CREATE_DEVICE | SUBMIT_CALIBRATION | GENERATE_CERT
  resource_type TEXT
  resource_id   TEXT
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
```

**Relationship summary:** 1 device → N calibration_records → N calibration_measurements. Measurements are batch-loaded per record fetch — one extra query on `WHERE record_id = $1`, not N+1. Every write emits one `audit_log` row inside the same transaction.

---

## Anomaly Detection

Z-score relative to measurement uncertainty:

```
z = |measured_value − reference_value| / uncertainty
```

| z-score | Status | Outcome |
|---------|--------|---------|
| < threshold (default 3.0) | `VALIDATED` | Certificate eligible |
| ≥ threshold | `ANOMALY` | Flagged for operator review, blocked from certificate |

The threshold is configurable via `ANOMALY_THRESHOLD` to support instrument-specific lab requirements (e.g., 2σ for high-precision pressure standards).

---

## Scalability

| Bottleneck | Current | Scale-out path |
|------------|---------|----------------|
| API tier | Single Container App (min 1 replica) | KEDA HTTP trigger — scale to 10 replicas; stateless, no sticky sessions |
| Processing worker | KEDA Service Bus trigger, min 0 | Scale to 10 replicas on queue depth; each instance independent |
| Database reads | Single PostgreSQL instance | Add read replica; route analytics queries to replica |
| Database writes | Single writer | PgBouncer for connection pooling; partition `calibration_records` by `(tenant_id, created_at)` at >10M rows/tenant |
| Multi-tenancy | WHERE predicate | Schema-per-tenant migration path at >10k tenants if query isolation required |
| Storage throughput | Single storage account | Shard by tenant prefix; Storage has 20k IOPS limit per account |

---

## Failure Modes

| Failure | Behaviour | Recovery |
|---------|-----------|----------|
| DB unavailable at startup | Health probe `/readyz` returns 503; Container Apps stops routing | Auto-recovers when DB connection pool re-establishes; no manual intervention |
| Service Bus unavailable | Ingestion API returns 503 with `X-Retry-After`; no data loss | Queue messages survive Bus outage; worker drains on recovery |
| Worker crashes mid-processing | Service Bus redelivers after lock timeout (30 s); dead-letter after 10 attempts | Alert on dead-letter queue depth; manual reprocessing via runbook |
| Blob upload fails | Worker logs error; measurement saved to DB but raw JSON missing | Blob upload is best-effort for the raw copy; canonical record is PostgreSQL |
| Duplicate device serial | PostgreSQL UNIQUE constraint → 409 Conflict | Client deduplicates before retry; error body identifies constraint |
| Partial measurement batch | SQLAlchemy async session rolled back on exception | Client retries full batch; idempotent if measurement ID is client-generated |
| Large payload attack | FastAPI body size limit → 413 Request Entity Too Large | No heap exhaustion; WAF additionally caps at Front Door layer |
| JWT expired or tampered | 401 Unauthorized | Client refreshes token via MSAL; no server state to clear |
| OOM / unhandled exception | FastAPI exception handler returns 500 + `request_id` | Alert on 500 spike; Container Apps restarts unhealthy replicas |

---

## API Reference

Base URL: `https://<front-door-hostname>`

All endpoints except `/healthz` and `/readyz` require `Authorization: Bearer <token>` (or `X-Dev-User` in dev mode).

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/healthz` | None | Liveness — 200 if process is alive |
| GET | `/readyz` | None | Readiness — checks DB connectivity; 503 if unhealthy |

### Devices

| Method | Path | Min Role | Description |
|--------|------|----------|-------------|
| GET | `/api/v1/devices` | Viewer | List registered devices (tenant-scoped) |
| GET | `/api/v1/devices/{id}` | Viewer | Get device by ID |
| POST | `/api/v1/devices` | Admin | Register new device |
| PUT | `/api/v1/devices/{id}` | Admin | Update device metadata |

### Measurements

| Method | Path | Min Role | Description |
|--------|------|----------|-------------|
| POST | `/api/v1/measurements` | Operator | Ingest measurement — 202 Accepted, async processing |
| GET | `/api/v1/measurements` | Viewer | List with pagination |
| GET | `/api/v1/measurements/{id}` | Viewer | Get by ID including analysis result |

**POST body:**
```json
{
  "device_id": "PG-001",
  "measurement_type": "PRESSURE",
  "measured_value": 100.32,
  "reference_value": 100.00,
  "uncertainty": 0.15,
  "unit": "bar",
  "temperature_ambient": 23.1,
  "operator_id": "op-47a2b"
}
```

**202 response:**
```json
{
  "measurement_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RECEIVED",
  "queued_at": "2026-03-14T10:23:45.123Z"
}
```

### Analytics

| Method | Path | Min Role | Description |
|--------|------|----------|-------------|
| GET | `/api/v1/analytics/summary` | Viewer | Totals, validated/anomaly counts, pass rate |
| GET | `/api/v1/analytics/devices/{id}/trend` | Viewer | Device time-series pass/fail trend |
| GET | `/api/v1/analytics/anomalies` | Viewer | Anomaly list, filterable by device and time range |

### Reports

| Method | Path | Min Role | Description |
|--------|------|----------|-------------|
| POST | `/api/v1/reports/calibration-certificate` | Operator | Generate ISO 17025 PDF; returns time-limited SAS URL |

### Error Format (RFC 7807)

```json
{
  "type": "https://calibration.example.com/errors/validation-error",
  "title": "Validation Error",
  "status": 422,
  "detail": "uncertainty must be > 0",
  "instance": "/api/v1/measurements",
  "request_id": "req-abc123"
}
```

---

## Security Model

### Role Matrix

| Action | Admin | Operator | Viewer |
|--------|:-----:|:--------:|:------:|
| Register / update device | ✓ | — | — |
| Ingest measurement | ✓ | ✓ | — |
| View devices and analytics | ✓ | ✓ | ✓ |
| Generate calibration certificate | ✓ | ✓ | — |
| Manage users / app roles | ✓ | — | — |

Roles are **Entra ID App Roles** assigned per user or service principal. The JWT `roles` claim is validated on every request; no DB lookup required for authorization.

### Network Isolation

```
Internet → Front Door (TLS termination, WAF OWASP 3.2)
         → Container Apps (VNet-injected subnets)
         → Private endpoints (PostgreSQL, Service Bus, Blob, Key Vault)
         → No public internet egress from data resources
```

NSGs enforce deny-by-default on all subnets. All traffic between compute and data traverses the Azure backbone only.

### Credential Policy

- Zero secrets in source code or environment variables at runtime
- All secrets fetched from Key Vault via Managed Identity at startup
- GitHub Actions uses OIDC federated credentials — no `AZURE_CLIENT_SECRET` in repository secrets
- Managed Identity scoped to minimum required RBAC roles per resource

### ISO 17025 Compliance Controls

| Control | Implementation |
|---------|----------------|
| 10-year retention | Blob lifecycle: hot (0–90d) → cool (90–365d) → archive (1–10y) |
| Audit trail | `audit_log` table — append-only, one row per API write, inside transaction |
| EU data residency | All resources: North Europe primary, West Europe DR only |
| RTO / RPO | Zone-redundant PostgreSQL (RPO ~0), geo-redundant Blob (RTO < 4h, RPO < 1h) |

---

## Deployment

### 1. Provision Infrastructure

```bash
az login

# Plan and apply (dev)
make tf-plan ENV=dev
make tf-apply ENV=dev
```

Terraform provisions 9 modules in dependency order:

| # | Module | Key Resources |
|---|--------|---------------|
| 1 | networking | VNet, subnets, NSGs, 4 private DNS zones |
| 2 | identity | Managed Identity, App Registration, OIDC federated credentials |
| 3 | keyvault | Key Vault (RBAC mode, purge protection) |
| 4 | database | PostgreSQL 16 Flexible Server, private endpoint |
| 5 | messaging | Service Bus namespace + queue, RBAC assignments |
| 6 | storage | Blob Storage, containers, lifecycle policy |
| 7 | monitoring | Log Analytics, App Insights, metric alerts |
| 8 | compute | Container Apps Environment + 3 apps + KEDA rules |
| 9 | frontdoor | Front Door Standard, WAF policy (OWASP 3.2) |

### 2. CI/CD Pipeline

```
push to main  →  CI: lint (ruff + mypy) → test (pytest -race) → docker build → tf validate
              ↓ success
              →  CD Infra: tf plan → manual approval → tf apply
              →  CD Deploy: OIDC login → ACR push → az containerapp update → smoke test /healthz
              ↓ failure
              →  auto-rollback to previous ACR revision
```

All Azure authentication in GitHub Actions uses **OIDC federated credentials** — no client secrets stored anywhere.

### 3. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` |
| `AZURE_TENANT_ID` | Yes | Entra ID tenant for JWT validation |
| `AZURE_CLIENT_ID` | Yes | App Registration client ID |
| `KEY_VAULT_URL` | Yes | Key Vault URI |
| `SERVICEBUS_NAMESPACE` | Yes | Service Bus FQDN |
| `STORAGE_ACCOUNT_NAME` | Prod | Azure Storage account name |
| `REDIS_URL` | Dev | `redis://localhost:6379` (replaces Service Bus locally) |
| `DEV_MODE` | Dev | `true` enables `X-Dev-User` bypass header |
| `ANOMALY_THRESHOLD` | No | Z-score threshold, default `3.0` |
| `RATE_LIMIT_RPS` | No | Per-user per-second limit, default `10` |

---

## Running Locally

```bash
git clone https://github.com/Aliipou/cloud-calibration-platform.git
cd cloud-calibration-platform

cp .env.example .env

# Start PostgreSQL 16 + Redis 7 + API + Worker
make dev

# Apply database migrations
make migrate

# Verify
curl http://localhost:8000/healthz
# {"status":"ok","database":"connected","version":"1.0.0"}
```

Dev auth — no Entra ID setup required locally:

```bash
curl -H 'X-Dev-User: {"sub":"dev-user","roles":["Admin"],"email":"dev@local"}' \
     -H 'Content-Type: application/json' \
     -d '{
       "device_id": "PG-001",
       "measurement_type": "PRESSURE",
       "measured_value": 100.32,
       "reference_value": 100.00,
       "uncertainty": 0.15,
       "unit": "bar",
       "operator_id": "op-001"
     }' \
     http://localhost:8000/api/v1/measurements
# HTTP 202 Accepted
```

---

## Testing

```bash
make test
# pytest --asyncio-mode=auto -race --cov --cov-fail-under=80
```

Test strategy:

- **Anomaly detector** — pure unit tests, no I/O; table-driven cases covering 2σ/3σ boundaries, zero uncertainty, negative deviation
- **Handlers** — async httptest with in-memory repository fakes; covers CRUD, RBAC enforcement, tenant isolation (cross-tenant read attempt → 404), store error propagation
- **Middleware** — JWT bypass active in dev mode, rejected in prod mode; rate limiter token bucket behaviour; body size limit enforcement
- **Worker** — mocked Service Bus client; verifies correct status transitions (PENDING → VALIDATED, PENDING → ANOMALY) and Blob upload call

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Language | Python 3.12 | Async-native ecosystem, excellent Azure SDK support |
| HTTP | FastAPI 0.111 | Async-first, Pydantic v2 validation, OpenAPI auto-generated |
| ORM | SQLAlchemy 2.0 async + asyncpg | True async driver, typed mapped columns, no hidden N+1 |
| Database | Azure PostgreSQL 16 Flexible Server | Managed, AAD-only auth, zone-redundant, private endpoint |
| Queue | Azure Service Bus | At-least-once delivery, dead-letter queue, AMQP, RBAC |
| Storage | Azure Blob Storage | Lifecycle policy, private endpoint, geo-redundant in prod |
| Secrets | Azure Key Vault RBAC | MI-only access, no legacy access policies, purge protection |
| Auth | Azure Entra ID JWT + JWKS | RS256, role claims, no shared secrets, JWKS auto-rotation |
| IaC | Terraform 1.7, azurerm ~> 3.90 | Declarative, OIDC backend, plan artefacts for audit |
| Runtime | Azure Container Apps + KEDA | Serverless, scale-to-zero worker, no cluster management overhead |
| Edge | Azure Front Door Standard + WAF | Global PoP, OWASP 3.2, bot manager, Prevention mode in prod |
| CI/CD | GitHub Actions + OIDC | Zero stored credentials, federated identity |
| Observability | structlog JSON + OpenTelemetry + App Insights | Correlation IDs, distributed tracing, structured log queries |
| Security scanning | Trivy, CodeQL, Checkov, pip-audit | SARIF uploads to GitHub Security tab on every push |

---

## Cost Estimates

### Development (~€31/month)

| Resource | SKU | Approx. Cost |
|----------|-----|-------------|
| PostgreSQL Flexible | Standard_B1ms | ~€15 |
| Service Bus | Basic | <€1 |
| Container Apps | Consumption, min 1 replica | ~€8 |
| Blob Storage | LRS, ~10 GB | <€1 |
| Front Door Standard | — | ~€5 |
| Log Analytics | ~1 GB/day | ~€3 |

### Production (~€307/month)

| Resource | SKU | Approx. Cost |
|----------|-----|-------------|
| PostgreSQL Flexible | Standard_D2s_v3, zone-redundant | ~€120 |
| Service Bus | Standard | ~€10 |
| Container Apps | Consumption, min 2 replicas | ~€80 |
| Blob Storage | GRS, ~500 GB + lifecycle | ~€25 |
| Front Door + WAF | Standard | ~€40 |
| Key Vault | Standard | ~€2 |
| Log Analytics | ~10 GB/day | ~€30 |

---

## Architecture Decision Records

| # | Decision | Status |
|---|----------|--------|
| [ADR-001](docs/adr/001-async-python.md) | Python FastAPI over .NET/Go for API tier | Accepted |
| [ADR-002](docs/adr/002-container-apps.md) | Azure Container Apps over AKS | Accepted |
| [ADR-003](docs/adr/003-service-bus.md) | Service Bus over Event Hubs for measurement queue | Accepted |
| [ADR-004](docs/adr/004-oidc-only.md) | OIDC federated credentials — zero stored secrets | Accepted |

---

## Repository Structure

```
cloud-calibration-platform/
├── api/                        # FastAPI application (ingestion + analytics)
│   ├── src/
│   │   ├── core/               # Auth, middleware, rate limiter, logging
│   │   ├── db/                 # Async engine, repository pattern
│   │   ├── models/             # SQLAlchemy models, Pydantic schemas, enums
│   │   ├── routes/             # HTTP handlers
│   │   ├── services/           # Business logic (ingestion, analytics, reports)
│   │   └── main.py
│   ├── alembic/                # Database migrations
│   ├── tests/                  # pytest-asyncio suite (>80% coverage)
│   ├── Dockerfile
│   └── pyproject.toml
├── worker/                     # Service Bus consumer + anomaly detector
│   ├── src/
│   │   ├── anomaly_detector.py
│   │   ├── processor.py
│   │   ├── storage.py
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── terraform/                  # Azure IaC — 9 modules
│   ├── modules/{networking,identity,keyvault,database,messaging,storage,monitoring,compute,frontdoor}/
│   ├── environments/{dev,prod}.tfvars
│   └── main.tf
├── .github/workflows/
│   ├── ci.yml                  # Lint + test + docker build + tf validate
│   ├── cd-infra.yml            # Terraform plan → approval → apply
│   ├── cd-deploy.yml           # OIDC → ACR push → containerapp update → smoke test
│   └── security-scan.yml       # Trivy + pip-audit + Checkov + CodeQL
├── docs/
│   ├── adr/                    # Architecture Decision Records 001–004
│   ├── architecture.md         # C4 diagrams
│   └── runbook.md              # On-call procedures
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned phases:

- **Phase 2** — PKI-signed calibration certificates (X.509, ETSI EN 319 102)
- **Phase 3** — Slack / Teams alert integration for anomaly notifications
- **Phase 4** — TimescaleDB hypertables for high-frequency time-series measurement storage
- **Phase 5** — AKS Helm chart deployment for customers requiring dedicated cluster isolation

---

## License

MIT © 2026 Ali Pourrahim
