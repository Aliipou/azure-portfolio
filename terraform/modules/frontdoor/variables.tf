variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "ingestion_api_fqdn" { type = string }
variable "analytics_api_fqdn" { type = string; default = "" }
