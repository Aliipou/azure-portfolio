output "ingestion_api_fqdn"  { value = azurerm_container_app.ingestion_api.ingress[0].fqdn }
output "analytics_api_fqdn" { value = try(azurerm_container_app.analytics_api.ingress[0].fqdn, "") }
output "environment_id"      { value = azurerm_container_app_environment.main.id }
