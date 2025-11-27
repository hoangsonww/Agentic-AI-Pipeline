# ECS Blue/Green Deployment with CodeDeploy
# This module creates an ECS service with blue/green deployment support

variable "app_name" { type = string }
variable "env" { type = string }
variable "vpc_id" { type = string }
variable "public_subnets" { type = list(string) }
variable "private_subnets" { type = list(string) }
variable "aws_region" { type = string }
variable "image_tag" { type = string }
variable "desired_count" { type = number, default = 2 }
variable "health_check_path" { type = string, default = "/api/new_chat" }

# ECR Repository
resource "aws_ecr_repository" "repo" {
  name = "${var.app_name}-${var.env}"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "this" {
  name = "${var.app_name}-${var.env}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lg" {
  name              = "/ecs/${var.app_name}/${var.env}"
  retention_in_days = 30
}

# IAM Role for ECS Task Execution
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

# ECS Task Definition
resource "aws_ecs_task_definition" "task" {
  family                   = "${var.app_name}-${var.env}"
  cpu                      = 512
  memory                   = 1024
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([{
    name  = "app"
    image = "${aws_ecr_repository.repo.repository_url}:${var.image_tag}"
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.lg.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    environment = [
      { name = "APP_HOST", value = "0.0.0.0" },
      { name = "APP_PORT", value = "8000" }
    ]
    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:8000${var.health_check_path} || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }
  }])
}

# Security Group
resource "aws_security_group" "sg" {
  name        = "${var.app_name}-${var.env}"
  description = "Allow HTTP traffic"
  vpc_id      = var.vpc_id

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

  tags = {
    Name = "${var.app_name}-${var.env}"
  }
}

# Application Load Balancer
resource "aws_lb" "alb" {
  name               = "${var.app_name}-alb-${var.env}"
  load_balancer_type = "application"
  subnets            = var.public_subnets
  security_groups    = [aws_security_group.sg.id]

  enable_deletion_protection = false
  enable_http2               = true

  tags = {
    Environment = var.env
  }
}

# Target Group 1 (Blue)
resource "aws_lb_target_group" "blue" {
  name        = "${var.app_name}-blue-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "blue"
  }
}

# Target Group 2 (Green)
resource "aws_lb_target_group" "green" {
  name        = "${var.app_name}-green-${var.env}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "green"
  }
}

# ALB Listener - Production (Port 80)
resource "aws_lb_listener" "production" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blue.arn
  }

  lifecycle {
    ignore_changes = [default_action]
  }
}

# ALB Listener - Test (Port 8080)
resource "aws_lb_listener" "test" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 8080
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.green.arn
  }

  lifecycle {
    ignore_changes = [default_action]
  }
}

# IAM Role for CodeDeploy
resource "aws_iam_role" "codedeploy" {
  name = "${var.app_name}-codedeploy-${var.env}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "codedeploy.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  managed_policy_arns = [
    "arn:aws:iam::aws:policy/AWSCodeDeployRoleForECS"
  ]
}

# CodeDeploy Application
resource "aws_codedeploy_app" "app" {
  compute_platform = "ECS"
  name             = "${var.app_name}-${var.env}"
}

# CodeDeploy Deployment Group
resource "aws_codedeploy_deployment_group" "group" {
  app_name               = aws_codedeploy_app.app.name
  deployment_group_name  = "${var.app_name}-dg-${var.env}"
  service_role_arn       = aws_iam_role.codedeploy.arn
  deployment_config_name = "CodeDeployDefault.ECSAllAtOnce"

  auto_rollback_configuration {
    enabled = true
    events  = ["DEPLOYMENT_FAILURE", "DEPLOYMENT_STOP_ON_ALARM"]
  }

  blue_green_deployment_config {
    terminate_blue_instances_on_deployment_success {
      action                           = "TERMINATE"
      termination_wait_time_in_minutes = 5
    }

    deployment_ready_option {
      action_on_timeout = "CONTINUE_DEPLOYMENT"
    }
  }

  deployment_style {
    deployment_option = "WITH_TRAFFIC_CONTROL"
    deployment_type   = "BLUE_GREEN"
  }

  ecs_service {
    cluster_name = aws_ecs_cluster.this.name
    service_name = aws_ecs_service.svc.name
  }

  load_balancer_info {
    target_group_pair_info {
      prod_traffic_route {
        listener_arns = [aws_lb_listener.production.arn]
      }

      test_traffic_route {
        listener_arns = [aws_lb_listener.test.arn]
      }

      target_group {
        name = aws_lb_target_group.blue.name
      }

      target_group {
        name = aws_lb_target_group.green.name
      }
    }
  }
}

# ECS Service with Blue/Green deployment
resource "aws_ecs_service" "svc" {
  name            = "${var.app_name}-${var.env}"
  cluster         = aws_ecs_cluster.this.id
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.task.arn

  deployment_controller {
    type = "CODE_DEPLOY"
  }

  network_configuration {
    subnets          = var.private_subnets
    assign_public_ip = true
    security_groups  = [aws_security_group.sg.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.blue.arn
    container_name   = "app"
    container_port   = 8000
  }

  lifecycle {
    ignore_changes = [task_definition, load_balancer]
  }

  depends_on = [aws_lb_listener.production]
}

# Outputs
output "alb_dns_name" {
  value = aws_lb.alb.dns_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.repo.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.svc.name
}

output "codedeploy_app_name" {
  value = aws_codedeploy_app.app.name
}

output "codedeploy_deployment_group" {
  value = aws_codedeploy_deployment_group.group.deployment_group_name
}
