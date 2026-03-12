output "namespace_id"   { value = azurerm_servicebus_namespace.main.id }
output "queue_name"     { value = azurerm_servicebus_queue.measurements.name }
output "namespace_name" { value = azurerm_servicebus_namespace.main.name }
