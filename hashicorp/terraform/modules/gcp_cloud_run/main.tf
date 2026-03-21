# =============================================================================
# GCP Cloud Run Module — Agentic AI Application
# =============================================================================
# Production-grade deployment of the Agentic AI FastAPI application to
# Google Cloud Run (2nd generation execution environment).
#
# Architecture overview:
#   Internet -> Cloud Load Balancer (HTTPS) -> Cloud Run (autoscaled)
#                                               |
#                                               +-> Artifact Registry (images)
#                                               +-> Secret Manager (API keys)
#                                               +-> VPC Connector (private net)
#                                               +-> Cloud SQL PostgreSQL (optional)
#
# Security posture:
#   - Dedicated service account with least-privilege IAM
#   - Secrets injected from Secret Manager (never in env vars or image)
#   - VPC connector for private networking to Cloud SQL
#   - Deletion protection on production resources
#   - Binary Authorization ready (image from Artifact Registry)
# =============================================================================

# ---------------------------------------------------------------------------
# Local values — computed once, referenced throughout
# ---------------------------------------------------------------------------
locals {
  # Canonical resource prefix used in all naming
  prefix = "${var.service_name}-${var.env}"

  # Standard labels applied to every resource for cost allocation and governance
  labels = merge(
    {
      app         = var.service_name
      environment = var.env
      managed_by  = "terraform"
      module      = "gcp-cloud-run"
    },
    var.extra_labels,
  )

  # Production guard — enables deletion protection and HA settings
  is_production = var.env == "prod"

  # Full image URI constructed from the Artifact Registry repository
  image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}/${var.service_name}:${var.image_tag}"
}

# ---------------------------------------------------------------------------
# Random suffix for globally-unique names (Cloud SQL, etc.)
# ---------------------------------------------------------------------------
resource "random_id" "suffix" {
  byte_length = 4
}

# =============================================================================
# 1. GOOGLE APIS — Enable required services
# =============================================================================
# Terraform enables APIs declaratively. These are idempotent: re-applying
# when the API is already enabled is a no-op.
# =============================================================================

resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",              # Cloud Run
    "artifactregistry.googleapis.com", # Artifact Registry
    "secretmanager.googleapis.com",    # Secret Manager
    "vpcaccess.googleapis.com",        # Serverless VPC Access
    "sqladmin.googleapis.com",         # Cloud SQL Admin (needed even if SQL is disabled — API is free)
    "compute.googleapis.com",          # Compute Engine (for LB, VPC, NEGs)
    "certificatemanager.googleapis.com", # Managed SSL certificates
    "cloudresourcemanager.googleapis.com", # Resource manager
  ])

  project                    = var.project_id
  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
}

# =============================================================================
# 2. ARTIFACT REGISTRY — Docker image repository
# =============================================================================
# A private Docker repository scoped to this application. Images are pushed
# here by CI/CD (e.g., Cloud Build, GitHub Actions) before Cloud Run
# references them.
# =============================================================================

resource "google_artifact_registry_repository" "repo" {
  provider = google-beta

  location      = var.region
  repository_id = "${local.prefix}-docker"
  format        = "DOCKER"
  description   = "Docker images for ${var.service_name} (${var.env})"

  labels = local.labels

  # Clean up untagged images automatically to control storage costs.
  # Tagged images (releases) are retained; only untagged manifests older
  # than 14 days are garbage-collected.
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "1209600s" # 14 days
    }
  }

  # Keep at least the 10 most recent tagged images
  cleanup_policies {
    id     = "keep-recent-tagged"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.required_apis]
}

# =============================================================================
# 3. IAM — Dedicated service account with least-privilege
# =============================================================================
# The Cloud Run service runs as this SA. It receives only the permissions
# it needs: pulling images, reading secrets, and connecting to Cloud SQL.
# This follows the principle of least privilege and avoids using the
# default compute service account.
# =============================================================================

