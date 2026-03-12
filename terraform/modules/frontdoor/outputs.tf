output "endpoint_hostname" { value = azurerm_cdn_frontdoor_endpoint.main.host_name }
output "waf_policy_id"     { value = azurerm_cdn_frontdoor_firewall_policy.main.id }
