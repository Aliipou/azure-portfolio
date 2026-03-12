variable "project"     { type = string }
variable "environment" { type = string }
variable "location"    { type = string }
variable "tags"        { type = map(string) }
variable "github_org"  { type = string; default = "Aliipou" }
variable "github_repo" { type = string; default = "cloud-calibration-platform" }
