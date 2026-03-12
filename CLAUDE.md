# cloud-calibration-platform — Claude Code Context

## What This Is
A production-grade cloud platform for calibration measurement data from industrial instruments.
Devices → Ingestion API → Service Bus → Processing Worker → PostgreSQL + Blob Storage → Analytics API

## Tech Stack
| Layer | Technology |
|-------|-----------|
| API | Python 3.12, FastAPI, SQLAlchemy 2.0 async |
| Worker | Python 3.12, azure-servicebus SDK |
| Database | Azure PostgreSQL Flexible Server |
| Queue | Azure Service Bus |
| Storage | Azure Blob Storage |
| Infrastructure | Terraform >= 1.7 (azurerm ~> 3.90) |
| Runtime | Azure Container Apps |
| Edge | Azure Front Door + WAF |
| Auth | Azure Entra ID (JWT, RBAC) |
| CI/CD | GitHub Actions (OIDC only) |

## Project Structure
```
api/src/         — FastAPI application
  routes/        — HTTP handlers (ingestion, devices, analytics, reports, health)
  core/          — Auth, rate limiter, middleware, logging
  models/        — SQLAlchemy models, Pydantic schemas, enums
  services/      — Business logic (ingestion, analytics, report, keyvault)
  db/            — Async engine, repository pattern
worker/src/      — Service Bus consumer, processor, anomaly detector, storage
terraform/       — All Azure infrastructure as Terraform modules
.github/workflows/ — CI, CD infra, CD deploy, security scan
docs/            — Architecture, security model, ADRs, runbook
```

## Naming Convention (Azure CAF)
- Resource Group: `rg-<project>-<component>-<env>`
- Container App: `ca-<project>-<service>-<env>`
- Storage: `st<project><env>001` (no hyphens)
- Key Vault: `kv-<project>-<env>-001`

## Running Locally
```bash
make dev          # docker-compose up
make migrate      # alembic upgrade head
make test         # pytest with coverage
make lint         # ruff + mypy
make tf-plan      # terraform plan (dev env)
```

## Auth (DEV MODE)
Set header `X-Dev-User: {"sub":"dev-user","roles":["Admin"],"email":"dev@local"}`
to bypass JWT validation in development.

## OIDC Only
GitHub Actions uses federated credentials — no client secrets stored anywhere.