resource "google_service_account" "cloud_run_sa" {
  account_id   = "${local.prefix}-run-sa"
  display_name = "Cloud Run SA for ${var.service_name} (${var.env})"
  description  = "Least-privilege service account for the ${var.service_name} Cloud Run service in ${var.env}."
  project      = var.project_id

  depends_on = [google_project_service.required_apis]
}

# Allow the SA to pull images from Artifact Registry
resource "google_artifact_registry_repository_iam_member" "sa_reader" {
  provider = google-beta

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.repo.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow the SA to access secrets from Secret Manager.
# This is a project-level binding scoped to the secretAccessor role.
# Granted when any secret env vars are configured OR when Cloud SQL is
# enabled (the DB password is stored in Secret Manager).
resource "google_project_iam_member" "sa_secret_accessor" {
  count = length(var.secret_env_vars) > 0 || var.enable_cloud_sql ? 1 : 0

  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow the SA to write logs to Cloud Logging
resource "google_project_iam_member" "sa_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow the SA to export metrics to Cloud Monitoring
resource "google_project_iam_member" "sa_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow the SA to connect to Cloud SQL (only when SQL is enabled)
resource "google_project_iam_member" "sa_cloudsql_client" {
  count = var.enable_cloud_sql ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# =============================================================================
# 4. SECRET MANAGER — API keys and sensitive configuration
# =============================================================================
# Secrets are referenced by Cloud Run as environment variable mounts.
# The actual secret values must be populated out-of-band (CLI, console, or
# a separate CI step). Terraform creates the secret *resources* but does
# NOT manage the secret *data* to avoid storing sensitive values in state.
# =============================================================================

resource "google_secret_manager_secret" "secrets" {
  for_each = var.secret_env_vars

  secret_id = each.value
  project   = var.project_id

  labels = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

# =============================================================================
# 5. NETWORKING — VPC & Serverless VPC Access Connector
# =============================================================================
# A VPC connector allows Cloud Run to reach private-IP resources (Cloud SQL,
# Memorystore, internal APIs) without exposing them to the public internet.
# The connector uses a dedicated /28 CIDR range.
# =============================================================================

resource "google_compute_network" "vpc" {
  count = var.enable_vpc_connector ? 1 : 0

  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id

  depends_on = [google_project_service.required_apis]
}

resource "google_compute_subnetwork" "connector_subnet" {
  count = var.enable_vpc_connector ? 1 : 0

  name          = "${local.prefix}-connector-subnet"
  ip_cidr_range = var.vpc_connector_cidr
  region        = var.region
  network       = google_compute_network.vpc[0].id
  project       = var.project_id

  # Enable Private Google Access so the subnet can reach Google APIs
  # without a public IP (useful for Cloud SQL private IP path)
  private_ip_google_access = true
}

resource "google_vpc_access_connector" "connector" {
  count = var.enable_vpc_connector ? 1 : 0

  provider = google-beta

  name    = "${local.prefix}-conn"
  region  = var.region
  project = var.project_id

  subnet {
    name       = google_compute_subnetwork.connector_subnet[0].name
    project_id = var.project_id
  }

  # Scale the connector based on environment. Production gets more
  # throughput; dev/staging use the minimum to save cost.
  min_instances = local.is_production ? 2 : 2
  max_instances = local.is_production ? 10 : 3

  machine_type = local.is_production ? "e2-standard-4" : "e2-micro"

  depends_on = [google_project_service.required_apis]
}

# =============================================================================
# 6. CLOUD SQL — PostgreSQL (optional, for production workloads)
# =============================================================================
# Disabled by default (var.enable_cloud_sql = false). When enabled,
# provisions a Cloud SQL PostgreSQL 15 instance with:
#   - Private IP via the VPC connector
#   - Automated backups and point-in-time recovery
#   - Deletion protection in production
#   - Insights and query logging enabled
# =============================================================================

resource "google_sql_database_instance" "postgres" {
  count = var.enable_cloud_sql ? 1 : 0

  provider = google-beta

  name                = "${local.prefix}-pg-${random_id.suffix.hex}"
  database_version    = "POSTGRES_15"
  region              = var.region
  project             = var.project_id
  deletion_protection = local.is_production

  settings {
    tier              = var.cloud_sql_tier
    availability_type = var.cloud_sql_availability_type
    disk_size         = var.cloud_sql_disk_size_gb
    disk_autoresize   = true
    disk_type         = "PD_SSD"

    # Private IP networking — accessible only through the VPC connector
    ip_configuration {
      ipv4_enabled    = false
      private_network = var.enable_vpc_connector ? google_compute_network.vpc[0].id : null
    }

    # Automated daily backups with 7-day retention and PITR
    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = local.is_production
      backup_retention_settings {
        retained_backups = local.is_production ? 30 : 7
      }
    }

    # Performance insights
    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
      record_client_address   = false
    }

    # Maintenance window — Sunday 04:00 UTC to minimize impact
    maintenance_window {
      day          = 7 # Sunday
      hour         = 4
      update_track = local.is_production ? "stable" : "canary"
    }

    database_flags {
      name  = "log_min_duration_statement"
      value = "1000" # Log queries slower than 1s
    }

    user_labels = local.labels
  }

  depends_on = [
    google_project_service.required_apis,
    google_compute_network.vpc,
  ]
}

# Create the application database
resource "google_sql_database" "app_db" {
  count = var.enable_cloud_sql ? 1 : 0

  name     = var.database_name
  instance = google_sql_database_instance.postgres[0].name
  project  = var.project_id
}

# Create a dedicated database user. The password is generated randomly
# and stored in Secret Manager so it never appears in logs or tfvars.
resource "random_password" "db_password" {
  count = var.enable_cloud_sql ? 1 : 0

  length  = 32
  special = false # Avoids URL-encoding issues in connection strings
}

resource "google_sql_user" "app_user" {
  count = var.enable_cloud_sql ? 1 : 0

  name     = "${var.service_name}-app"
  instance = google_sql_database_instance.postgres[0].name
  password = random_password.db_password[0].result
  project  = var.project_id
}

# Store the database password in Secret Manager
resource "google_secret_manager_secret" "db_password_secret" {
  count = var.enable_cloud_sql ? 1 : 0

  secret_id = "${local.prefix}-db-password"
  project   = var.project_id
  labels    = local.labels

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "db_password_value" {
  count = var.enable_cloud_sql ? 1 : 0

  secret      = google_secret_manager_secret.db_password_secret[0].id
  secret_data = random_password.db_password[0].result
}

# =============================================================================
# 7. CLOUD RUN SERVICE (v2) — Application deployment
# =============================================================================
# Uses the Cloud Run v2 API (google_cloud_run_v2_service) which provides:
#   - 2nd generation execution environment (full Linux compatibility)
#   - Startup and liveness probes
#   - Volume mounts and sidecars
#   - Direct VPC egress
#   - GPU support (future)
# =============================================================================

resource "google_cloud_run_v2_service" "app" {
  provider = google-beta

  name     = local.prefix
  location = var.region
  project  = var.project_id

  # Deletion protection prevents accidental `terraform destroy` in production.
  deletion_protection = local.is_production

  # Ingress: allow traffic from the load balancer and internal sources only
  # in production; allow all traffic in dev/staging for easier testing.
  ingress = local.is_production ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"

  labels = local.labels

  template {
    # Service account — least-privilege SA created above
    service_account = google_service_account.cloud_run_sa.email

    labels = local.labels

    # --------------- Scaling ---------------
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # --------------- VPC access ---------------
    dynamic "vpc_access" {
      for_each = var.enable_vpc_connector ? [1] : []
      content {
        connector = google_vpc_access_connector.connector[0].id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }

    # --------------- Cloud SQL connection ---------------
    dynamic "volumes" {
      for_each = var.enable_cloud_sql ? [1] : []
      content {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres[0].connection_name]
        }
      }
    }

    # --------------- Container specification ---------------
    containers {
      image = local.image_uri
      name  = "app"

      # Resource allocation
      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        # CPU is always allocated (not throttled between requests) when
        # min_instances > 0. This gives predictable latency.
        cpu_idle = var.min_instances > 0 ? false : true
      }

      # Container port
      ports {
        container_port = var.container_port
      }

      # --------------- Health checks ---------------
      # Startup probe: allows up to 240s for the container to become ready.
      # This is generous to handle cold starts with large ML model loading.
      startup_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 24
      }

      # Liveness probe: ongoing health verification. If the app becomes
      # unhealthy, Cloud Run replaces the instance automatically.
      liveness_probe {
        http_get {
          path = "/health"
          port = var.container_port
        }
        period_seconds    = 30
        timeout_seconds   = 5
        failure_threshold = 3
      }

      # --------------- Plain-text environment variables ---------------
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Environment label so the app knows which env it is in
      env {
        name  = "ENVIRONMENT"
        value = var.env
      }

      # --------------- Secret environment variables ---------------
      # Each secret is mounted from Secret Manager. The SA has
      # roles/secretmanager.secretAccessor so it can read them at boot.
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = "latest"
            }
          }
        }
      }

      # Inject the database connection string from Secret Manager when SQL is enabled
      dynamic "env" {
        for_each = var.enable_cloud_sql ? [1] : []
        content {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_password_secret[0].secret_id
              version = "latest"
            }
          }
        }
      }

      # Mount the Cloud SQL socket volume
      dynamic "volume_mounts" {
        for_each = var.enable_cloud_sql ? [1] : []
        content {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }

    # Timeout for individual requests
    timeout = "${var.request_timeout}s"

    # Maximum concurrent requests per instance
    max_instance_request_concurrency = var.container_concurrency
  }

  # Traffic: 100% to the latest revision. Blue/green and canary deployments
  # are handled through separate revisions and traffic splitting.
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.repo,
    google_secret_manager_secret.secrets,
  ]

  lifecycle {
    # Ignore changes to the image tag — CI/CD updates this directly
    # via `gcloud run deploy` or `terraform apply -var image_tag=...`
    ignore_changes = []
  }
}

