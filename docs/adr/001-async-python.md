# ADR-001: Python FastAPI over .NET/Go for the API layer

**Date:** 2024-03-01
**Status:** Accepted

## Context

The calibration platform needs an HTTP API that:
- Handles concurrent measurement ingestion from many devices simultaneously
- Integrates natively with Azure SDKs (Service Bus, Blob, Key Vault)
- Can be validated with Pydantic against strict ISO 17025 measurement schemas
- Has first-class async support for PostgreSQL (asyncpg) and Redis

Candidates considered: .NET 8 (Minimal API), Go (Gin/Echo), Python (FastAPI), Python (Django REST Framework).

## Decision

Use **Python 3.12 + FastAPI** with SQLAlchemy 2.0 async + asyncpg.

## Rationale

| Criterion | FastAPI | .NET 8 | Go |
|-----------|---------|--------|-----|
| Azure SDK maturity | Excellent (azure-sdk-for-python) | Excellent | Good |
| Async PostgreSQL | asyncpg (native) | Npgsql | pgx |
| Schema validation | Pydantic v2 (5-50× faster than v1) | FluentValidation | manual |
| OpenAPI generation | Built-in, zero config | Swashbuckle | swaggo |
| Type safety | mypy strict | Native | Native |
| Team familiarity | High | Medium | Low |
| Cold start (Container Apps) | ~200ms | ~400ms | ~50ms |

FastAPI's automatic OpenAPI generation is critical: calibration labs integrate via the published schema, and keeping it accurate without manual maintenance reduces errors.

## Consequences

- **Positive**: OpenAPI spec auto-generated, Pydantic validation covers all measurement field constraints (uncertainty > 0, valid device types), async-native means no thread pool overhead
- **Negative**: Python's GIL means CPU-bound work (anomaly detection) must run in the worker, not inline; cold starts slightly slower than Go
- **Mitigation**: Worker handles all CPU-bound processing; Container Apps keeps min replicas = 1 in prod (no cold start penalty)
