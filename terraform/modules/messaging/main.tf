resource "azurerm_resource_group" "messaging" {
  name     = "rg-${var.project}-messaging-${var.environment}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_servicebus_namespace" "main" {
  name                = "sb-${var.project}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.messaging.name
  sku                 = var.servicebus_sku
  tags                = var.tags

  local_auth_enabled = false  # Managed Identity only
}

resource "azurerm_servicebus_queue" "measurements" {
  name         = "calibration-measurements"
  namespace_id = azurerm_servicebus_namespace.main.id

  enable_partitioning                  = var.servicebus_sku != "Basic"
  max_delivery_count                   = 3
  dead_lettering_on_message_expiration = true
  message_time_to_live                 = "P7D"
  lock_duration                        = "PT1M"
}

resource "azurerm_private_endpoint" "servicebus" {
  name                = "pe-sb-${var.project}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.messaging.name
  subnet_id           = var.data_subnet_id
  tags                = var.tags

  private_service_connection {
    name                           = "psc-sb"
    private_connection_resource_id = azurerm_servicebus_namespace.main.id
    subresource_names              = ["namespace"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "dns-group-sb"
    private_dns_zone_ids = [var.servicebus_private_dns_zone_id]
  }
}

# RBAC for managed identity
resource "azurerm_role_assignment" "app_sb_sender" {
  scope                = azurerm_servicebus_namespace.main.id
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_role_assignment" "app_sb_receiver" {
  scope                = azurerm_servicebus_namespace.main.id
  role_definition_name = "Azure Service Bus Data Receiver"
  principal_id         = var.managed_identity_principal_id
}
