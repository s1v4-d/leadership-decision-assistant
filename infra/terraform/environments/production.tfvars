environment = "production"
aws_region  = "us-east-1"
app_name    = "leadership-agent"

ecs_cpu           = 2048
ecs_memory        = 4096
ecs_desired_count = 2

db_instance_class        = "db.t3.small"
db_allocated_storage     = 50
db_max_allocated_storage = 200

cache_node_type    = "cache.t3.small"
log_retention_days = 90
