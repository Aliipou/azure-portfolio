variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "log_analytics_workspace_id" { type = string }
variable "app_subnet_id"              { type = string }
variable "managed_identity_id"        { type = string }
variable "managed_identity_client_id" { type = string }
variable "key_vault_uri"              { type = string }
variable "servicebus_queue_name"      { type = string }
variable "servicebus_connection_string" { type = string; sensitive = true }
variable "api_image"    { type = string; default = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" }
variable "worker_image" { type = string; default = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" }
variable "api_min_replicas"    { type = number; default = 1 }
variable "api_max_replicas"    { type = number; default = 10 }
variable "worker_min_replicas" { type = number; default = 1 }
variable "worker_max_replicas" { type = number; default = 5 }
