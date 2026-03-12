# Remote state in Azure Storage — configure via -backend-config or environment vars
# az storage account create --name stterraformbeamex --resource-group rg-terraform-state
# az storage container create --name tfstate --account-name stterraformbeamex

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "stterraformbeamex"
    container_name       = "tfstate"
    key                  = "calibration-platform.tfstate"
    use_oidc             = true  # GitHub Actions OIDC — no client secret
  }
}
