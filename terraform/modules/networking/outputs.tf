output "vnet_id"          { value = azurerm_virtual_network.main.id }
output "app_subnet_id"    { value = azurerm_subnet.app.id }
output "data_subnet_id"   { value = azurerm_subnet.data.id }
output "resource_group_name" { value = azurerm_resource_group.networking.name }

output "private_dns_zone_ids" {
  value = { for k, v in azurerm_private_dns_zone.zones : k => v.id }
}
