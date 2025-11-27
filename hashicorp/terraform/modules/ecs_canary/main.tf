# ECS Canary Deployment with ALB Weighted Target Groups
# This module creates an ECS setup supporting canary deployments via weighted routing

variable "app_name" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "public_subnets" { type = list(string) }
variable "private_subnets" { type = list(string) }
variable "aws_region" { type = string }
variable "stable_image_tag" { type = string }
variable "canary_image_tag" { type = string, default = "" }
variable "desired_count_stable" { type = number, default = 3 }
variable "desired_count_canary" { type = number, default = 1 }
variable "canary_weight" { type = number, default = 10 }
variable "health_check_path" { type = string, default = "/api/new_chat" }

# ECR Repository
resource "aws_ecr_repository" "repo" {
  name = "${var.app_name}-${var.env}"
}

# ECS Cluster
resource "aws_ecs_cluster" "this" {
  name = "${var.app_name}-${var.env}"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "stable" {
  name              = "/ecs/${var.app_name}-stable/${var.env}"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "canary" {
  name              = "/ecs/${var.app_name}-canary/${var.env}"
  retention_in_days = 14
}

# IAM Roles
data "aws_iam_policy_document" "ecs_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_exec" {
  name               = "${var.app_name}-task-exec-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  ]
}

# Task Definition - Stable
resource "aws_ecs_task_definition" "stable" {
  family                   = "${var.app_name}-stable-${var.env}"
  cpu                      = 512
  memory                   = 1024
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([{
    name  = "app"
    image = "${aws_ecr_repository.repo.repository_url}:${var.stable_image_tag}"
    portMappings = [{ containerPort = 8000 }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.stable.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "stable"
      }
    }
    environment = [
      { name = "APP_HOST", value = "0.0.0.0" },
      { name = "APP_PORT", value = "8000" },
      { name = "DEPLOYMENT_TRACK", value = "stable" }
    ]
  }])
}

# Task Definition - Canary
resource "aws_ecs_task_definition" "canary" {
  family                   = "${var.app_name}-canary-${var.env}"
  cpu                      = 512
  memory                   = 1024
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([{
    name  = "app"
    image = "${aws_ecr_repository.repo.repository_url}:${var.canary_image_tag != "" ? var.canary_image_tag : var.stable_image_tag}"
    portMappings = [{ containerPort = 8000 }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.canary.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "canary"
      }
    }
    environment = [
      { name = "APP_HOST", value = "0.0.0.0" },
      { name = "APP_PORT", value = "8000" },
      { name = "DEPLOYMENT_TRACK", value = "canary" }
    ]
  }])
}

# Security Group
resource "aws_security_group" "sg" {
  name   = "${var.app_name}-${var.env}"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Application Load Balancer
resource "aws_lb" "alb" {
  name               = "${var.app_name}-alb-${var.env}"
  load_balancer_type = "application"
  subnets            = var.public_subnets
  security_groups    = [aws_security_group.sg.id]
}

# Target Group - Stable
resource "aws_lb_target_group" "stable" {
  name        = "${var.app_name}-stable-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Track = "stable" }
}

# Target Group - Canary
resource "aws_lb_target_group" "canary" {
  name        = "${var.app_name}-canary-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Track = "canary" }
}

# ALB Listener with Weighted Target Groups
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "forward"

    forward {
      target_group {
        arn    = aws_lb_target_group.stable.arn
        weight = 100 - var.canary_weight
      }

      target_group {
        arn    = aws_lb_target_group.canary.arn
        weight = var.canary_weight
      }

      stickiness {
        enabled  = true
        duration = 3600
      }
    }
  }
}

# ECS Service - Stable
resource "aws_ecs_service" "stable" {
  name            = "${var.app_name}-stable-${var.env}"
  cluster         = aws_ecs_cluster.this.id
  desired_count   = var.desired_count_stable
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.stable.arn

  network_configuration {
    subnets          = var.private_subnets
    assign_public_ip = true
    security_groups  = [aws_security_group.sg.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.stable.arn
    container_name   = "app"
    container_port   = 8000
  }
}

# ECS Service - Canary
resource "aws_ecs_service" "canary" {
  name            = "${var.app_name}-canary-${var.env}"
  cluster         = aws_ecs_cluster.this.id
  desired_count   = var.desired_count_canary
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.canary.arn

  network_configuration {
    subnets          = var.private_subnets
    assign_public_ip = true
    security_groups  = [aws_security_group.sg.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.canary.arn
    container_name   = "app"
    container_port   = 8000
  }
}

# Outputs
output "alb_dns_name" {
  value = aws_lb.alb.dns_name
}

output "stable_service_name" {
  value = aws_ecs_service.stable.name
}

output "canary_service_name" {
  value = aws_ecs_service.canary.name
}
