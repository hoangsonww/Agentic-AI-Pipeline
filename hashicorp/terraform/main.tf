module "agentic_ai" {
  source           = "./modules/ecs_fargate"
  vpc_id           = var.vpc_id
  public_subnets   = var.public_subnets
  private_subnets  = var.public_subnets   # demo: reuse public subnets
  aws_region       = var.aws_region
  image_tag        = var.image_tag
  env              = var.env
  desired_count    = var.desired_count
}
