variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "postgres_sku" { type = string; default = "Standard_B1ms" }
variable "data_subnet_id" { type = string }
variable "postgres_private_dns_zone_id" { type = string }
variable "tenant_id" { type = string }
variable "managed_identity_principal_id" { type = string }
