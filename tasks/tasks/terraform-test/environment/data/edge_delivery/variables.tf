variable "service_name" {
  description = "Short service identifier used in resource metadata."
  type        = string
  default     = "edge-router"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.service_name))
    error_message = "service_name must be 3-24 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment tier."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "network_cidr" {
  description = "IPv4 network from which private /24 subnets are allocated."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.network_cidr))
    error_message = "network_cidr must be valid IPv4 CIDR notation."
  }
}

variable "subnet_count" {
  description = "Number of private subnets. Production requires at least three."
  type        = number
  default     = 2

  validation {
    condition     = var.subnet_count >= 2 && var.subnet_count <= 6 && floor(var.subnet_count) == var.subnet_count
    error_message = "subnet_count must be a whole number from 2 through 6."
  }
}

variable "availability_zones" {
  description = "Ordered zone pool used in round-robin subnet placement."
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]

  validation {
    condition = (
      length(var.availability_zones) >= 3 &&
      length(distinct(var.availability_zones)) == length(var.availability_zones)
    )
    error_message = "availability_zones must contain at least three distinct zones."
  }
}

variable "enable_private_endpoints" {
  description = "Create one private endpoint attachment for every private subnet."
  type        = bool
  default     = false
}

variable "common_tags" {
  description = "Caller tags. Environment, ManagedBy, and Service are protected."
  type        = map(string)
  default     = {}
}
