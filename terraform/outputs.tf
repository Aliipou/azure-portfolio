output "front_door_hostname" {
  value       = module.frontdoor.endpoint_hostname
  description = "Azure Front Door endpoint — use this as your API base URL"
}

output "ingestion_api_fqdn" {
  value       = module.compute.ingestion_api_fqdn
  description = "Ingestion API Container App FQDN"
}

output "key_vault_uri" {
  value       = module.keyvault.key_vault_uri
  description = "Key Vault URI"
}

output "log_analytics_workspace_id" {
  value       = module.monitoring.log_analytics_workspace_id
  description = "Log Analytics workspace resource ID"
}

output "managed_identity_client_id" {
  value       = module.identity.managed_identity_client_id
  description = "App managed identity client ID (set as AZURE_CLIENT_ID in Container Apps)"
}

output "api_client_id" {
  value       = module.identity.api_client_id
  description = "Azure AD App Registration client ID (set as AZURE_CLIENT_ID for auth)"
}

output "app_insights_connection_string" {
  value       = module.monitoring.app_insights_connection_string
  sensitive   = true
  description = "Application Insights connection string"
}
