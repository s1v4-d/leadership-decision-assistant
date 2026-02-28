environment = "staging"
aws_region  = "us-east-1"
app_name    = "leadership-agent"

ecs_cpu           = 1024
ecs_memory        = 2048
ecs_desired_count = 1

db_instance_class    = "db.t3.micro"
db_allocated_storage = 20

cache_node_type    = "cache.t3.micro"
log_retention_days = 14
