resource "azurerm_resource_group" "database" {
  name     = "rg-${var.project}-database-${var.environment}"
  location = var.location
  tags     = var.tags
}

resource "random_password" "pg_admin" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "pg-${var.project}-${var.environment}"
  resource_group_name           = azurerm_resource_group.database.name
  location                      = var.location
  version                       = "16"
  sku_name                      = var.postgres_sku
  storage_mb                    = 32768
  backup_retention_days         = 35
  geo_redundant_backup_enabled  = var.environment == "prod"
  public_network_access_enabled = false
  tags                          = var.tags

  # AAD-only authentication
  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = false
    tenant_id                     = var.tenant_id
  }

  delegated_subnet_id    = var.data_subnet_id
  private_dns_zone_id    = var.postgres_private_dns_zone_id

  maintenance_window {
    day_of_week  = 0
    start_hour   = 3
    start_minute = 0
  }
}

resource "azurerm_postgresql_flexible_server_database" "calibration" {
  name      = "calibration_db"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "UTF8"
}

resource "azurerm_postgresql_flexible_server_active_directory_administrator" "app" {
  server_name         = azurerm_postgresql_flexible_server.main.name
  resource_group_name = azurerm_resource_group.database.name
  tenant_id           = var.tenant_id
  object_id           = var.managed_identity_principal_id
  principal_name      = "mi-${var.project}-${var.environment}"
  principal_type      = "ServicePrincipal"
}
