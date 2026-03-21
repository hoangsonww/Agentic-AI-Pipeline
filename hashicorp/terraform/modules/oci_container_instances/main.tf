# ------------------------------------------------------------------------------
# OCI Container Instances Module - Main Infrastructure
# ------------------------------------------------------------------------------
# Deploys the Agentic AI FastAPI application and MCP server to Oracle Cloud
# Infrastructure using Container Instances, fronted by a public Load Balancer.
#
# Architecture:
#   Internet --> OCI LB (443/80) --> Private Subnet --> Container Instances
#     - App container:  FastAPI on port 8000, /health endpoint
#     - MCP container:  MCP server on port 8001
#
# Network topology:
#   VCN (10.0.0.0/16)
#     |-- Public Subnet  (10.0.1.0/24)  -- Load Balancer
#     |-- Private Subnet (10.0.2.0/24)  -- Container Instances
#
# Security model:
#   - Public subnet: ingress 80/443 from anywhere, egress to private subnet
#   - Private subnet: ingress from LB only, egress to OCI services + internet
#   - Network Security Group: granular per-port rules for container traffic
#   - All resources tagged for cost allocation and governance
# ------------------------------------------------------------------------------

locals {
  # Naming convention: {project}-{resource}-{env}
  name_prefix = "${var.project_name}-${var.env}"

  # Merge caller-supplied freeform tags with mandatory operational tags
  common_freeform_tags = merge(
    {
      "project"     = var.project_name
      "environment" = var.env
      "managed-by"  = "terraform"
      "module"      = "oci_container_instances"
    },
    var.freeform_tags,
  )

  # Defined tags pass-through (requires tag namespaces to be pre-created)
  common_defined_tags = var.defined_tags

  # Resolve MCP image tag: fall back to main app tag if not overridden
  effective_mcp_image_tag = var.mcp_image_tag != "" ? var.mcp_image_tag : var.image_tag

  # OCIR image URLs are built after the repository is created
  # Format: <region-key>.ocir.io/<namespace>/<repo>:<tag>
  ocir_region_key = replace(var.region, "-", "")
  app_image_url   = "${var.region}.ocir.io/${local.ocir_namespace}/${oci_artifacts_container_repository.app.display_name}:${var.image_tag}"
  mcp_image_url   = "${var.region}.ocir.io/${local.ocir_namespace}/${oci_artifacts_container_repository.mcp.display_name}:${local.effective_mcp_image_tag}"

  # If caller did not provide an OCIR namespace, look it up from the tenancy
  ocir_namespace = var.ocir_namespace != "" ? var.ocir_namespace : data.oci_objectstorage_namespace.this.namespace
}

# ========================== Data Sources =======================================

# Look up the object storage namespace (doubles as OCIR namespace in OCI)
data "oci_objectstorage_namespace" "this" {
  compartment_id = var.compartment_id
}

# Retrieve the list of OCI services for the service gateway
data "oci_core_services" "all" {}

# ==============================================================================
# 1. CONTAINER REGISTRY (OCIR)
# ==============================================================================
# Two private repositories: one for the main app, one for the MCP server.
# Images are pushed here by the CI/CD pipeline before Terraform apply.
# ------------------------------------------------------------------------------

resource "oci_artifacts_container_repository" "app" {
  compartment_id = var.compartment_id
  display_name   = "${var.project_name}/${var.ocir_repo_name}"
  is_public      = false
  is_immutable   = false

  # NOTE: freeform_tags are not supported on OCIR repositories as of
  # OCI provider v5.x. This block is a placeholder for future support.
}

resource "oci_artifacts_container_repository" "mcp" {
  compartment_id = var.compartment_id
  display_name   = "${var.project_name}/${var.mcp_ocir_repo_name}"
  is_public      = false
  is_immutable   = false
}

