resource "aws_ecr_repository" "repo" {
  name = "agentic-ai"
}

resource "aws_ecs_cluster" "this" {
  name = "agentic-ai-${var.env}"
}

resource "aws_cloudwatch_log_group" "lg" {
  name              = "/ecs/agentic-ai/${var.env}"
  retention_in_days = 14
}

data "aws_iam_policy_document" "ecs_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals { type = "Service", identifiers = ["ecs-tasks.amazonaws.com"] }
  }
}

resource "aws_iam_role" "task_exec" {
  name               = "agentic-ai-task-exec-${var.env}"
  assume_role_policy = data.aws_iam_policy_document.ecs_trust.json
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"]
}

resource "aws_ecs_task_definition" "task" {
  family                   = "agentic-ai-${var.env}"
  cpu                      = 512
  memory                   = 1024
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task_exec.arn

  container_definitions = jsonencode([{
    name  = "app"
    image = "${aws_ecr_repository.repo.repository_url}:${var.image_tag}"
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs",
      options = {
        awslogs-group         = aws_cloudwatch_log_group.lg.name,
        awslogs-region        = var.aws_region,
        awslogs-stream-prefix = "ecs"
      }
    }
    environment = [
      { name = "APP_HOST", value = "0.0.0.0" },
      { name = "APP_PORT", value = "8000" }
    ]
  }])
}

resource "aws_security_group" "sg" {
  name        = "agentic-ai-${var.env}"
  description = "Allow HTTP"
  vpc_id      = var.vpc_id
  ingress { from_port = 8000 to_port = 8000 protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0    to_port = 0    protocol = "-1"  cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_lb" "alb" {
  name               = "agentic-ai-alb-${var.env}"
  load_balancer_type = "application"
  subnets            = var.public_subnets
  security_groups    = [aws_security_group.sg.id]
}

resource "aws_lb_target_group" "tg" {
  name     = "agentic-ai-tg-${var.env}"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  health_check { path = "/api/new_chat" }
}

resource "aws_lb_listener" "listener" {
  load_balancer_arn = aws_lb.alb.arn
  port              = 80
  protocol          = "HTTP"
  default_action { type = "forward", target_group_arn = aws_lb_target_group.tg.arn }
}

resource "aws_ecs_service" "svc" {
  name            = "agentic-ai-${var.env}"
  cluster         = aws_ecs_cluster.this.id
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  task_definition = aws_ecs_task_definition.task.arn
  network_configuration {
    subnets          = var.private_subnets
    assign_public_ip = true
    security_groups  = [aws_security_group.sg.id]
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.tg.arn
    container_name   = "app"
    container_port   = 8000
  }
}
