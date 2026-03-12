resource "azurerm_resource_group" "compute" {
  name     = "rg-${var.project}-compute-${var.environment}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project}-${var.environment}"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.compute.name
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.app_subnet_id
  tags                       = var.tags
}

# ── Ingestion API ─────────────────────────────────────────────────────────────

resource "azurerm_container_app" "ingestion_api" {
  name                         = "ca-${var.project}-api-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.compute.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    http_scale_rule {
      name                = "http-scale"
      concurrent_requests = "50"
    }

    container {
      name   = "ingestion-api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name        = "AZURE_KEYVAULT_URL"
        secret_name = "keyvault-url"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.managed_identity_client_id
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/readyz"
      }
    }
  }

  secret {
    name  = "keyvault-url"
    value = var.key_vault_uri
  }
}

# ── Processing Worker ─────────────────────────────────────────────────────────

resource "azurerm_container_app" "worker" {
  name                         = "ca-${var.project}-worker-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.compute.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  template {
    min_replicas = var.worker_min_replicas
    max_replicas = var.worker_max_replicas

    azure_queue_scale_rule {
      name         = "servicebus-scale"
      queue_name   = var.servicebus_queue_name
      queue_length = 10
      authentication {
        secret_ref        = "servicebus-conn"
        trigger_parameter = "connection"
      }
    }

    container {
      name   = "processing-worker"
      image  = var.worker_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.managed_identity_client_id
      }
      env {
        name        = "SERVICEBUS_CONNECTION_STRING"
        secret_name = "servicebus-conn"
      }
    }
  }

  secret {
    name  = "servicebus-conn"
    value = var.servicebus_connection_string
  }
}

# ── Analytics API ─────────────────────────────────────────────────────────────

resource "azurerm_container_app" "analytics_api" {
  name                         = "ca-${var.project}-analytics-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.compute.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas

    http_scale_rule {
      name                = "http-scale"
      concurrent_requests = "30"
    }

    container {
      name   = "analytics-api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.managed_identity_client_id
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/healthz"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8000
        path      = "/readyz"
      }
    }
  }
}
