# =============================================================================
# Variables — Azure Container Apps Module
# =============================================================================
# All inputs are configurable with sensible defaults for the Agentic AI
# FastAPI application. Override per environment via .tfvars files.
# =============================================================================

# ---------------------------------------------------------------------------
# General / Resource Group
# ---------------------------------------------------------------------------

variable "resource_group_name" {
  description = "Name of the Azure Resource Group. Auto-generated if left empty."
  type        = string
  default     = ""
}

variable "location" {
  description = "Azure region for all resources (e.g. eastus, westeurope)."
  type        = string
  default     = "eastus"

  validation {
    condition     = can(regex("^[a-z]+[a-z0-9]*$", var.location))
    error_message = "Location must be a valid Azure region identifier (lowercase, no spaces)."
  }
}

variable "env" {
  description = "Deployment environment: dev, staging, or production."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "production"], var.env)
    error_message = "Environment must be one of: dev, staging, production."
  }
}

variable "project_name" {
  description = "Project identifier used in resource naming and tags."
  type        = string
  default     = "agentic-ai"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "Project name must be lowercase alphanumeric with hyphens, 2-21 chars."
  }
}

# ---------------------------------------------------------------------------
# Container App — Main API
# ---------------------------------------------------------------------------

variable "app_name" {
  description = "Name suffix for the main Container App (the FastAPI service)."
  type        = string
  default     = "api"
}

variable "image_tag" {
  description = "Docker image tag to deploy (e.g. latest, v1.2.3, sha-abc1234)."
  type        = string
  default     = "latest"
}

variable "app_port" {
  description = "Port the FastAPI application listens on."
  type        = number
  default     = 8000
}

variable "cpu" {
  description = "CPU cores allocated to the main API container (e.g. 0.5, 1, 2)."
  type        = number
  default     = 1.0

  validation {
    condition     = contains([0.25, 0.5, 1, 1.5, 2, 4], var.cpu)
    error_message = "CPU must be one of: 0.25, 0.5, 1, 1.5, 2, 4."
  }
}

variable "memory" {
  description = "Memory allocated to the main API container (e.g. 0.5Gi, 1Gi, 2Gi, 4Gi)."
  type        = string
  default     = "2Gi"

  validation {
    condition     = can(regex("^[0-9]+(\\.[0-9]+)?Gi$", var.memory))
    error_message = "Memory must be specified in Gi format (e.g. 2Gi, 4Gi)."
  }
}

variable "min_replicas" {
  description = "Minimum number of replicas for the main API (0 allows scale to zero)."
  type        = number
  default     = 1

  validation {
    condition     = var.min_replicas >= 0 && var.min_replicas <= 30
    error_message = "Minimum replicas must be between 0 and 30."
  }
}

variable "max_replicas" {
  description = "Maximum number of replicas for the main API under autoscaling."
  type        = number
  default     = 10

  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 300
    error_message = "Maximum replicas must be between 1 and 300."
  }
}

variable "concurrent_requests_threshold" {
  description = "Number of concurrent HTTP requests per replica before scaling out."
  type        = number
  default     = 50
}

# ---------------------------------------------------------------------------
# Container App — MCP Server
# ---------------------------------------------------------------------------

variable "mcp_image_tag" {
  description = "Docker image tag for the MCP server container."
  type        = string
  default     = "latest"
}

variable "mcp_port" {
  description = "Port the MCP server listens on."
  type        = number
  default     = 8001
}

variable "mcp_cpu" {
  description = "CPU cores allocated to the MCP server container."
  type        = number
  default     = 0.5
}

variable "mcp_memory" {
  description = "Memory allocated to the MCP server container."
  type        = string
  default     = "1Gi"
}

variable "mcp_min_replicas" {
  description = "Minimum replicas for the MCP server."
  type        = number
  default     = 1
}

variable "mcp_max_replicas" {
  description = "Maximum replicas for the MCP server."
  type        = number
  default     = 5
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

variable "vnet_address_space" {
  description = "Address space for the virtual network."
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "container_apps_subnet_prefix" {
  description = "CIDR prefix for the Container Apps Environment subnet. Must be /21 or larger."
  type        = string
  default     = "10.0.0.0/21"
}

# ---------------------------------------------------------------------------
# Secrets / Environment Variables
# ---------------------------------------------------------------------------

variable "app_secrets" {
  description = "Map of secret name to value, injected as Container App secrets and environment variables."
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "app_env_vars" {
  description = "Map of non-secret environment variables for the main API container."
  type        = map(string)
  default     = {}
}

# ---------------------------------------------------------------------------
# Log Analytics
# ---------------------------------------------------------------------------

variable "log_retention_days" {
  description = "Number of days to retain logs in the Log Analytics workspace."
  type        = number
  default     = 30

  validation {
    condition     = var.log_retention_days >= 7 && var.log_retention_days <= 730
    error_message = "Log retention must be between 7 and 730 days."
  }
}

# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

variable "extra_tags" {
  description = "Additional tags to apply to all resources."
  type        = map(string)
  default     = {}
}
