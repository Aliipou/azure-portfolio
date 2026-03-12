resource "azurerm_resource_group" "frontdoor" {
  name     = "rg-${var.project}-frontdoor-${var.environment}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_cdn_frontdoor_profile" "main" {
  name                = "afd-${var.project}-${var.environment}"
  resource_group_name = azurerm_resource_group.frontdoor.name
  sku_name            = "Standard_AzureFrontDoor"
  tags                = var.tags
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  name                     = "ep-${var.project}-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  tags                     = var.tags
}

resource "azurerm_cdn_frontdoor_origin_group" "ingestion" {
  name                     = "og-ingestion"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  load_balancing {}
  health_probe {
    interval_in_seconds = 30
    path                = "/healthz"
    protocol            = "Https"
    request_type        = "GET"
  }
}

resource "azurerm_cdn_frontdoor_origin" "ingestion" {
  name                           = "origin-ingestion"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.ingestion.id
  enabled                        = true
  host_name                      = var.ingestion_api_fqdn
  origin_host_header             = var.ingestion_api_fqdn
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true
  https_port                     = 443
  http_port                      = 80
}

resource "azurerm_cdn_frontdoor_origin_group" "analytics" {
  name                     = "og-analytics"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  load_balancing {}
  health_probe {
    interval_in_seconds = 30
    path                = "/healthz"
    protocol            = "Https"
    request_type        = "GET"
  }
}

resource "azurerm_cdn_frontdoor_origin" "analytics" {
  name                           = "origin-analytics"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.analytics.id
  enabled                        = true
  host_name                      = var.analytics_api_fqdn != "" ? var.analytics_api_fqdn : var.ingestion_api_fqdn
  origin_host_header             = var.analytics_api_fqdn != "" ? var.analytics_api_fqdn : var.ingestion_api_fqdn
  priority                       = 1
  weight                         = 1000
  certificate_name_check_enabled = true
  https_port                     = 443
  http_port                      = 80
}

resource "azurerm_cdn_frontdoor_route" "ingestion" {
  name                          = "route-ingestion"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.ingestion.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.ingestion.id]
  enabled                       = true
  forwarding_protocol           = "HttpsOnly"
  https_redirect_enabled        = true
  link_to_default_domain        = true
  patterns_to_match             = ["/api/v1/measurements*", "/api/v1/devices*", "/api/v1/reports*", "/healthz", "/readyz", "/docs*"]
  supported_protocols           = ["Http", "Https"]
}

resource "azurerm_cdn_frontdoor_route" "analytics" {
  name                          = "route-analytics"
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.analytics.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.analytics.id]
  enabled                       = true
  forwarding_protocol           = "HttpsOnly"
  https_redirect_enabled        = true
  link_to_default_domain        = false
  patterns_to_match             = ["/api/v1/analytics*"]
  supported_protocols           = ["Http", "Https"]
}

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  name                = "waf${var.project}${var.environment}"
  resource_group_name = azurerm_resource_group.frontdoor.name
  sku_name            = azurerm_cdn_frontdoor_profile.main.sku_name
  enabled             = true
  mode                = var.environment == "prod" ? "Prevention" : "Detection"
  tags                = var.tags

  managed_rule {
    type    = "Microsoft_DefaultRuleSet"
    version = "2.1"
    action  = "Block"
  }

  managed_rule {
    type    = "Microsoft_BotManagerRuleSet"
    version = "1.1"
    action  = "Block"
  }

  custom_rule {
    name                           = "RateLimitAll"
    action                         = "Block"
    enabled                        = true
    priority                       = 100
    type                           = "RateLimitRule"
    rate_limit_duration_in_minutes = 1
    rate_limit_threshold           = 1000

    match_condition {
      match_variable     = "RequestUri"
      operator           = "Contains"
      negation_condition = false
      match_values       = ["/api/"]
    }
  }
}

resource "azurerm_cdn_frontdoor_security_policy" "main" {
  name                     = "sp-${var.project}-${var.environment}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.main.id
      association {
        patterns_to_match = ["/*"]
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.main.id
        }
      }
    }
  }
}
