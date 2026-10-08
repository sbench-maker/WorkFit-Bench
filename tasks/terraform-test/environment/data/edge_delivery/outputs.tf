output "network_summary" {
  description = "Plan-known deployment summary used by policy checks."
  value = {
    service_name      = var.service_name
    environment       = var.environment
    network_cidr      = var.network_cidr
    subnet_count      = var.subnet_count
    endpoint_count    = var.enable_private_endpoints ? var.subnet_count : 0
    high_availability = var.subnet_count >= 3
    tags              = local.effective_tags
  }
}

output "subnet_matrix" {
  description = "Deterministic CIDR and zone placement for each private subnet."
  value = [
    for index in range(var.subnet_count) : {
      index              = index
      cidr               = local.subnet_cidrs[index]
      zone               = local.subnet_zones[index]
      public_ip_on_launch = false
    }
  ]
}

output "endpoint_subnet_cidrs" {
  description = "Subnets that receive an object-store private endpoint attachment."
  value = var.enable_private_endpoints ? [
    for cidr in local.subnet_cidrs : cidr
  ] : []
}
