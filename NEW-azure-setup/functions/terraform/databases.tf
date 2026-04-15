# ═══════════════════════════════════════════════════════════════════════════
#  PostgreSQL Flexible Server + Redis Cache
# ═══════════════════════════════════════════════════════════════════════════

# ── Random password for PostgreSQL ─────────────────────────────────────────

resource "random_password" "postgresql" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}|:<>?"
}

# ── PostgreSQL Flexible Server ─────────────────────────────────────────────

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.prefix}-pg-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  version                       = var.postgresql_version
  administrator_login           = var.postgresql_admin_username
  administrator_password        = random_password.postgresql.result
  storage_mb                    = var.postgresql_storage_mb
  sku_name                      = var.postgresql_sku
  zone                          = "1"
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = false
  public_network_access_enabled = true  # Consumption plan - secured via SSL + firewall

  authentication {
    active_directory_auth_enabled = true
    password_auth_enabled         = true
    tenant_id                     = data.azurerm_client_config.current.tenant_id
  }

  tags = local.tags
}

# ── PostgreSQL Firewall: Allow Azure Services ─────────────────────────────

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# ── PostgreSQL Database ────────────────────────────────────────────────────

resource "azurerm_postgresql_flexible_server_database" "migrator" {
  name      = "migrator"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ── PostgreSQL Extensions (pgvector, uuid-ossp) ───────────────────────────

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR,UUID-OSSP"
}

# ── PostgreSQL Auto-stop ───────────────────────────────────────────────────

resource "azurerm_postgresql_flexible_server_configuration" "auto_stop" {
  name      = "idle_session_timeout"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = tostring(var.postgresql_auto_stop_minutes * 60 * 1000)
}

# ── Redis Cache (Basic C0) ────────────────────────────────────────────────

resource "azurerm_redis_cache" "main" {
  name                          = "${local.prefix}-redis-${random_string.suffix.result}"
  resource_group_name           = azurerm_resource_group.main.name
  location                      = azurerm_resource_group.main.location
  capacity                      = var.redis_capacity
  family                        = var.redis_family
  sku_name                      = var.redis_sku
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true   # Consumption plan can't VNet-integrate; secured via SSL + access key
  redis_version                 = "6"

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = local.tags
}
