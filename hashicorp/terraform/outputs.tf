# =============================================================================
# Outputs — Multi-Provider
# =============================================================================

output "cloud_provider" {
  value       = var.cloud_provider
  description = "Active cloud provider"
}

# --- AWS ---
output "aws_alb_dns" {
  value       = var.cloud_provider == "aws" ? module.aws[0].alb_dns_name : null
  description = "AWS ALB DNS name"
}

output "aws_ecr_url" {
  value       = var.cloud_provider == "aws" ? module.aws[0].repository_url : null
  description = "AWS ECR repository URL"
}

# --- GCP ---
output "gcp_service_url" {
  value       = var.cloud_provider == "gcp" ? module.gcp[0].service_url : null
  description = "GCP Cloud Run service URL"
}

output "gcp_registry_url" {
  value       = var.cloud_provider == "gcp" ? module.gcp[0].artifact_registry_url : null
  description = "GCP Artifact Registry URL"
}

# --- Azure ---
output "azure_app_fqdn" {
  value       = var.cloud_provider == "azure" ? module.azure[0].app_fqdn : null
  description = "Azure Container App FQDN"
}

output "azure_acr_server" {
  value       = var.cloud_provider == "azure" ? module.azure[0].acr_login_server : null
  description = "Azure Container Registry login server"
}

# --- OCI ---
output "oci_lb_ip" {
  value       = var.cloud_provider == "oci" ? module.oci[0].load_balancer_ip : null
  description = "OCI Load Balancer public IP"
}

output "oci_registry" {
  value       = var.cloud_provider == "oci" ? module.oci[0].ocir_repository : null
  description = "OCI Container Registry path"
}