# ==============================================================================
# 2. VIRTUAL CLOUD NETWORK (VCN) & SUBNETS
# ==============================================================================
# A dedicated VCN isolates all Agentic AI resources. Two subnets:
#   - Public:  hosts the load balancer with internet-facing IP
#   - Private: hosts container instances, reachable only from the LB
# ------------------------------------------------------------------------------

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_id
  display_name   = "${local.name_prefix}-vcn"
  cidr_blocks    = [var.vcn_cidr_block]
  dns_label      = var.dns_label_vcn

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Internet Gateway -- allows public subnet to reach the internet
resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-igw"
  enabled        = true

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# NAT Gateway -- allows private subnet outbound internet access (no inbound)
resource "oci_core_nat_gateway" "this" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-natgw"

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Service Gateway -- allows private subnet to reach OCI services (OCIR, etc.)
resource "oci_core_service_gateway" "this" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-sgw"

  services {
    service_id = [
      for s in data.oci_core_services.all.services :
      s.id if can(regex("All .* Services In Oracle Services Network", s.name))
    ][0]
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# ----- Route Tables -----

# Public route table: default route to internet gateway
resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-rt-public"

  route_rules {
    description       = "Default route to internet"
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Private route table: NAT gateway for internet, service gateway for OCI services
resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-rt-private"

  route_rules {
    description       = "Outbound internet via NAT gateway"
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.this.id
  }

  route_rules {
    description       = "OCI services via service gateway"
    destination       = data.oci_core_services.all.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.this.id
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# ----- Security Lists -----

# Public subnet security list: allows HTTP/HTTPS ingress, all egress
resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-sl-public"

  # --- Ingress Rules ---

  # HTTP from anywhere (will redirect to HTTPS)
  ingress_security_rules {
    description = "Allow HTTP from internet"
    protocol    = "6" # TCP
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = 80
      max = 80
    }
  }

  # HTTPS from anywhere
  ingress_security_rules {
    description = "Allow HTTPS from internet"
    protocol    = "6"
    source      = "0.0.0.0/0"
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = 443
      max = 443
    }
  }

  # --- Egress Rules ---

  # Allow all outbound (LB needs to reach private subnet backends)
  egress_security_rules {
    description      = "Allow all outbound traffic"
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless        = false
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Private subnet security list: ingress from LB only, controlled egress
resource "oci_core_security_list" "private" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-sl-private"

  # --- Ingress Rules ---

  # App port from public subnet (load balancer health checks + traffic)
  ingress_security_rules {
    description = "Allow app traffic from public subnet (LB)"
    protocol    = "6"
    source      = var.public_subnet_cidr
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = var.app_port
      max = var.app_port
    }
  }

  # MCP port from public subnet (load balancer)
  ingress_security_rules {
    description = "Allow MCP traffic from public subnet (LB)"
    protocol    = "6"
    source      = var.public_subnet_cidr
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = var.mcp_port
      max = var.mcp_port
    }
  }

  # Internal: allow containers in private subnet to communicate with each other
  ingress_security_rules {
    description = "Allow intra-subnet communication"
    protocol    = "6"
    source      = var.private_subnet_cidr
    source_type = "CIDR_BLOCK"
    stateless   = false

    tcp_options {
      min = 1
      max = 65535
    }
  }

  # --- Egress Rules ---

  # Allow all outbound (container instances need to pull images, call APIs, etc.)
  egress_security_rules {
    description      = "Allow all outbound traffic"
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless        = false
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# ----- Subnets -----

# Public subnet: load balancer lives here
resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${local.name_prefix}-subnet-public"
  cidr_block                 = var.public_subnet_cidr
  dns_label                  = var.dns_label_public
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Private subnet: container instances live here
resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${local.name_prefix}-subnet-private"
  cidr_block                 = var.private_subnet_cidr
  dns_label                  = var.dns_label_private
  prohibit_public_ip_on_vnic = true
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_security_list.private.id]

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# ==============================================================================
# 3. NETWORK SECURITY GROUP (NSG)
# ==============================================================================
# NSGs provide granular, stateful firewall rules that attach directly to VNICs.
# These complement the subnet-level security lists with per-resource precision.
# ------------------------------------------------------------------------------

