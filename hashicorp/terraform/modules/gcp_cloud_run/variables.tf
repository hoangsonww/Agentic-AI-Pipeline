# =============================================================================
# Variables — GCP Cloud Run Module
# =============================================================================
# All tunables for the Agentic AI Cloud Run deployment. Sensible defaults
# are provided so that a minimal `terraform apply` works for dev; production
# overrides are applied through tfvars files or CI/CD variable injection.
# =============================================================================

# ---------------------------------------------------------------------------
# Project & Region
# ---------------------------------------------------------------------------
variable "project_id" {
  description = "GCP project ID where all resources will be created."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid GCP project ID (6-30 lowercase alphanumeric characters or hyphens)."
  }
}

variable "region" {
  description = "GCP region for all regional resources (Cloud Run, Cloud SQL, VPC connector)."
  type        = string
  default     = "us-central1"
}

# ---------------------------------------------------------------------------
# Environment & Naming
# ---------------------------------------------------------------------------
variable "env" {
  description = "Deployment environment — controls naming, scaling, and deletion protection."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod."
  }
}

variable "service_name" {
  description = "Base name for the Cloud Run service and related resources."
  type        = string
  default     = "agentic-ai"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,48}[a-z0-9]$", var.service_name))
    error_message = "service_name must be lowercase alphanumeric with hyphens, 3-50 characters."
  }
}

# ---------------------------------------------------------------------------
# Container Image
# ---------------------------------------------------------------------------
variable "image_tag" {
  description = "Docker image tag to deploy. Use a SHA digest in production for immutability."
  type        = string
  default     = "latest"
}

# ---------------------------------------------------------------------------
# Cloud Run Compute — Scaling & Resources
# ---------------------------------------------------------------------------
variable "min_instances" {
  description = "Minimum number of Cloud Run instances (set > 0 to avoid cold starts in prod)."
  type        = number
  default     = 1

  validation {
    condition     = var.min_instances >= 0 && var.min_instances <= 100
    error_message = "min_instances must be between 0 and 100."
  }
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances for autoscaling."
  type        = number
  default     = 10

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 1000
    error_message = "max_instances must be between 1 and 1000."
  }
}

variable "cpu" {
  description = "CPU allocation per Cloud Run instance (e.g. '1', '2', '4')."
  type        = string
  default     = "1"

  validation {
    condition     = contains(["1", "2", "4", "8"], var.cpu)
    error_message = "cpu must be one of: 1, 2, 4, 8."
  }
}

variable "memory" {
  description = "Memory allocation per Cloud Run instance (e.g. '512Mi', '1Gi', '2Gi', '4Gi')."
  type        = string
  default     = "2Gi"

  validation {
    condition     = can(regex("^[0-9]+(Mi|Gi)$", var.memory))
    error_message = "memory must be a valid Kubernetes-style quantity (e.g. '512Mi', '2Gi')."
  }
}

variable "container_port" {
  description = "Port the application listens on inside the container."
  type        = number
  default     = 8000
}

variable "request_timeout" {
  description = "Maximum request duration in seconds before Cloud Run terminates it."
  type        = number
  default     = 300
}

variable "container_concurrency" {
  description = "Maximum concurrent requests per container instance."
  type        = number
  default     = 80
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "vpc_connector_cidr" {
  description = "CIDR range for the Serverless VPC Access connector (/28 required)."
  type        = string
  default     = "10.8.0.0/28"
}

variable "enable_vpc_connector" {
  description = "Whether to create a VPC connector for private networking (required for Cloud SQL private IP)."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Cloud SQL (optional)
# ---------------------------------------------------------------------------
variable "enable_cloud_sql" {
  description = "Whether to provision a Cloud SQL PostgreSQL instance. Set false for dev (SQLite works locally)."
  type        = bool
  default     = false
}

variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier. Use db-f1-micro for dev, db-custom-2-7680 for prod."
  type        = string
  default     = "db-f1-micro"
}

variable "cloud_sql_disk_size_gb" {
  description = "Initial disk size in GB for the Cloud SQL instance."
  type        = number
  default     = 10
}

variable "cloud_sql_availability_type" {
  description = "Cloud SQL availability: ZONAL for dev, REGIONAL for prod (automatic failover)."
  type        = string
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.cloud_sql_availability_type)
    error_message = "cloud_sql_availability_type must be ZONAL or REGIONAL."
  }
}

variable "database_name" {
  description = "Name of the PostgreSQL database to create inside the Cloud SQL instance."
  type        = string
  default     = "agentic_ai"
}

# ---------------------------------------------------------------------------
# Load Balancing & Domain
# ---------------------------------------------------------------------------
variable "domain_name" {
  description = "Custom domain for the HTTPS load balancer. Leave empty to use the default Cloud Run URL."
  type        = string
  default     = ""
}

variable "enable_cdn" {
  description = "Whether to enable Cloud CDN on the load balancer backend."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Secret Manager — API keys injected into Cloud Run as env vars
# ---------------------------------------------------------------------------
variable "secret_env_vars" {
  description = <<-EOT
    Map of environment variable names to Secret Manager secret IDs.
    Each entry creates a secret reference in the Cloud Run container.
    Example: { "OPENAI_API_KEY" = "openai-api-key", "ANTHROPIC_API_KEY" = "anthropic-api-key" }
  EOT
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Plain-text environment variables
# ---------------------------------------------------------------------------
variable "env_vars" {
  description = <<-EOT
    Map of non-secret environment variables to set on the Cloud Run container.
    Example: { "LOG_LEVEL" = "info", "WORKERS" = "1" }
  EOT
  type        = map(string)
  default = {
    APP_HOST = "0.0.0.0"
    APP_PORT = "8000"
  }
}

# ---------------------------------------------------------------------------
# IAM — Public access
# ---------------------------------------------------------------------------
variable "allow_unauthenticated" {
  description = "Whether to allow unauthenticated (public) access to the Cloud Run service."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
variable "extra_labels" {
  description = "Additional labels to apply to all resources. Merged with default labels."
  type        = map(string)
  default     = {}
}
