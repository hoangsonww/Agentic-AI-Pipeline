# =============================================================================
# Outputs — GCP Cloud Run Module
# =============================================================================
# These outputs expose the key resource identifiers and URLs needed by
# downstream consumers: CI/CD pipelines, monitoring dashboards, DNS
# configuration, and root-module composition.
# =============================================================================

# ---------------------------------------------------------------------------
# Cloud Run Service
# ---------------------------------------------------------------------------
output "service_url" {
  description = "The default HTTPS URL of the Cloud Run service (*.run.app)."
  value       = google_cloud_run_v2_service.app.uri
}

output "service_name" {
  description = "The name of the Cloud Run service."
  value       = google_cloud_run_v2_service.app.name
}

output "service_id" {
  description = "The fully-qualified resource ID of the Cloud Run service."
  value       = google_cloud_run_v2_service.app.id
}

output "latest_revision" {
  description = "The name of the latest ready revision."
  value       = google_cloud_run_v2_service.app.latest_ready_revision
}

output "service_location" {
  description = "The GCP region where the Cloud Run service is deployed."
  value       = google_cloud_run_v2_service.app.location
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------
output "artifact_registry_url" {
  description = "The full URL of the Artifact Registry Docker repository. Use this as the image registry in CI/CD."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "artifact_registry_repository_id" {
  description = "The repository ID of the Artifact Registry."
  value       = google_artifact_registry_repository.repo.repository_id
}

output "image_uri" {
  description = "The full image URI currently deployed (registry + tag)."
  value       = local.image_uri
}

# ---------------------------------------------------------------------------
# Service Account
# ---------------------------------------------------------------------------
output "service_account_email" {
  description = "The email address of the Cloud Run service account."
  value       = google_service_account.cloud_run_sa.email
}

output "service_account_id" {
  description = "The fully-qualified resource ID of the service account."
  value       = google_service_account.cloud_run_sa.id
}

# ---------------------------------------------------------------------------
# Load Balancer
# ---------------------------------------------------------------------------
output "load_balancer_ip" {
  description = "The global IP address of the HTTPS load balancer. Point your domain's A record here."
  value       = var.domain_name != "" ? google_compute_global_forwarding_rule.https[0].ip_address : null
}

output "load_balancer_url" {
  description = "The HTTPS URL via the load balancer (null if no domain is configured)."
  value       = var.domain_name != "" ? "https://${var.domain_name}" : null
}

# ---------------------------------------------------------------------------
# Cloud SQL (conditional)
# ---------------------------------------------------------------------------
output "cloud_sql_instance_name" {
  description = "The name of the Cloud SQL PostgreSQL instance (null if Cloud SQL is disabled)."
  value       = var.enable_cloud_sql ? google_sql_database_instance.postgres[0].name : null
}

output "cloud_sql_connection_name" {
  description = "The connection name for Cloud SQL Auth Proxy (project:region:instance)."
  value       = var.enable_cloud_sql ? google_sql_database_instance.postgres[0].connection_name : null
}

output "cloud_sql_private_ip" {
  description = "The private IP address of the Cloud SQL instance (null if Cloud SQL is disabled)."
  value       = var.enable_cloud_sql ? google_sql_database_instance.postgres[0].private_ip_address : null
}

output "database_name" {
  description = "The name of the PostgreSQL database created inside the Cloud SQL instance."
  value       = var.enable_cloud_sql ? google_sql_database.app_db[0].name : null
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
output "vpc_id" {
  description = "The ID of the VPC network (null if VPC connector is disabled)."
  value       = var.enable_vpc_connector ? google_compute_network.vpc[0].id : null
}

output "vpc_connector_id" {
  description = "The ID of the Serverless VPC Access connector (null if disabled)."
  value       = var.enable_vpc_connector ? google_vpc_access_connector.connector[0].id : null
}

# ---------------------------------------------------------------------------
# Convenience — CI/CD integration
# ---------------------------------------------------------------------------
output "docker_push_command" {
  description = "Example command to push a Docker image to this module's Artifact Registry."
  value       = "docker push ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.service_name}:YOUR_TAG"
}

output "gcloud_deploy_command" {
  description = "Example gcloud command to deploy a new revision to the Cloud Run service."
  value       = "gcloud run deploy ${google_cloud_run_v2_service.app.name} --image=${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.service_name}:YOUR_TAG --region=${var.region}"
}
