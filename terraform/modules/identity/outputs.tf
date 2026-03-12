output "managed_identity_id"           { value = azurerm_user_assigned_identity.app.id }
output "managed_identity_principal_id" { value = azurerm_user_assigned_identity.app.principal_id }
output "managed_identity_client_id"    { value = azurerm_user_assigned_identity.app.client_id }
output "api_client_id"                 { value = azuread_application.api.client_id }
output "tenant_id"                     { value = data.azuread_client_config.current.tenant_id }
