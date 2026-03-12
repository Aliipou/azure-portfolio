locals {
  tags = {
    environment  = var.environment
    project      = var.project
    owner        = var.owner
    cost-center  = "calibration-platform"
    managed-by   = "terraform"
    repository   = "cloud-calibration-platform"
  }
}

data "azurerm_client_config" "current" {}

# ── 1. Monitoring (no deps) ───────────────────────────────────────────────────

module "monitoring" {
  source              = "./modules/monitoring"
  project             = var.project
  environment         = var.environment
  location            = var.location
  tags                = local.tags
  log_retention_days  = var.log_retention_days
  alert_email         = var.alert_email
}

# ── 2. Networking (no deps) ───────────────────────────────────────────────────

module "networking" {
  source      = "./modules/networking"
  project     = var.project
  environment = var.environment
  location    = var.location
  tags        = local.tags
}

# ── 3. Identity (no deps) ─────────────────────────────────────────────────────

module "identity" {
  source      = "./modules/identity"
  project     = var.project
  environment = var.environment
  location    = var.location
  tags        = local.tags
  github_org  = var.github_org
  github_repo = var.github_repo
}

# ── 4. Key Vault (needs: networking, identity, monitoring) ────────────────────

module "keyvault" {
  source                        = "./modules/keyvault"
  project                       = var.project
  environment                   = var.environment
  location                      = var.location
  tags                          = local.tags
  data_subnet_id                = module.networking.data_subnet_id
  keyvault_private_dns_zone_id  = module.networking.private_dns_zone_ids["privatelink.vaultcore.azure.net"]
  managed_identity_principal_id = module.identity.managed_identity_principal_id
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
}

# ── 5. Database (needs: networking, identity) ─────────────────────────────────

module "database" {
  source                        = "./modules/database"
  project                       = var.project
  environment                   = var.environment
  location                      = var.location
  tags                          = local.tags
  postgres_sku                  = var.postgres_sku
  data_subnet_id                = module.networking.data_subnet_id
  postgres_private_dns_zone_id  = module.networking.private_dns_zone_ids["privatelink.postgres.database.azure.com"]
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  managed_identity_principal_id = module.identity.managed_identity_principal_id
}

# ── 6. Messaging (needs: networking, identity) ────────────────────────────────

module "messaging" {
  source                          = "./modules/messaging"
  project                         = var.project
  environment                     = var.environment
  location                        = var.location
  tags                            = local.tags
  servicebus_sku                  = var.servicebus_sku
  data_subnet_id                  = module.networking.data_subnet_id
  servicebus_private_dns_zone_id  = module.networking.private_dns_zone_ids["privatelink.servicebus.windows.net"]
  managed_identity_principal_id   = module.identity.managed_identity_principal_id
}

# ── 7. Storage (needs: networking, identity) ──────────────────────────────────

module "storage" {
  source                        = "./modules/storage"
  project                       = var.project
  environment                   = var.environment
  location                      = var.location
  tags                          = local.tags
  data_subnet_id                = module.networking.data_subnet_id
  blob_private_dns_zone_id      = module.networking.private_dns_zone_ids["privatelink.blob.core.windows.net"]
  managed_identity_principal_id = module.identity.managed_identity_principal_id
}

# ── 8. Compute (needs: all above) ─────────────────────────────────────────────

module "compute" {
  source                        = "./modules/compute"
  project                       = var.project
  environment                   = var.environment
  location                      = var.location
  tags                          = local.tags
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
  app_subnet_id                 = module.networking.app_subnet_id
  managed_identity_id           = module.identity.managed_identity_id
  managed_identity_client_id    = module.identity.managed_identity_client_id
  key_vault_uri                 = module.keyvault.key_vault_uri
  servicebus_queue_name         = module.messaging.queue_name
  servicebus_connection_string  = "Endpoint=sb://${module.messaging.namespace_name}.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=placeholder"
  api_min_replicas              = var.api_min_replicas
  api_max_replicas              = var.api_max_replicas
  worker_min_replicas           = var.worker_min_replicas
  worker_max_replicas           = var.worker_max_replicas
}

# ── 9. Front Door (needs: compute) ───────────────────────────────────────────

module "frontdoor" {
  source              = "./modules/frontdoor"
  project             = var.project
  environment         = var.environment
  location            = var.location
  tags                = local.tags
  ingestion_api_fqdn  = module.compute.ingestion_api_fqdn
  analytics_api_fqdn  = module.compute.analytics_api_fqdn
}
