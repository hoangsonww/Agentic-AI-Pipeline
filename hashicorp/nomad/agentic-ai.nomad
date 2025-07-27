job "agentic-ai" {
  datacenters = ["dc1"]
  type = "service"

  group "web" {
    count = 1
    network { port "http" { to = 8000 } }

    task "app" {
      driver = "docker"
      config {
        image = "your-registry/agentic-ai:latest"
        ports = ["http"]
      }
      env {
        APP_HOST = "0.0.0.0"
        APP_PORT = "8000"
      }
      resources { cpu = 500 memory = 1024 }
      service {
        name = "agentic-ai"
        port = "http"
        check { type = "http" path = "/api/new_chat" interval = "10s" timeout = "2s" }
      }
    }
  }
}