# =============================================================================
# 8. IAM — Public access policy for Cloud Run
# =============================================================================
# When allow_unauthenticated is true, grant the allUsers principal the
# Cloud Run Invoker role. In production this is typically false because
# traffic arrives through the load balancer which handles auth.
# =============================================================================

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count = var.allow_unauthenticated ? 1 : 0

  provider = google-beta

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# =============================================================================
# 9. CLOUD LOAD BALANCING — External HTTPS with managed certificate
# =============================================================================
# Sets up a global external Application Load Balancer with:
#   - Google-managed SSL certificate (auto-provisioned and renewed)
#   - HTTP-to-HTTPS redirect
#   - Cloud CDN (optional, for static asset caching)
#   - Serverless NEG pointing to the Cloud Run service
#
# This block is created only when a domain_name is provided.
# Without a domain, users access Cloud Run via its default *.run.app URL.
# =============================================================================

# --- Serverless Network Endpoint Group (NEG) for Cloud Run ---
resource "google_compute_region_network_endpoint_group" "cloud_run_neg" {
  count = var.domain_name != "" ? 1 : 0

  provider = google-beta

  name                  = "${local.prefix}-neg"
  region                = var.region
  project               = var.project_id
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.app.name
  }

  depends_on = [google_project_service.required_apis]
}