resource "oci_core_network_security_group" "container" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${local.name_prefix}-nsg-containers"

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# Ingress: app port from public subnet (LB)
resource "oci_core_network_security_group_security_rule" "app_ingress" {
  network_security_group_id = oci_core_network_security_group.container.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  description               = "Allow app port from load balancer subnet"
  source                    = var.public_subnet_cidr
  source_type               = "CIDR_BLOCK"
  stateless                 = false

  tcp_options {
    destination_port_range {
      min = var.app_port
      max = var.app_port
    }
  }
}

# Ingress: MCP port from public subnet (LB)
resource "oci_core_network_security_group_security_rule" "mcp_ingress" {
  network_security_group_id = oci_core_network_security_group.container.id
  direction                 = "INGRESS"
  protocol                  = "6"
  description               = "Allow MCP port from load balancer subnet"
  source                    = var.public_subnet_cidr
  source_type               = "CIDR_BLOCK"
  stateless                 = false

  tcp_options {
    destination_port_range {
      min = var.mcp_port
      max = var.mcp_port
    }
  }
}

# Ingress: allow inter-container communication within the private subnet
resource "oci_core_network_security_group_security_rule" "internal_ingress" {
  network_security_group_id = oci_core_network_security_group.container.id
  direction                 = "INGRESS"
  protocol                  = "6"
  description               = "Allow intra-subnet container communication"
  source                    = var.private_subnet_cidr
  source_type               = "CIDR_BLOCK"
  stateless                 = false

  tcp_options {
    destination_port_range {
      min = 1
      max = 65535
    }
  }
}

# Egress: all outbound traffic (image pulls, API calls, dependency fetches)
resource "oci_core_network_security_group_security_rule" "all_egress" {
  network_security_group_id = oci_core_network_security_group.container.id
  direction                 = "EGRESS"
  protocol                  = "all"
  description               = "Allow all outbound traffic"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  stateless                 = false
}

# ==============================================================================
# 4. CONTAINER INSTANCES
# ==============================================================================
# OCI Container Instances are a serverless container runtime. Each instance
# runs one or more containers on a dedicated micro-VM with no cluster overhead.
# We create separate instances for the app and MCP server for independent
# scaling and fault isolation.
# ------------------------------------------------------------------------------

# ----- Main Application Container Instance -----

resource "oci_container_instances_container_instance" "app" {
  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  display_name        = "${local.name_prefix}-app"
  state               = "ACTIVE"

  shape = var.shape

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  # Network: place in private subnet with NSG
  vnics {
    subnet_id             = oci_core_subnet.private.id
    display_name          = "${local.name_prefix}-app-vnic"
    is_public_ip_assigned = false
    nsg_ids               = [oci_core_network_security_group.container.id]
  }

  # Container definition: FastAPI application
  containers {
    display_name = "app"
    image_url    = local.app_image_url

    # Resource limits for the container (subset of instance resources)
    resource_config {
      vcpus_limit       = var.ocpus
      memory_limit_in_gbs = var.memory_in_gbs
    }

    # Health check: verifies the /health endpoint responds with 200
    health_checks {
      health_check_type = "HTTP"
      port              = var.app_port
      path              = var.health_check_path
      name              = "app-health"
      interval_in_seconds    = ceil(var.health_check_interval_ms / 1000)
      timeout_in_seconds     = ceil(var.health_check_timeout_ms / 1000)
      failure_threshold      = var.health_check_retries
      success_threshold      = 1
      failure_action         = "KILL"
    }

    # Standard environment variables + user-supplied overrides.
    # OCI Container Instances accept environment_variables as a flat map.
    environment_variables = merge(
      {
        APP_HOST    = "0.0.0.0"
        APP_PORT    = tostring(var.app_port)
        ENVIRONMENT = var.env
        SERVICE     = "app"
      },
      var.app_env_vars,
    )
  }

  # Graceful shutdown: allow the app to drain connections
  graceful_shutdown_timeout_in_seconds = var.graceful_shutdown_timeout_seconds

  freeform_tags = merge(local.common_freeform_tags, { "service" = "app" })
  defined_tags  = local.common_defined_tags
}

