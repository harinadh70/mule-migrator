# ═══════════════════════════════════════════════════════════════════════════
#  Core resources: Resource Group, Storage Account, Function App, Static
#  Web App, Key Vault.
# ═══════════════════════════════════════════════════════════════════════════

locals {
  rg_name  = var.resource_group_name != "" ? var.resource_group_name : "${var.project_name}-${var.environment}-rg"
  prefix   = "${var.project_name}-${var.environment}"
  # Sanitise for resources that require alphanumeric-only names
  alphanum = replace(replace(local.prefix, "-", ""), "_", "")
  tags     = merge(var.tags, { environment = var.environment })
}

# ── Resource Group ─────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = local.rg_name
  location = var.location
  tags     = local.tags
}

# ── Random suffix for globally unique names ────────────────────────────────

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# ── Storage Account (for Function App + queues) ───────────────────────────

resource "azurerm_storage_account" "func" {
  name                     = "mulemigsa${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = local.tags
}

# ── Storage Queues ─────────────────────────────────────────────────────────

resource "azurerm_storage_queue" "migration_queue" {
  name                 = "migration-queue"
  storage_account_name = azurerm_storage_account.func.name
}

resource "azurerm_storage_queue" "build_queue" {
  name                 = "build-queue"
  storage_account_name = azurerm_storage_account.func.name
}

resource "azurerm_storage_queue" "validation_queue" {
  name                 = "validation-queue"
  storage_account_name = azurerm_storage_account.func.name
}

resource "azurerm_storage_queue" "validation_teardown_queue" {
  name                 = "validation-teardown-queue"
  storage_account_name = azurerm_storage_account.func.name
}

# ── Storage Tables ───────────────────────────────────────────────────────────

resource "azurerm_storage_table" "build_logs" {
  name                 = "buildlogs"
  storage_account_name = azurerm_storage_account.func.name
}

resource "azurerm_storage_table" "validation_logs" {
  name                 = "validationlogs"
  storage_account_name = azurerm_storage_account.func.name
}

# ── App Service Plan (Consumption / Linux) ─────────────────────────────────

resource "azurerm_service_plan" "func" {
  name                = "${local.prefix}-plan"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption plan (~$0 when idle)

  tags = local.tags
}

# ── Linux Function App (Python 3.12) ──────────────────────────────────────

resource "azurerm_linux_function_app" "main" {
  name                = "${local.prefix}-func-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.func.id

  storage_account_name       = azurerm_storage_account.func.name
  storage_account_access_key = azurerm_storage_account.func.primary_access_key

  https_only                 = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = var.function_app_python_version
    }

    cors {
      allowed_origins     = ["*"]
      support_credentials = false
    }

    ftps_state               = "Disabled"
    minimum_tls_version      = "1.2"
    application_insights_key = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"            = "python"
    "FUNCTIONS_EXTENSION_VERSION"         = "~4"
    "PYTHON_ISOLATE_WORKER_DEPENDENCIES"  = "1"
    "ENVIRONMENT"                         = var.environment
    "LOG_LEVEL"                           = var.environment == "prod" ? "INFO" : "DEBUG"

    # Database (resolved from Key Vault)
    "POSTGRESQL_CONNECTION_STRING"        = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/postgresql-connection-string/)"

    # Redis (resolved from Key Vault)
    "REDIS_URL"                           = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/redis-connection-string/)"

    # GitHub Copilot (primary LLM provider)
    "GITHUB_TOKEN"                        = var.github_token
    "GITHUB_COPILOT_MODEL"                = "gpt-4.1"

    # Azure OpenAI (fallback LLM provider)
    "AZURE_OPENAI_ENDPOINT"               = azurerm_cognitive_account.openai.endpoint
    "AZURE_OPENAI_CHAT_DEPLOYMENT"        = var.openai_chat_model
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"   = var.openai_embedding_model
    "AZURE_OPENAI_API_VERSION"            = var.openai_chat_model_version

    # Key Vault
    "KEY_VAULT_URI"                       = azurerm_key_vault.main.vault_uri

    # Azure AD
    "AZURE_AD_TENANT_ID"                  = data.azuread_client_config.current.tenant_id
    "AZURE_AD_CLIENT_ID"                  = azuread_application.migrator.client_id

    # Admin
    "ADMIN_EMAIL"                         = var.admin_email
    "ADMIN_PASSWORD"                      = var.admin_password
    "ENABLE_LLM"                          = "true"

    # Azure OpenAI API Key (for fallback)
    "AZURE_OPENAI_API_KEY"               = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/openai-api-key/)"

    # Direct PostgreSQL connection params (for compatibility)
    "PGHOST"                              = azurerm_postgresql_flexible_server.main.fqdn
    "PGPORT"                              = "5432"
    "PGDATABASE"                          = "migrator"
    "PGUSER"                              = var.postgresql_admin_username
    "PGPASSWORD"                          = random_password.postgresql.result
    "PGSSLMODE"                           = "require"

    # CORS
    "CORS_ORIGINS"                        = "*"

    # Container Registry (for validation deployments)
    "ACR_LOGIN_SERVER"                    = var.acr_login_server
    "ACR_ADMIN_USERNAME"                  = var.acr_admin_username
    "ACR_ADMIN_PASSWORD"                  = var.acr_admin_password
    "AZURE_SUBSCRIPTION_ID"               = data.azurerm_client_config.current.subscription_id
    "RESOURCE_GROUP"                      = azurerm_resource_group.main.name
    "AZURE_LOCATION"                      = var.location

    # App Insights
    "APP_INSIGHTS_CONNECTION_STRING"      = azurerm_application_insights.main.connection_string
    "APPLICATIONINSIGHTS_CONNECTION_STRING" = azurerm_application_insights.main.connection_string
  }

  tags = local.tags

  # Key Vault access policy is created after the Function App
  # (uses the Function App's managed identity principal_id)
}

# ── Key Vault ──────────────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "main" {
  name                       = "mulemigkv${random_string.suffix.result}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  tags = local.tags
}

# Access policy — deployer (current user/SP)
resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Purge", "Recover",
  ]
}

# Access policy — Function App managed identity
resource "azurerm_key_vault_access_policy" "function_app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_function_app.main.identity[0].principal_id

  secret_permissions = [
    "Get", "List",
  ]
}

# ── Key Vault Secrets ──────────────────────────────────────────────────────

resource "azurerm_key_vault_secret" "postgresql_connection_string" {
  name         = "postgresql-connection-string"
  value        = "host=${azurerm_postgresql_flexible_server.main.fqdn} port=5432 dbname=migrator user=${var.postgresql_admin_username} password=${random_password.postgresql.result} sslmode=require"
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.deployer]
}

resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "openai-api-key"
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.deployer]
}

resource "azurerm_key_vault_secret" "redis_connection_string" {
  name         = "redis-connection-string"
  value        = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  key_vault_id = azurerm_key_vault.main.id

  depends_on = [azurerm_key_vault_access_policy.deployer]
}

# ── Static Web App (frontend) ─────────────────────────────────────────────

resource "azurerm_static_web_app" "frontend" {
  name                = "${local.prefix}-swa-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku_tier            = "Standard"
  sku_size            = "Standard"

  tags = local.tags
}
