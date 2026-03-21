# =============================================================================
# Multi-Provider Variables — Choose your cloud
# =============================================================================

variable "cloud_provider" {
  type        = string
  description = "Target cloud: aws | gcp | azure | oci"
  default     = "aws"

  validation {
    condition     = contains(["aws", "gcp", "azure", "oci"], var.cloud_provider)
    error_message = "cloud_provider must be one of: aws, gcp, azure, oci"
  }
}

variable "env" {
  type        = string
  description = "Environment: dev | staging | prod"
  default     = "dev"
}

variable "image_tag" {
  type        = string
  description = "Docker image tag to deploy"
  default     = "latest"
}

variable "desired_count" {
  type        = number
  description = "Number of service instances"
  default     = 1
}

# ---------- AWS-specific ----------
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "aws_profile" {
  type    = string
  default = "default"
}

variable "vpc_id" {
  type        = string
  description = "AWS VPC ID (required for AWS deployments)"
  default     = ""
}

variable "public_subnets" {
  type        = list(string)
  description = "AWS public subnet IDs"
  default     = []
}

# ---------- GCP-specific ----------
variable "gcp_project_id" {
  type        = string
  description = "GCP project ID"
  default     = ""
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

# ---------- Azure-specific ----------
variable "azure_location" {
  type    = string
  default = "East US"
}

variable "azure_resource_group" {
  type        = string
  description = "Azure resource group name"
  default     = "agentic-ai-rg"
}

# ---------- OCI-specific ----------
variable "oci_compartment_id" {
  type        = string
  description = "OCI compartment OCID"
  default     = ""
}

variable "oci_region" {
  type    = string
  default = "us-ashburn-1"
}
