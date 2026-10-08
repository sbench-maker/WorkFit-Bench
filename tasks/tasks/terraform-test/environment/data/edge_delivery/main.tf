locals {
  reserved_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Service     = var.service_name
  }

  effective_tags = merge(var.common_tags, local.reserved_tags)

  subnet_cidrs = [
    for index in range(var.subnet_count) :
    cidrsubnet(var.network_cidr, 8, index + 10)
  ]

  subnet_zones = [
    for index in range(var.subnet_count) :
    var.availability_zones[index % length(var.availability_zones)]
  ]
}

resource "terraform_data" "network" {
  input = {
    service_name = var.service_name
    environment  = var.environment
    network_cidr = var.network_cidr
    tags         = local.effective_tags
  }

  lifecycle {
    precondition {
      condition     = var.environment != "prod" || var.subnet_count >= 3
      error_message = "Production deployments require at least three private subnets."
    }
  }
}

resource "terraform_data" "private_subnet" {
  count = var.subnet_count

  input = {
    index        = count.index
    network_id   = terraform_data.network.id
    cidr         = local.subnet_cidrs[count.index]
    zone         = local.subnet_zones[count.index]
    assign_ipv4  = false
    resource_tag = "${var.service_name}-${var.environment}-private-${count.index + 1}"
    tags         = local.effective_tags
  }
}

resource "terraform_data" "private_endpoint" {
  count = var.enable_private_endpoints ? var.subnet_count : 0

  input = {
    subnet_index = count.index
    subnet_cidr  = local.subnet_cidrs[count.index]
    zone         = local.subnet_zones[count.index]
    service      = "object-store"
    tags         = local.effective_tags
  }
}
