variable "environment" {
  type        = string
  description = "Deployment environment"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "location" {
  type        = string
  description = "Azure region"
  default     = "northeurope"
  validation {
    condition     = contains(["northeurope", "westeurope"], var.location)
    error_message = "Only EU regions are permitted."
  }
}

variable "project" {
  type        = string
  description = "Project name used in resource naming"
  default     = "calibration"
  validation {
    condition     = can(regex("^[a-z0-9]{3,15}$", var.project))
    error_message = "project must be 3-15 lowercase alphanumeric characters."
  }
}

variable "owner" {
  type    = string
  default = "ali.pourrahim@beamex.com"
}

variable "github_org" {
  type    = string
  default = "Aliipou"
}

variable "github_repo" {
  type    = string
  default = "cloud-calibration-platform"
}

# Environment-specific SKUs
variable "postgres_sku" {
  type    = string
  default = "Standard_B1ms"
}

variable "servicebus_sku" {
  type    = string
  default = "Basic"
}

variable "api_min_replicas" {
  type    = number
  default = 1
}

variable "api_max_replicas" {
  type    = number
  default = 10
}

variable "worker_min_replicas" {
  type    = number
  default = 1
}

variable "worker_max_replicas" {
  type    = number
  default = 5
}

variable "log_retention_days" {
  type    = number
  default = 90
}

variable "alert_email" {
  type    = string
  default = "ops@beamex.com"
}
