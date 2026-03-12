data "azurerm_subscription" "current" {}
data "azuread_client_config" "current" {}

resource "azurerm_resource_group" "identity" {
  name     = "rg-${var.project}-identity-${var.environment}"
  location = var.location
  tags     = var.tags
}

# User-assigned Managed Identity for Container Apps
resource "azurerm_user_assigned_identity" "app" {
  name                = "mi-${var.project}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.identity.name
  tags                = var.tags
}

# Azure AD App Registration for the API
resource "azuread_application" "api" {
  display_name     = "${var.project}-api-${var.environment}"
  sign_in_audience = "AzureADMyOrg"

  app_role {
    allowed_member_types = ["User"]
    description          = "Full admin access"
    display_name         = "Admin"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000001"
    value                = "Admin"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Can submit and view measurements"
    display_name         = "Operator"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000002"
    value                = "Operator"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Read-only access to measurements and analytics"
    display_name         = "Viewer"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000003"
    value                = "Viewer"
  }
}

resource "azuread_service_principal" "api" {
  client_id = azuread_application.api.client_id
}

# OIDC Federated Credential for GitHub Actions (no stored secrets)
resource "azuread_application_federated_identity_credential" "github_main" {
  application_id = azuread_application.api.id
  display_name   = "github-main"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
}

resource "azuread_application_federated_identity_credential" "github_env_prod" {
  application_id = azuread_application.api.id
  display_name   = "github-env-prod"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_org}/${var.github_repo}:environment:production"
}