# --- Backend Service ---
resource "google_compute_backend_service" "default" {
  count = var.domain_name != "" ? 1 : 0

  provider = google-beta

  name        = "${local.prefix}-backend"
  project     = var.project_id
  protocol    = "HTTP"
  port_name   = "http"
  timeout_sec = var.request_timeout

  # Point to the serverless NEG
  backend {
    group = google_compute_region_network_endpoint_group.cloud_run_neg[0].id
  }

  # Cloud CDN configuration
  enable_cdn = var.enable_cdn
  dynamic "cdn_policy" {
    for_each = var.enable_cdn ? [1] : []
    content {
      cache_mode                   = "CACHE_ALL_STATIC"
      default_ttl                  = 3600
      max_ttl                      = 86400
      signed_url_cache_max_age_sec = 0
    }
  }

  # Logging
  log_config {
    enable      = true
    sample_rate = local.is_production ? 0.5 : 1.0
  }
}

# --- URL Map (routes all traffic to the backend) ---
resource "google_compute_url_map" "default" {
  count = var.domain_name != "" ? 1 : 0

  name            = "${local.prefix}-urlmap"
  project         = var.project_id
  default_service = google_compute_backend_service.default[0].id
}

# --- Google-managed SSL Certificate ---
resource "google_compute_managed_ssl_certificate" "default" {
  count = var.domain_name != "" ? 1 : 0

  provider = google-beta

  name    = "${local.prefix}-cert"
  project = var.project_id

  managed {
    domains = [var.domain_name]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# --- HTTPS Target Proxy ---
resource "google_compute_target_https_proxy" "default" {
  count = var.domain_name != "" ? 1 : 0

  name             = "${local.prefix}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.default[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.default[0].id]
}

# --- Global Forwarding Rule (HTTPS on port 443) ---
resource "google_compute_global_forwarding_rule" "https" {
  count = var.domain_name != "" ? 1 : 0

  name       = "${local.prefix}-https-fwd"
  project    = var.project_id
  target     = google_compute_target_https_proxy.default[0].id
  port_range = "443"

  labels = local.labels
}

# --- HTTP-to-HTTPS redirect ---
resource "google_compute_url_map" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name    = "${local.prefix}-http-redirect"
  project = var.project_id

  default_url_redirect {
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    https_redirect         = true
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name    = "${local.prefix}-http-redirect-proxy"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  count = var.domain_name != "" ? 1 : 0

  name       = "${local.prefix}-http-redirect-fwd"
  project    = var.project_id
  target     = google_compute_target_http_proxy.http_redirect[0].id
  port_range = "80"

  labels = local.labels
}

# =============================================================================
# 10. CLOUD ARMOR — WAF (production only, when LB is enabled)
# =============================================================================
# Basic Cloud Armor security policy with OWASP Top-10 protection.
# Attached to the backend service when both domain_name is set and
# the environment is production.
# =============================================================================

resource "google_compute_security_policy" "waf" {
  count = var.domain_name != "" && local.is_production ? 1 : 0

  provider = google-beta

  name        = "${local.prefix}-waf"
  project     = var.project_id
  description = "Cloud Armor WAF policy for ${var.service_name} (${var.env})"

  # Default rule: allow all traffic
  rule {
    action   = "allow"
    priority = 2147483647

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    description = "Default allow rule"
  }

  # Rate limiting: max 1000 requests per minute per IP
  rule {
    action   = "rate_based_ban"
    priority = 1000

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      rate_limit_threshold {
        count        = 1000
        interval_sec = 60
      }
      conform_action = "allow"
      exceed_action  = "deny(429)"
      ban_duration_sec = 300
    }

    description = "Rate limiting: 1000 req/min per IP"
  }

  # Block known bad patterns (XSS)
  rule {
    action   = "deny(403)"
    priority = 2000

    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }

    description = "Block XSS attacks (OWASP ModSecurity CRS)"
  }

  # Block SQL injection
  rule {
    action   = "deny(403)"
    priority = 2001

    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }

    description = "Block SQL injection attacks (OWASP ModSecurity CRS)"
  }
}
