# ADR-003: Azure Service Bus over Event Hubs for measurement queue

**Date:** 2024-03-01
**Status:** Accepted

## Context

The ingestion API must decouple from the processing worker. Measurements arrive in bursts (end of calibration shift) and processing can fall behind temporarily. The queue must guarantee at-least-once delivery with dead-lettering for failed messages.

Candidates: Azure Service Bus (queues), Azure Event Hubs (partitioned log), Azure Storage Queue.

## Decision

Use **Azure Service Bus** with a single `calibration-measurements` queue.

## Rationale

| Criterion | Service Bus | Event Hubs | Storage Queue |
|-----------|-------------|------------|---------------|
| At-least-once delivery | Yes | Yes | Yes |
| Dead-letter queue | Yes (built-in) | No (manual) | No |
| Message ordering (per session) | Yes (sessions) | Yes (per partition) | No |
| Max message size | 256KB (Basic), 1MB (Standard) | 1MB | 64KB |
| RBAC Sender/Receiver | Yes | Yes | Yes |
| Retention | 14 days | 1–7 days (configurable) | 7 days |
| Cost (10k msg/day) | ~€0.05/mo (Basic) | ~€10/mo minimum | ~€0.01/mo |

The critical requirement is **dead-lettering**: failed measurements (e.g., database unreachable during processing) must not be lost. Service Bus dead-letter queues allow manual inspection and reprocessing. Event Hubs does not have a built-in dead-letter concept.

Storage Queue was eliminated due to the 64KB message limit (a measurement with full metadata can approach this limit) and lack of dead-lettering.

## Consequences

- **Positive**: Dead-letter queue prevents data loss during processing failures; 3-retry exponential backoff in the worker exhausts before dead-lettering; RBAC-only auth (no connection strings)
- **Negative**: Service Bus costs more than Storage Queue; requires Standard SKU for prod to get 1MB messages and topics
- **Mitigation**: Dev environment uses Redis BLPOP (simpler, zero cost) with the same message format; `USE_REDIS_QUEUE=true` flag swaps the transport layer without changing processor logic
