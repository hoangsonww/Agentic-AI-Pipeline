job "agentic-ai" {
  datacenters = ["dc1"]
  type        = "service"
  namespace   = "default"

  meta {
    version     = "0.4.0"
    managed_by  = "nomad"
    environment = "production"
  }

  # ---------- Update strategy ----------
  update {
    max_parallel      = 1
    health_check      = "checks"
    min_healthy_time  = "30s"
    healthy_deadline  = "5m"
    progress_deadline = "10m"
    auto_revert       = true
    canary            = 1
  }

  # ---------- Main API service ----------
  group "api" {
    count = 2

    spread {
      attribute = "${node.datacenter}"
    }

    network {
      port "http" { to = 8000 }
    }

    volume "chroma" {
      type      = "host"
      source    = "agentic-chroma"
      read_only = false
    }

    volume "sqlite" {
      type      = "host"
      source    = "agentic-sqlite"
      read_only = false
    }

    restart {
      attempts = 3
      interval = "5m"
      delay    = "15s"
      mode     = "delay"
    }

    task "app" {
      driver = "docker"

      config {
        image = "ghcr.io/hoangsonww/agentic-ai:latest"
        ports = ["http"]

        volumes = [
          "local/env:/app/.env:ro",
        ]

        logging {
          type = "journald"
          config {
            tag = "agentic-ai-app"
          }
        }
      }

      volume_mount {
        volume      = "chroma"
        destination = "/data/chroma"
      }

      volume_mount {
        volume      = "sqlite"
        destination = "/data/sqlite"
      }

      # Secrets injected from Vault
      template {
        data = <<-EOT
          PYTHONPATH=/app/src
          APP_HOST=0.0.0.0
          APP_PORT=8000
          MODEL_PROVIDER={{ key "agentic-ai/config/model_provider" }}
          OPENAI_API_KEY={{ with secret "secret/data/agentic-ai/api-keys" }}{{ .Data.data.openai_api_key }}{{ end }}
          ANTHROPIC_API_KEY={{ with secret "secret/data/agentic-ai/api-keys" }}{{ .Data.data.anthropic_api_key }}{{ end }}
          GOOGLE_API_KEY={{ with secret "secret/data/agentic-ai/api-keys" }}{{ .Data.data.google_api_key }}{{ end }}
          CHROMA_DIR=/data/chroma
          SQLITE_PATH=/data/sqlite/agent.db
          LOG_LEVEL=INFO
          LOG_DIR=/app/.logs
        EOT
        destination = "local/env"
        env         = true
      }

      resources {
        cpu    = 1000  # 1 GHz
        memory = 2048  # 2 GB
      }

      service {
        name = "agentic-ai-api"
        port = "http"
        tags = ["traefik.enable=true", "urlprefix-/"]

        check {
          type     = "http"
          path     = "/health"
          interval = "15s"
          timeout  = "5s"
        }

        check {
          type     = "http"
          path     = "/api/new_chat"
          interval = "30s"
          timeout  = "5s"
        }
      }
    }
  }

  # ---------- MCP server ----------
  group "mcp" {
    count = 1

    network {
      port "http" { to = 8001 }
    }

    volume "chroma" {
      type      = "host"
      source    = "agentic-chroma"
      read_only = false
    }

    task "mcp" {
      driver = "docker"

      config {
        image   = "ghcr.io/hoangsonww/agentic-ai:latest"
        ports   = ["http"]
        command = "python"
        args    = ["-m", "uvicorn", "mcp.server:create_app", "--factory",
                   "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
      }

      volume_mount {
        volume      = "chroma"
        destination = "/data/chroma"
      }

      template {
        data = <<-EOT
          PYTHONPATH=/app/src
          OPENAI_API_KEY={{ with secret "secret/data/agentic-ai/api-keys" }}{{ .Data.data.openai_api_key }}{{ end }}
          CHROMA_DIR=/data/chroma
          SQLITE_PATH=/data/sqlite/agent.db
        EOT
        destination = "local/env"
        env         = true
      }

      resources {
        cpu    = 500
        memory = 1024
      }

      service {
        name = "agentic-ai-mcp"
        port = "http"

        check {
          type     = "http"
          path     = "/status"
          interval = "15s"
          timeout  = "5s"
        }
      }
    }
  }
}