# ----- MCP Server Container Instance -----

resource "oci_container_instances_container_instance" "mcp" {
  compartment_id      = var.compartment_id
  availability_domain = var.availability_domain
  display_name        = "${local.name_prefix}-mcp"
  state               = "ACTIVE"

  shape = var.shape

  shape_config {
    ocpus         = var.mcp_ocpus
    memory_in_gbs = var.mcp_memory_in_gbs
  }

  vnics {
    subnet_id             = oci_core_subnet.private.id
    display_name          = "${local.name_prefix}-mcp-vnic"
    is_public_ip_assigned = false
    nsg_ids               = [oci_core_network_security_group.container.id]
  }

  containers {
    display_name = "mcp"
    image_url    = local.mcp_image_url

    resource_config {
      vcpus_limit       = var.mcp_ocpus
      memory_limit_in_gbs = var.mcp_memory_in_gbs
    }

    health_checks {
      health_check_type = "HTTP"
      port              = var.mcp_port
      path              = var.health_check_path
      name              = "mcp-health"
      interval_in_seconds    = ceil(var.health_check_interval_ms / 1000)
      timeout_in_seconds     = ceil(var.health_check_timeout_ms / 1000)
      failure_threshold      = var.health_check_retries
      success_threshold      = 1
      failure_action         = "KILL"
    }

    environment_variables = merge(
      {
        APP_HOST    = "0.0.0.0"
        APP_PORT    = tostring(var.mcp_port)
        ENVIRONMENT = var.env
        SERVICE     = "mcp"
      },
      var.mcp_env_vars,
    )
  }

  graceful_shutdown_timeout_in_seconds = var.graceful_shutdown_timeout_seconds

  freeform_tags = merge(local.common_freeform_tags, { "service" = "mcp" })
  defined_tags  = local.common_defined_tags
}

# ==============================================================================
# 5. LOAD BALANCER
# ==============================================================================
# A public flexible load balancer terminates HTTP/HTTPS and distributes traffic
# to the container instances in the private subnet. Backend sets include health
# checks that monitor /health at configurable intervals.
# ------------------------------------------------------------------------------

resource "oci_load_balancer_load_balancer" "this" {
  compartment_id = var.compartment_id
  display_name   = "${local.name_prefix}-lb"
  shape          = var.lb_shape
  is_private     = false

  subnet_ids = [oci_core_subnet.public.id]

  dynamic "shape_details" {
    for_each = var.lb_shape == "flexible" ? [1] : []
    content {
      minimum_bandwidth_in_mbps = var.lb_min_bandwidth_mbps
      maximum_bandwidth_in_mbps = var.lb_max_bandwidth_mbps
    }
  }

  freeform_tags = local.common_freeform_tags
  defined_tags  = local.common_defined_tags
}

# ----- Backend Sets -----

# App backend set with health checker
resource "oci_load_balancer_backend_set" "app" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = "${local.name_prefix}-app-bs"
  policy           = "ROUND_ROBIN"

  health_checker {
    protocol            = "HTTP"
    port                = var.app_port
    url_path            = var.health_check_path
    return_code         = 200
    interval_ms         = var.health_check_interval_ms
    timeout_in_millis   = var.health_check_timeout_ms
    retries             = var.health_check_retries
    is_force_plain_text = true
  }

  session_persistence_configuration {
    cookie_name      = "${var.project_name}-session"
    disable_fallback = false
  }
}

# MCP backend set with health checker
resource "oci_load_balancer_backend_set" "mcp" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = "${local.name_prefix}-mcp-bs"
  policy           = "ROUND_ROBIN"

  health_checker {
    protocol            = "HTTP"
    port                = var.mcp_port
    url_path            = var.health_check_path
    return_code         = 200
    interval_ms         = var.health_check_interval_ms
    timeout_in_millis   = var.health_check_timeout_ms
    retries             = var.health_check_retries
    is_force_plain_text = true
  }
}

