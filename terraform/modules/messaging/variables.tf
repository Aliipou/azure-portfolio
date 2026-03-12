variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "servicebus_sku" { type = string; default = "Basic" }
variable "data_subnet_id" { type = string }
variable "servicebus_private_dns_zone_id" { type = string }
variable "managed_identity_principal_id" { type = string }
