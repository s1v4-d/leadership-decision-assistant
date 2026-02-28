data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "${var.app_name}-${var.environment}"

  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  tags = {
    Project     = var.app_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
