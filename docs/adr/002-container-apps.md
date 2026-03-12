# ADR-002: Azure Container Apps over AKS

**Date:** 2024-03-01
**Status:** Accepted

## Context

The platform needs to run three containerized services (ingestion-api, processing-worker, analytics-api) with:
- Auto-scaling based on HTTP load and Service Bus queue depth
- Managed TLS and ingress
- Zero-downtime deployments
- Reasonable operational overhead for a platform maintained by a small team

Candidates: Azure Kubernetes Service (AKS), Azure Container Apps (ACA), Azure App Service (containers).

## Decision

Use **Azure Container Apps** with the Consumption + Dedicated plan, using KEDA scale rules.

## Rationale

| Criterion | ACA | AKS | App Service |
|-----------|-----|-----|-------------|
| Operational overhead | Very low (no cluster) | High (node pools, upgrades) | Low |
| KEDA scaling | Built-in | Requires KEDA add-on | Limited |
| Scale to zero | Yes (worker) | Yes (with KEDA) | No |
| Service Bus trigger | Built-in rule | Custom ScaledObject | No |
| Managed identity | First-class | Workload Identity (complex) | First-class |
| Cost (dev) | ~€8/mo | ~€150/mo (min cluster) | ~€15/mo |
| Private networking | VNet injection | Azure CNI | VNet integration |

For a calibration data platform with predictable load patterns (business hours, batch uploads), ACA's scale-to-zero for the worker provides significant cost savings. The platform does not need advanced Kubernetes features (custom operators, DaemonSets, complex scheduling).

## Consequences

- **Positive**: No cluster to manage, KEDA Service Bus scaling built-in, worker scales to zero off-hours, 60% cost reduction vs AKS for this workload
- **Negative**: Less flexibility than AKS (no sidecar patterns, no DaemonSets), revision traffic splitting is less granular than Kubernetes rolling updates
- **Mitigation**: ACA revision management provides sufficient blue/green capability; rollback is handled in the CD workflow via `az containerapp update` to a previous image tag
