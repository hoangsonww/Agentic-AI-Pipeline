# ------------------------------------------------------------------------------
# OCI Container Instances Module - Variables
# ------------------------------------------------------------------------------
# All configurable parameters for the Agentic AI deployment on Oracle Cloud
# Infrastructure. Sensible defaults are provided where possible; callers MUST
# supply compartment_id and availability_domain at a minimum.
# ------------------------------------------------------------------------------

# ========================== Identity & Region ==================================

variable "compartment_id" {
  description = "OCID of the compartment where all resources will be created."
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.compartment\\.", var.compartment_id))
    error_message = "compartment_id must be a valid OCI compartment OCID."
  }
}

variable "tenancy_ocid" {
  description = "OCID of the tenancy. Required for defined tags and policy creation."
  type        = string
  default     = ""
}

variable "region" {
  description = "OCI region identifier (e.g. us-ashburn-1, eu-frankfurt-1)."
  type        = string
  default     = "us-ashburn-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.region))
    error_message = "region must follow the OCI region format (e.g. us-ashburn-1)."
  }
}

variable "availability_domain" {
  description = "Full name of the availability domain (e.g. Uocm:US-ASHBURN-AD-1)."
  type        = string
}

# ========================== Environment & Naming ===============================

variable "env" {
  description = "Deployment environment: dev, staging, or prod."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod."
  }
}

variable "project_name" {
  description = "Project name used as a prefix for all resource display names."
  type        = string
  default     = "agentic-ai"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.project_name))
    error_message = "project_name must be lowercase alphanumeric with hyphens, 2-31 chars."
  }
}

# ========================== Container Image ====================================

variable "image_tag" {
  description = "Container image tag to deploy from OCIR."
  type        = string
  default     = "latest"
}

variable "ocir_namespace" {
  description = "OCIR object storage namespace (tenancy namespace). Leave empty to auto-derive."
  type        = string
  default     = ""
}

variable "ocir_repo_name" {
  description = "Name of the OCIR repository."
  type        = string
  default     = "agentic-ai"
}

variable "mcp_image_tag" {
  description = "Container image tag for the MCP server. Falls back to image_tag if empty."
  type        = string
  default     = ""
}

variable "mcp_ocir_repo_name" {
  description = "Name of the OCIR repository for the MCP server image."
  type        = string
  default     = "agentic-ai-mcp"
}

# ========================== Compute Shape ======================================

variable "shape" {
  description = "OCI Container Instance shape."
  type        = string
  default     = "CI.Standard.E4.Flex"

  validation {
    condition     = contains(["CI.Standard.E3.Flex", "CI.Standard.E4.Flex"], var.shape)
    error_message = "shape must be a valid OCI Container Instance flex shape."
  }
}

variable "ocpus" {
  description = "Number of OCPUs allocated to each container instance."
  type        = number
  default     = 1

  validation {
    condition     = var.ocpus >= 1 && var.ocpus <= 64
    error_message = "ocpus must be between 1 and 64."
  }
}

variable "memory_in_gbs" {
  description = "Memory in GBs allocated to each container instance."
  type        = number
  default     = 2

  validation {
    condition     = var.memory_in_gbs >= 1 && var.memory_in_gbs <= 1024
    error_message = "memory_in_gbs must be between 1 and 1024."
  }
}

variable "mcp_ocpus" {
  description = "Number of OCPUs for the MCP server container instance."
  type        = number
  default     = 1
}

variable "mcp_memory_in_gbs" {
  description = "Memory in GBs for the MCP server container instance."
  type        = number
  default     = 2
}

# ========================== Networking =========================================

variable "vcn_cidr_block" {
  description = "CIDR block for the Virtual Cloud Network."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vcn_cidr_block, 0))
    error_message = "vcn_cidr_block must be a valid CIDR block."
  }
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet (load balancer)."
  type        = string
  default     = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
  description = "CIDR block for the private subnet (container instances)."
  type        = string
  default     = "10.0.2.0/24"
}

# ========================== Load Balancer ======================================

variable "lb_shape" {
  description = "Load balancer shape: flexible or one of the fixed shapes."
  type        = string
  default     = "flexible"
}

variable "lb_min_bandwidth_mbps" {
  description = "Minimum bandwidth in Mbps for a flexible load balancer."
  type        = number
  default     = 10
}

variable "lb_max_bandwidth_mbps" {
  description = "Maximum bandwidth in Mbps for a flexible load balancer."
  type        = number
  default     = 100
}

variable "certificate_ids" {
  description = "List of OCI certificate OCIDs for HTTPS listener. Leave empty to skip HTTPS."
  type        = list(string)
  default     = []
}

variable "ssl_certificate_name" {
  description = "Display name for the SSL certificate bundle on the load balancer."
  type        = string
  default     = ""
}

# ========================== Health Check =======================================

variable "health_check_path" {
  description = "HTTP path for health checks."
  type        = string
  default     = "/health"
}

variable "health_check_interval_ms" {
  description = "Interval in milliseconds between health checks."
  type        = number
  default     = 10000
}

variable "health_check_timeout_ms" {
  description = "Timeout in milliseconds for each health check."
  type        = number
  default     = 3000
}

variable "health_check_retries" {
  description = "Number of retries before marking a backend unhealthy."
  type        = number
  default     = 3
}

# ========================== Application Config =================================

variable "app_env_vars" {
  description = "Additional environment variables to inject into the app container."
  type        = map(string)
  default     = {}
}

variable "mcp_env_vars" {
  description = "Additional environment variables to inject into the MCP server container."
  type        = map(string)
  default     = {}
}

variable "app_port" {
  description = "Port the FastAPI application listens on."
  type        = number
  default     = 8000
}

variable "mcp_port" {
  description = "Port the MCP server listens on."
  type        = number
  default     = 8001
}

# ========================== Tags ===============================================

variable "freeform_tags" {
  description = "Freeform tags applied to all resources."
  type        = map(string)
  default     = {}
}

variable "defined_tags" {
  description = "Defined tags applied to all resources. Requires tag namespaces to exist."
  type        = map(string)
  default     = {}
}

# ========================== Graceful Shutdown ===================================

variable "graceful_shutdown_timeout_seconds" {
  description = "Seconds to wait for a container to shut down gracefully before force-killing."
  type        = number
  default     = 30
}

# ========================== DNS (optional) ======================================

variable "dns_label_vcn" {
  description = "DNS label for the VCN. Must be unique within the tenancy."
  type        = string
  default     = "agentainet"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{0,14}$", var.dns_label_vcn))
    error_message = "dns_label_vcn must start with a letter, contain only lowercase alphanumerics, max 15 chars."
  }
}

variable "dns_label_public" {
  description = "DNS label for the public subnet."
  type        = string
  default     = "pub"
}

variable "dns_label_private" {
  description = "DNS label for the private subnet."
  type        = string
  default     = "priv"
}
