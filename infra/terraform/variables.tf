variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
}

variable "app_name" {
  description = "Application name used in resource naming"
  type        = string
  default     = "leadership-agent"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "app_port" {
  description = "Port for the FastAPI backend"
  type        = number
  default     = 8000
}

variable "ui_port" {
  description = "Port for the Streamlit UI"
  type        = number
  default     = 8501
}

variable "ecs_cpu" {
  description = "CPU units for the ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "ecs_memory" {
  description = "Memory in MiB for the ECS task"
  type        = number
  default     = 2048
}

variable "ecs_desired_count" {
  description = "Number of ECS task instances to run"
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Initial allocated storage in GB for RDS"
  type        = number
  default     = 20
}

variable "db_max_allocated_storage" {
  description = "Maximum autoscaled storage in GB for RDS"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "leadership_agent"
}

variable "db_username" {
  description = "Master username for the RDS instance"
  type        = string
  default     = "leadership"
}

variable "db_password" {
  description = "Master password for the RDS instance"
  type        = string
  sensitive   = true
}

variable "db_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for database password"
  type        = string
  default     = ""
}

variable "openai_api_key_secret_arn" {
  description = "ARN of the Secrets Manager secret for OpenAI API key"
  type        = string
  default     = ""
}

variable "cache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 30
}
