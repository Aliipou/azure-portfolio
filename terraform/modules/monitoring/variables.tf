variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "log_retention_days" { type = number; default = 90 }
variable "alert_email" { type = string; default = "ops@beamex.com" }
