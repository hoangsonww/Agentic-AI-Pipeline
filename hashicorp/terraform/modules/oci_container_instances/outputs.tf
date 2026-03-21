# ------------------------------------------------------------------------------
# OCI Container Instances Module - Outputs
# ------------------------------------------------------------------------------
# Exposes resource identifiers, endpoints, and metadata needed by callers,
# CI/CD pipelines, and downstream modules.
# ------------------------------------------------------------------------------

# ========================== Load Balancer ======================================

output "load_balancer_id" {
  description = "OCID of the OCI Load Balancer."
  value       = oci_load_balancer_load_balancer.this.id
}

output "load_balancer_public_ip" {
  description = "Public IP address of the load balancer."
  value       = oci_load_balancer_load_balancer.this.ip_address_details[0].ip_address
}

output "load_balancer_display_name" {
  description = "Display name of the load balancer."
  value       = oci_load_balancer_load_balancer.this.display_name
}

output "app_url" {
  description = "HTTP URL to reach the Agentic AI application via the load balancer."
  value       = "http://${oci_load_balancer_load_balancer.this.ip_address_details[0].ip_address}"
}

output "health_check_url" {
  description = "Full URL of the health check endpoint through the load balancer."
  value       = "http://${oci_load_balancer_load_balancer.this.ip_address_details[0].ip_address}${var.health_check_path}"
}

# ========================== OCIR Repositories ==================================

output "ocir_app_repo_path" {
  description = "Full OCIR path for the app repository (use for docker push)."
  value       = "${var.region}.ocir.io/${local.ocir_namespace}/${oci_artifacts_container_repository.app.display_name}"
}

output "ocir_mcp_repo_path" {
  description = "Full OCIR path for the MCP server repository (use for docker push)."
  value       = "${var.region}.ocir.io/${local.ocir_namespace}/${oci_artifacts_container_repository.mcp.display_name}"
}

output "ocir_app_repo_id" {
  description = "OCID of the app container image repository."
  value       = oci_artifacts_container_repository.app.id
}

output "ocir_mcp_repo_id" {
  description = "OCID of the MCP server container image repository."
  value       = oci_artifacts_container_repository.mcp.id
}

# ========================== Container Instances ================================

output "app_container_instance_id" {
  description = "OCID of the app container instance."
  value       = oci_container_instances_container_instance.app.id
}

output "mcp_container_instance_id" {
  description = "OCID of the MCP server container instance."
  value       = oci_container_instances_container_instance.mcp.id
}

output "app_container_instance_state" {
  description = "Current lifecycle state of the app container instance."
  value       = oci_container_instances_container_instance.app.state
}

output "mcp_container_instance_state" {
  description = "Current lifecycle state of the MCP server container instance."
  value       = oci_container_instances_container_instance.mcp.state
}

output "app_private_ip" {
  description = "Private IP of the app container instance VNIC."
  value       = oci_container_instances_container_instance.app.vnics[0].private_ip
}

output "mcp_private_ip" {
  description = "Private IP of the MCP server container instance VNIC."
  value       = oci_container_instances_container_instance.mcp.vnics[0].private_ip
}

# ========================== Networking =========================================

output "vcn_id" {
  description = "OCID of the Virtual Cloud Network."
  value       = oci_core_vcn.this.id
}

output "public_subnet_id" {
  description = "OCID of the public subnet (load balancer)."
  value       = oci_core_subnet.public.id
}

output "private_subnet_id" {
  description = "OCID of the private subnet (container instances)."
  value       = oci_core_subnet.private.id
}

output "nsg_id" {
  description = "OCID of the Network Security Group attached to container instances."
  value       = oci_core_network_security_group.container.id
}

output "internet_gateway_id" {
  description = "OCID of the Internet Gateway."
  value       = oci_core_internet_gateway.this.id
}

output "nat_gateway_id" {
  description = "OCID of the NAT Gateway."
  value       = oci_core_nat_gateway.this.id
}

# ========================== Computed Metadata ===================================

output "app_image_url" {
  description = "Full OCIR image URL used by the app container instance."
  value       = local.app_image_url
}

output "mcp_image_url" {
  description = "Full OCIR image URL used by the MCP server container instance."
  value       = local.mcp_image_url
}

output "resource_summary" {
  description = "Human-readable summary of deployed resources for CI/CD logging."
  value = {
    environment     = var.env
    region          = var.region
    lb_ip           = oci_load_balancer_load_balancer.this.ip_address_details[0].ip_address
    app_instance_id = oci_container_instances_container_instance.app.id
    mcp_instance_id = oci_container_instances_container_instance.mcp.id
    app_image       = local.app_image_url
    mcp_image       = local.mcp_image_url
    vcn_id          = oci_core_vcn.this.id
  }
}
