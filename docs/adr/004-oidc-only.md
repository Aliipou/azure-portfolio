# ADR-004: OIDC federated credentials, zero stored secrets in CI/CD

**Date:** 2024-03-01
**Status:** Accepted

## Context

The CI/CD pipeline needs to authenticate to Azure to:
- Push container images to ACR
- Run `az containerapp update` for deployments
- Execute Terraform (read/write state, provision resources)

Traditional approach: store client secret or service principal credentials in GitHub Secrets. These have a fixed lifetime, can be leaked, and require rotation procedures.

## Decision

Use **OIDC federated credentials** (Workload Identity Federation) for all CI/CD Azure authentication. No client secrets are stored anywhere.

## Implementation

```
GitHub Actions runner → requests OIDC JWT from GitHub token endpoint
                     → exchanges JWT for Azure AD access token (no secret needed)
                     → uses access token for Azure CLI / Terraform / ACR
```

Terraform module creates federated credentials scoped to:
- `repo:Aliipou/cloud-calibration-platform:ref:refs/heads/main` (main branch pushes)
- `repo:Aliipou/cloud-calibration-platform:environment:production` (production environment)

Terraform uses `ARM_USE_OIDC=true` — no `ARM_CLIENT_SECRET`.

## Rationale

| Criterion | OIDC Federated | Client Secret | Managed Identity (self-hosted) |
|-----------|---------------|---------------|-------------------------------|
| Secret rotation needed | No | Every 90 days | No |
| Leaked secret risk | None | High | None |
| Scope limiting | Exact branch/env | Any workflow | Runner scope |
| Setup complexity | Medium | Low | High |
| Audit trail | GitHub Actions JWT claims | Service Principal | Azure MI logs |

## Consequences

- **Positive**: No secrets to rotate, no risk of secret leak in logs or PRs, audit log shows exact GitHub workflow that authenticated
- **Negative**: More complex Terraform setup (federated credential resources), runners must be GitHub-hosted (or self-hosted with OIDC support)
- **Mitigation**: The `identity` Terraform module encapsulates all federated credential setup; the pattern is well-documented and reusable across projects
