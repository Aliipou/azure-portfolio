data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "keyvault" {
  name     = "rg-${var.project}-keyvault-${var.environment}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_key_vault" "main" {
  name                        = "kv-${var.project}-${var.environment}-001"
  location                    = var.location
  resource_group_name         = azurerm_resource_group.keyvault.name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  enable_rbac_authorization   = true
  purge_protection_enabled    = true
  soft_delete_retention_days  = 90
  tags                        = var.tags

  network_acls {
    bypass         = "AzureServices"
    default_action = "Deny"
  }
}

resource "azurerm_private_endpoint" "keyvault" {
  name                = "pe-kv-${var.project}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.keyvault.name
  subnet_id           = var.data_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-kv"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "dns-group-kv"
    private_dns_zone_ids = [var.keyvault_private_dns_zone_id]
  }
}

# Grant managed identity access to read secrets
resource "azurerm_role_assignment" "app_kv_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.managed_identity_principal_id
}

# Diagnostic settings
resource "azurerm_monitor_diagnostic_setting" "kv" {
  name                       = "diag-kv"
  target_resource_id         = azurerm_key_vault.main.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log { category = "AuditEvent" }
  metric { category = "AllMetrics" }
}
