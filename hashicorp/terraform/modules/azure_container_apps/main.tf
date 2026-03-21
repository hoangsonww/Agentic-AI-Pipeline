# =============================================================================
# Main Infrastructure — Azure Container Apps Module
# =============================================================================
# Deploys the Agentic AI FastAPI application and MCP server to Azure Container
# Apps with full networking, observability, security, and autoscaling.
#
# Architecture:
#   Resource Group
#   +-- Azure Container Registry (ACR)
#   +-- Virtual Network
#   |     +-- Container Apps Subnet (/21)
#   +-- Log Analytics Workspace
#   +-- Container Apps Environment (VNet-integrated)
#   |     +-- Container App: Main API   (external HTTPS, port 8000)
#   |     +-- Container App: MCP Server (internal only, port 8001)
#   +-- Management Lock (production only)
# =============================================================================

# ---------------------------------------------------------------------------
# Locals — Naming conventions, tags, computed values
# ---------------------------------------------------------------------------

locals {
  # Consistent naming: {project}-{component}-{env}
  name_prefix = "${var.project_name}-${var.env}"

  # Resource group name: use provided or generate
  resource_group_name = var.resource_group_name != "" ? var.resource_group_name : "rg-${local.name_prefix}"

  # ACR names must be globally unique, alphanumeric only, 5-50 chars
  acr_name = replace("acr${var.project_name}${var.env}", "-", "")

  # Standard tags applied to every resource
  common_tags = merge(
    {
      environment = var.env
      project     = var.project_name
      managed-by  = "terraform"
      module      = "azure-container-apps"
    },
    var.extra_tags,
  )
}

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "this" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

# ---------------------------------------------------------------------------
# Management Lock — Prevent accidental deletion in production
# ---------------------------------------------------------------------------

resource "azurerm_management_lock" "rg_lock" {
  count = var.env == "production" ? 1 : 0

  name       = "lock-${local.name_prefix}-nodelete"
  scope      = azurerm_resource_group.this.id
  lock_level = "CanNotDelete"
  notes      = "Production resource group is protected from accidental deletion."
}

# =============================================================================
# Container Registry (ACR)
# =============================================================================

resource "azurerm_container_registry" "acr" {
  name                = local.acr_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = var.env == "production" ? "Premium" : "Basic"
  admin_enabled       = true

  # Disable anonymous pulls for security
  anonymous_pull_enabled     = false
  network_rule_bypass_option = "AzureServices"

  # Premium-only features conditionally enabled for production
  dynamic "retention_policy" {
    for_each = var.env == "production" ? [1] : []
    content {
      enabled = true
      days    = 30
    }
  }

  tags = local.common_tags
}

# =============================================================================
# Networking — VNet + Subnet for Container Apps Environment
# =============================================================================

resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  address_space       = var.vnet_address_space
  tags                = local.common_tags
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-container-apps"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = [var.container_apps_subnet_prefix]

  # Delegate the subnet to Microsoft.App/environments for Container Apps
  delegation {
    name = "container-apps-delegation"
    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

# Network Security Group — restrict inbound traffic to HTTPS only
resource "azurerm_network_security_group" "container_apps" {
  name                = "nsg-${local.name_prefix}-cae"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tags                = local.common_tags

  security_rule {
    name                       = "AllowHTTPS"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "DenyAllInbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_subnet_network_security_group_association" "container_apps" {
  subnet_id                 = azurerm_subnet.container_apps.id
  network_security_group_id = azurerm_network_security_group.container_apps.id
}

# =============================================================================
# Observability — Log Analytics Workspace
# =============================================================================

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "log-${local.name_prefix}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_days
  tags                = local.common_tags
}

# =============================================================================
# Container Apps Environment
# =============================================================================

resource "azurerm_container_app_environment" "env" {
  name                       = "cae-${local.name_prefix}"
  resource_group_name        = azurerm_resource_group.this.name
  location                   = azurerm_resource_group.this.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id

  # VNet integration for network isolation
  infrastructure_subnet_id = azurerm_subnet.container_apps.id

  # Workload profiles: Consumption plan (serverless, pay-per-use)
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    minimum_count         = 0
    maximum_count         = 0
  }

  tags = local.common_tags
}

# =============================================================================
# Container App — Main API (FastAPI on port 8000)
# =============================================================================
# External-facing HTTPS ingress with autoscaling based on HTTP concurrency.
# Health probes on /health for both liveness and readiness.
# =============================================================================

resource "azurerm_container_app" "api" {
  name                         = "ca-${local.name_prefix}-${var.app_name}"
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"
  tags                         = local.common_tags

  # -------------------------------------------------------------------------
  # Secrets — injected from var.app_secrets
  # -------------------------------------------------------------------------
  dynamic "secret" {
    for_each = var.app_secrets
    content {
      name  = lower(replace(secret.key, "_", "-"))
      value = secret.value
    }
  }

  # -------------------------------------------------------------------------
  # Container template
  # -------------------------------------------------------------------------
  template {
    # Min/max replicas for autoscaling
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "api"
      image  = "${azurerm_container_registry.acr.login_server}/${var.project_name}-${var.app_name}:${var.image_tag}"
      cpu    = var.cpu
      memory = var.memory

      # -------------------------------------------------------------------
      # Environment variables — non-secret
      # -------------------------------------------------------------------
      env {
        name  = "APP_HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "APP_PORT"
        value = tostring(var.app_port)
      }

      env {
        name  = "APP_ENV"
        value = var.env
      }

      # MCP server endpoint for inter-service communication
      env {
        name  = "MCP_SERVER_URL"
        value = "https://ca-${local.name_prefix}-mcp.internal.${azurerm_container_app_environment.env.default_domain}"
      }

      # Additional non-secret env vars
      dynamic "env" {
        for_each = var.app_env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secret-backed environment variables
      dynamic "env" {
        for_each = var.app_secrets
        content {
          name       = env.key
          secret_name = lower(replace(env.key, "_", "-"))
        }
      }

      # -------------------------------------------------------------------
      # Liveness probe — restarts unhealthy containers
      # -------------------------------------------------------------------
      liveness_probe {
        transport               = "HTTP"
        port                    = var.app_port
        path                    = "/health"
        initial_delay           = 10
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      # -------------------------------------------------------------------
      # Readiness probe — gates traffic until container is ready
      # -------------------------------------------------------------------
      readiness_probe {
        transport               = "HTTP"
        port                    = var.app_port
        path                    = "/health"
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
        success_count_threshold = 1
      }

      # -------------------------------------------------------------------
      # Startup probe — allows slow-starting containers extra time
      # -------------------------------------------------------------------
      startup_probe {
        transport               = "HTTP"
        port                    = var.app_port
        path                    = "/health"
        interval_seconds        = 5
        timeout                 = 3
        failure_count_threshold = 30
      }
    }

    # ---------------------------------------------------------------------
    # Autoscaling — HTTP concurrent requests
    # ---------------------------------------------------------------------
    http_scale_rule {
      name                = "http-concurrency"
      concurrent_requests = tostring(var.concurrent_requests_threshold)
    }
  }

  # -------------------------------------------------------------------------
  # Ingress — External HTTPS on the application port
  # -------------------------------------------------------------------------
  ingress {
    external_enabled = true
    target_port      = var.app_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # -------------------------------------------------------------------------
  # Registry — Pull images from our ACR
  # -------------------------------------------------------------------------
  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  # ACR admin password as a container app secret
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }

  depends_on = [
    azurerm_container_app_environment.env,
    azurerm_container_registry.acr,
  ]
}

# =============================================================================
# Container App — MCP Server (port 8001, internal only)
# =============================================================================
# Internal-only service accessible within the Container Apps Environment.
# The main API communicates with MCP over the internal domain.
# =============================================================================

resource "azurerm_container_app" "mcp" {
  name                         = "ca-${local.name_prefix}-mcp"
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  revision_mode                = "Single"
  tags                         = local.common_tags

  # -------------------------------------------------------------------------
  # Container template
  # -------------------------------------------------------------------------
  template {
    min_replicas = var.mcp_min_replicas
    max_replicas = var.mcp_max_replicas

    container {
      name   = "mcp"
      image  = "${azurerm_container_registry.acr.login_server}/${var.project_name}-mcp:${var.mcp_image_tag}"
      cpu    = var.mcp_cpu
      memory = var.mcp_memory

      env {
        name  = "MCP_HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "MCP_PORT"
        value = tostring(var.mcp_port)
      }

      env {
        name  = "APP_ENV"
        value = var.env
      }

      # Secret-backed environment variables (shared secrets)
      dynamic "env" {
        for_each = var.app_secrets
        content {
          name       = env.key
          secret_name = lower(replace(env.key, "_", "-"))
        }
      }

      # -------------------------------------------------------------------
      # Liveness probe
      # -------------------------------------------------------------------
      liveness_probe {
        transport               = "HTTP"
        port                    = var.mcp_port
        path                    = "/health"
        initial_delay           = 10
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      # -------------------------------------------------------------------
      # Readiness probe
      # -------------------------------------------------------------------
      readiness_probe {
        transport               = "HTTP"
        port                    = var.mcp_port
        path                    = "/health"
        interval_seconds        = 10
        timeout                 = 3
        failure_count_threshold = 3
        success_count_threshold = 1
      }
    }

    # Autoscaling for MCP server
    http_scale_rule {
      name                = "mcp-http-concurrency"
      concurrent_requests = "25"
    }
  }

  # -------------------------------------------------------------------------
  # Ingress — Internal only, not exposed to the public internet
  # -------------------------------------------------------------------------
  ingress {
    external_enabled = false
    target_port      = var.mcp_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  # -------------------------------------------------------------------------
  # Registry — Pull images from our ACR
  # -------------------------------------------------------------------------
  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }

  # Secrets
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }

  dynamic "secret" {
    for_each = var.app_secrets
    content {
      name  = lower(replace(secret.key, "_", "-"))
      value = secret.value
    }
  }

  depends_on = [
    azurerm_container_app_environment.env,
    azurerm_container_registry.acr,
  ]
}
