# =============================================================================
# Outputs — Azure Container Apps Module
# =============================================================================
# Exposes key attributes for downstream consumption (CI/CD pipelines,
# other Terraform modules, monitoring dashboards, etc.).
# =============================================================================

# ---------------------------------------------------------------------------
# Resource Group
# ---------------------------------------------------------------------------

output "resource_group_name" {
  description = "Name of the Azure Resource Group containing all deployed resources."
  value       = azurerm_resource_group.this.name
}

output "resource_group_id" {
  description = "Resource ID of the Azure Resource Group."
  value       = azurerm_resource_group.this.id
}

# ---------------------------------------------------------------------------
# Container Registry
# ---------------------------------------------------------------------------

output "acr_login_server" {
  description = "Login server URL for the Azure Container Registry (e.g. acragenticaidev.azurecr.io)."
  value       = azurerm_container_registry.acr.login_server
}

output "acr_admin_username" {
  description = "Admin username for the Azure Container Registry."
  value       = azurerm_container_registry.acr.admin_username
  sensitive   = true
}

output "acr_admin_password" {
  description = "Admin password for the Azure Container Registry."
  value       = azurerm_container_registry.acr.admin_password
  sensitive   = true
}

# ---------------------------------------------------------------------------
# Container Apps — Main API
# ---------------------------------------------------------------------------

output "api_fqdn" {
  description = "Fully qualified domain name of the main API Container App (external HTTPS)."
  value       = azurerm_container_app.api.ingress[0].fqdn
}

output "api_url" {
  description = "Full HTTPS URL for the main API (convenience output)."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "api_container_app_id" {
  description = "Resource ID of the main API Container App."
  value       = azurerm_container_app.api.id
}

output "api_latest_revision_name" {
  description = "Name of the latest deployed revision of the main API."
  value       = azurerm_container_app.api.latest_revision_name
}

# ---------------------------------------------------------------------------
# Container Apps — MCP Server
# ---------------------------------------------------------------------------

output "mcp_fqdn" {
  description = "Internal FQDN of the MCP server Container App (not externally accessible)."
  value       = azurerm_container_app.mcp.ingress[0].fqdn
}

output "mcp_container_app_id" {
  description = "Resource ID of the MCP server Container App."
  value       = azurerm_container_app.mcp.id
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------

output "vnet_id" {
  description = "Resource ID of the Virtual Network."
  value       = azurerm_virtual_network.vnet.id
}

output "container_apps_subnet_id" {
  description = "Resource ID of the Container Apps subnet."
  value       = azurerm_subnet.container_apps.id
}

output "container_apps_environment_id" {
  description = "Resource ID of the Container Apps Environment."
  value       = azurerm_container_app_environment.env.id
}

output "container_apps_default_domain" {
  description = "Default domain of the Container Apps Environment."
  value       = azurerm_container_app_environment.env.default_domain
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------

output "log_analytics_workspace_id" {
  description = "Resource ID of the Log Analytics workspace."
  value       = azurerm_log_analytics_workspace.logs.id
}

output "log_analytics_workspace_name" {
  description = "Name of the Log Analytics workspace for querying logs."
  value       = azurerm_log_analytics_workspace.logs.name
}
