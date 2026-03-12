variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "data_subnet_id" { type = string }
variable "blob_private_dns_zone_id" { type = string }
variable "managed_identity_principal_id" { type = string }
