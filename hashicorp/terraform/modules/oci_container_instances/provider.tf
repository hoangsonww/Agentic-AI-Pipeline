# ------------------------------------------------------------------------------
# OCI Container Instances Module - Provider Configuration
# ------------------------------------------------------------------------------
# Declares the required OCI provider and Terraform version constraints.
# Authentication is expected to be configured by the calling root module or
# via environment variables (OCI_TENANCY_OCID, OCI_USER_OCID, OCI_FINGERPRINT,
# OCI_PRIVATE_KEY_PATH, OCI_REGION) or instance principal / resource principal.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.30.0, < 7.0.0"
    }
  }
}

# NOTE: The provider block itself is intentionally omitted here.
# Child modules should NOT declare provider configurations — that is the
# responsibility of the root module. This follows the Terraform best practice
# of provider inheritance. The root module must configure the "oci" provider:
#
#   provider "oci" {
#     tenancy_ocid     = var.tenancy_ocid
#     user_ocid        = var.user_ocid
#     fingerprint      = var.fingerprint
#     private_key_path = var.private_key_path
#     region           = var.region
#   }
#
# Alternatively, for CI/CD pipelines, use environment variables or instance
# principal authentication:
#
#   provider "oci" {
#     auth   = "InstancePrincipal"
#     region = var.region
#   }
