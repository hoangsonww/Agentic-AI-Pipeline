# =============================================================================
# Provider Configuration — Azure Container Apps Module
# =============================================================================
# Configures the AzureRM provider with required features blocks.
# Pin to a minimum version to ensure Container Apps API support.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.90.0, < 5.0.0"
    }
  }
}

provider "azurerm" {
  features {
    # Prevent accidental data loss on resource group deletion
    resource_group {
      prevent_deletion_if_contains_resources = true
    }

    # Purge Key Vault secrets on destroy to avoid soft-delete conflicts
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }

    # Retain OS disk on VM deletion (safety default)
    virtual_machine {
      delete_os_disk_on_deletion = false
    }

    log_analytics_workspace {
      permanently_delete_on_destroy = false
    }
  }
}
