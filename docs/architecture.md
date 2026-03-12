# Architecture

## C4 Model — System Context

```mermaid
C4Context
    title Cloud Calibration Platform — System Context

    Person(operator, "Calibration Operator", "Lab technician uploading measurement results")
    Person(viewer, "Calibration Viewer", "Quality manager reviewing analytics and certificates")
    Person(admin, "Platform Admin", "Manages device registry and user roles")

    System(platform, "Cloud Calibration Platform", "Ingests, processes, and stores calibration measurement data from industrial instruments")

    System_Ext(devices, "Field Devices", "Pressure gauges, thermometers, electrical meters submitting measurements via HTTPS")
    System_Ext(entra, "Azure Entra ID", "Identity provider — issues JWT tokens with role claims")
    System_Ext(metrology, "Metrology Lab Systems", "Consumes calibration certificates (PDF) for accreditation")

    Rel(devices, platform, "POST /api/v1/measurements", "HTTPS/JSON")
    Rel(operator, platform, "Ingest measurements, generate certificates", "HTTPS")
    Rel(viewer, platform, "View analytics, download reports", "HTTPS")
    Rel(admin, platform, "Manage devices and users", "HTTPS")
    Rel(platform, entra, "Validate JWT tokens", "HTTPS/JWKS")
    Rel(platform, metrology, "Export PDF certificates", "SFTP/HTTPS")
```

## C4 Model — Container Diagram

```mermaid
C4Container
    title Cloud Calibration Platform — Container Diagram

    Person(operator, "Operator")

    System_Boundary(platform, "Cloud Calibration Platform") {
        Container(fd, "Azure Front Door + WAF", "Azure PaaS", "Global load balancing, TLS termination, OWASP 3.2 WAF")
        Container(api, "Ingestion API", "Python 3.12, FastAPI", "Accepts measurements, authenticates JWT, rate-limits, enqueues")
        Container(worker, "Processing Worker", "Python 3.12", "Consumes queue, detects anomalies, stores results")
        Container(analytics, "Analytics API", "Python 3.12, FastAPI", "Serves trend data, anomaly list, generates PDF certs")
        ContainerDb(pg, "PostgreSQL 16", "Azure PostgreSQL Flexible Server", "Devices, Measurements, AnalysisResults, AuditLog")
        Container(sb, "Service Bus Queue", "Azure Service Bus", "calibration-measurements — at-least-once delivery")
        ContainerDb(blob, "Blob Storage", "Azure Blob Storage", "raw-measurements + reports containers")
        Container(kv, "Key Vault", "Azure Key Vault", "Secrets, certificates — RBAC mode")
    }

    Rel(operator, fd, "HTTPS")
    Rel(fd, api, "HTTPS — ingestion origin group")
    Rel(fd, analytics, "HTTPS — analytics origin group")
    Rel(api, sb, "Enqueue measurement", "AMQP, MI auth")
    Rel(api, pg, "Read/write devices + measurements", "asyncpg TLS")
    Rel(worker, sb, "Consume + dead-letter", "AMQP, MI auth")
    Rel(worker, blob, "Upload raw JSON", "HTTPS, MI auth")
    Rel(worker, pg, "Write AnalysisResult", "asyncpg TLS")
    Rel(analytics, pg, "Read analytics", "asyncpg TLS")
    Rel(analytics, blob, "Upload PDF reports", "HTTPS, MI auth")
    Rel(api, kv, "Fetch secrets", "HTTPS, MI auth")
```

## Networking

```
VNet: 10.0.0.0/16
├── app-subnet: 10.0.1.0/24   (Container Apps delegation)
└── data-subnet: 10.0.2.0/24  (Private endpoints)

Private DNS Zones (linked to VNet):
├── privatelink.postgres.database.azure.com
├── privatelink.servicebus.windows.net
├── privatelink.blob.core.windows.net
└── privatelink.vaultcore.azure.net

NSGs:
├── app-nsg: allow HTTPS inbound from Front Door, deny all else
└── data-nsg: allow 5432/5671/443 from app-subnet only
```

## Sequence: Measurement Ingestion

```mermaid
sequenceDiagram
    participant D as Device
    participant FD as Front Door WAF
    participant API as Ingestion API
    participant SB as Service Bus
    participant W as Worker
    participant PG as PostgreSQL
    participant BS as Blob Storage

    D->>FD: POST /api/v1/measurements (Bearer JWT)
    FD->>FD: WAF inspection (OWASP rules)
    FD->>API: Forward request
    API->>API: Validate JWT (JWKS, 24h cache)
    API->>API: Rate limit check (token bucket)
    API->>API: Pydantic validation
    API->>PG: INSERT CalibrationMeasurement (status=RECEIVED)
    API->>PG: INSERT AuditLog
    API->>SB: Send message (measurement_id)
    API-->>D: 202 Accepted {measurement_id, status: "RECEIVED"}

    SB->>W: Deliver message
    W->>PG: SELECT measurement by ID
    W->>BS: Upload raw JSON {device_id}/{year}/{month}/{id}.json
    W->>W: Z-score anomaly detection
    W->>PG: INSERT AnalysisResult
    W->>PG: UPDATE measurement status=VALIDATED|ANOMALY
    W->>SB: Complete message (ack)
```

## Scaling Architecture

```
KEDA Scale Rules:
┌─────────────────────────────────────────────┐
│ Ingestion API                               │
│   trigger: HTTP concurrent requests         │
│   threshold: 10 concurrent / replica        │
│   min: 1  max: 10 (prod)                   │
├─────────────────────────────────────────────┤
│ Processing Worker                           │
│   trigger: Service Bus queue depth          │
│   threshold: 5 messages / replica           │
│   min: 0  max: 10 (prod) ← scales to zero  │
├─────────────────────────────────────────────┤
│ Analytics API                               │
│   trigger: HTTP concurrent requests         │
│   threshold: 10 concurrent / replica        │
│   min: 1  max: 5 (prod)                    │
└─────────────────────────────────────────────┘
```