# ----- Backends -----

# Register the app container instance as a backend
resource "oci_load_balancer_backend" "app" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  backendset_name  = oci_load_balancer_backend_set.app.name
  ip_address       = oci_container_instances_container_instance.app.vnics[0].private_ip
  port             = var.app_port
  weight           = 1
  backup           = false
  drain            = false
  offline          = false
}

# Register the MCP container instance as a backend
resource "oci_load_balancer_backend" "mcp" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  backendset_name  = oci_load_balancer_backend_set.mcp.name
  ip_address       = oci_container_instances_container_instance.mcp.vnics[0].private_ip
  port             = var.mcp_port
  weight           = 1
  backup           = false
  drain            = false
  offline          = false
}

# ----- Listeners -----

# HTTP listener on port 80 -- redirects to HTTPS when certificate is available,
# otherwise forwards directly to the app backend set.
resource "oci_load_balancer_listener" "http" {
  load_balancer_id         = oci_load_balancer_load_balancer.this.id
  name                     = "${local.name_prefix}-http-listener"
  default_backend_set_name = oci_load_balancer_backend_set.app.name
  port                     = 80
  protocol                 = "HTTP"

  connection_configuration {
    idle_timeout_in_seconds = 60
  }

  # When an SSL certificate is configured, attach the HTTP-to-HTTPS redirect
  # rule set to this listener so all HTTP traffic is redirected to port 443.
  rule_set_names = length(var.certificate_ids) > 0 ? [oci_load_balancer_rule_set.http_redirect[0].name] : []
}

# HTTPS listener on port 443 -- only created when an SSL certificate is provided
resource "oci_load_balancer_listener" "https" {
  count = length(var.certificate_ids) > 0 ? 1 : 0

  load_balancer_id         = oci_load_balancer_load_balancer.this.id
  name                     = "${local.name_prefix}-https-listener"
  default_backend_set_name = oci_load_balancer_backend_set.app.name
  port                     = 443
  protocol                 = "HTTP"

  ssl_configuration {
    # certificate_ids references OCI Certificate Service managed certificates.
    # For self-managed certificates, use certificate_name instead and create
    # an oci_load_balancer_certificate resource.
    certificate_ids          = var.certificate_ids
    verify_peer_certificate  = false
    cipher_suite_name        = "oci-default-ssl-cipher-suite-v1"
  }

  connection_configuration {
    idle_timeout_in_seconds = 120
  }
}

# ----- Rule Sets -----

# HTTP to HTTPS redirect rule (only created when certificate is present)
resource "oci_load_balancer_rule_set" "http_redirect" {
  count = length(var.certificate_ids) > 0 ? 1 : 0

  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = "${local.name_prefix}-http-redirect"

  items {
    action = "REDIRECT"

    redirect_uri {
      protocol = "HTTPS"
      port     = 443
      host     = "{host}"
      path     = "{path}"
      query    = "{query}"
    }

    conditions {
      attribute_name  = "PATH"
      attribute_value = "/"
      operator        = "PREFIX_MATCH"
    }

    response_code = 301
  }
}

# ----- Routing Policies -----

# Path-based routing: /mcp/* goes to MCP backend, everything else to app
resource "oci_load_balancer_path_route_set" "this" {
  load_balancer_id = oci_load_balancer_load_balancer.this.id
  name             = "${local.name_prefix}-path-routes"

  path_routes {
    path                    = "/mcp"
    backend_set_name        = oci_load_balancer_backend_set.mcp.name
    path_match_type {
      match_type = "PREFIX_MATCH"
    }
  }

  path_routes {
    path                    = "/"
    backend_set_name        = oci_load_balancer_backend_set.app.name
    path_match_type {
      match_type = "PREFIX_MATCH"
    }
  }
}
