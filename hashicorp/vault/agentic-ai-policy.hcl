# =============================================================================
# Vault Policy — Agentic AI Application
# =============================================================================
# Usage:
#   vault policy write agentic-ai hashicorp/vault/agentic-ai-policy.hcl
#   vault write auth/approle/role/agentic-ai \
#     token_policies="agentic-ai" token_ttl=1h token_max_ttl=4h
# =============================================================================

# --- KV v2 secrets (API keys, credentials) ---
path "secret/data/agentic-ai/*" {
  capabilities = ["read", "list"]
}

path "secret/metadata/agentic-ai/*" {
  capabilities = ["read", "list"]
}

# --- KV v1 fallback ---
path "kv/data/agentic-ai/*" {
  capabilities = ["read", "list"]
}

# --- Database dynamic credentials (if using Vault DB engine) ---
path "database/creds/agentic-ai-*" {
  capabilities = ["read"]
}

# --- PKI: request TLS certificates ---
path "pki/issue/agentic-ai" {
  capabilities = ["create", "update"]
}

path "pki/certs" {
  capabilities = ["list"]
}

# --- Transit encryption (encrypt/decrypt data at rest) ---
path "transit/encrypt/agentic-ai" {
  capabilities = ["update"]
}

path "transit/decrypt/agentic-ai" {
  capabilities = ["update"]
}

# --- Token self-management ---
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# --- Deny all other paths ---
path "sys/*" {
  capabilities = ["deny"]
}
