# =============================================================================
# Provider Configuration — Google Cloud Platform
# =============================================================================
# This module requires both the GA and beta Google providers. The beta
# provider is needed for Cloud Run v2 and certain IAM / networking features
# that are still in preview.  The caller (root module) supplies project_id
# and region via variables; the provider blocks here are configured using
# those values so the module is fully self-contained.
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# -----------------------------------------------------------------------------
# GA provider — used for most resources
# -----------------------------------------------------------------------------
provider "google" {
  project = var.project_id
  region  = var.region
}

# -----------------------------------------------------------------------------
# Beta provider — used for Cloud Run v2, advanced IAM, and preview features
# -----------------------------------------------------------------------------
provider "google-beta" {
  project = var.project_id
  region  = var.region
}
