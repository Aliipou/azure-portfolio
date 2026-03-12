output "server_id"   { value = azurerm_postgresql_flexible_server.main.id }
output "server_fqdn" { value = azurerm_postgresql_flexible_server.main.fqdn }
output "database_name" { value = azurerm_postgresql_flexible_server_database.calibration.name }
