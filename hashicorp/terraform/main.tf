# =============================================================================
# Multi-Provider Root Module
# =============================================================================
# Usage:
#   terraform init
#   terraform plan -var="cloud_provider=aws" -var="vpc_id=vpc-xxx" ...
#   terraform plan -var="cloud_provider=gcp" -var="gcp_project_id=my-proj" ...
#   terraform plan -var="cloud_provider=azure" ...
#   terraform plan -var="cloud_provider=oci" -var="oci_compartment_id=ocid1..." ...
# =============================================================================

# ---------- AWS: ECS Fargate ----------
module "aws" {
  source  = "./modules/ecs_fargate"
  count   = var.cloud_provider == "aws" ? 1 : 0

  vpc_id          = var.vpc_id
  public_subnets  = var.public_subnets
  private_subnets = var.public_subnets
  aws_region      = var.aws_region
  image_tag       = var.image_tag
  env             = var.env
  desired_count   = var.desired_count
}

# ---------- GCP: Cloud Run ----------
module "gcp" {
  source  = "./modules/gcp_cloud_run"
  count   = var.cloud_provider == "gcp" ? 1 : 0

  project_id = var.gcp_project_id
  region     = var.gcp_region
  env        = var.env
  image_tag  = var.image_tag
}

# ---------- Azure: Container Apps ----------
module "azure" {
  source  = "./modules/azure_container_apps"
  count   = var.cloud_provider == "azure" ? 1 : 0

  location             = var.azure_location
  resource_group_name  = var.azure_resource_group
  env                  = var.env
  image_tag            = var.image_tag
}

# ---------- OCI: Container Instances ----------
module "oci" {
  source  = "./modules/oci_container_instances"
  count   = var.cloud_provider == "oci" ? 1 : 0

  compartment_id = var.oci_compartment_id
  region         = var.oci_region
  env            = var.env
  image_tag      = var.image_tag
}
