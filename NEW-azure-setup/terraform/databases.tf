# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Database Resources
# =============================================================================

# -----------------------------------------------------------------------------
# Azure Database for PostgreSQL Flexible Server
# -----------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server" "main" {
  name                   = "psql-${local.resource_prefix}"
  resource_group_name    = azurerm_resource_group.main.name
  location               = azurerm_resource_group.main.location
  version                = var.postgres_version
  administrator_login    = var.postgres_admin_username
  administrator_password = random_password.postgres.result
  storage_mb             = var.postgres_storage_mb
  sku_name               = var.postgres_sku

  # Networking - VNet integration via delegated subnet
  delegated_subnet_id           = azurerm_subnet.db.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgres.id
  public_network_access_enabled = false

  # Backup configuration
  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  # High availability (disabled for burstable SKU)
  # high_availability {
  #   mode = "ZoneRedundant"
  # }

  zone = "1"

  tags = local.common_tags

  depends_on = [
    azurerm_private_dns_zone_virtual_network_link.postgres,
    azurerm_subnet_network_security_group_association.db,
  ]
}

# -----------------------------------------------------------------------------
# PostgreSQL Database
# -----------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server_database" "migrator" {
  name      = "migrator"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# -----------------------------------------------------------------------------
# PostgreSQL Server Configuration
# -----------------------------------------------------------------------------
resource "azurerm_postgresql_flexible_server_configuration" "log_connections" {
  name      = "log_connections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "log_disconnections" {
  name      = "log_disconnections"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_configuration" "connection_throttling" {
  name      = "connection_throttle.enable"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "on"
}

# PgBouncer not supported on Burstable tier — skip for Demo/POC
# Upgrade to General Purpose tier to enable PgBouncer

# Firewall rules not needed — VNet integration handles access via delegated subnet

# -----------------------------------------------------------------------------
# Azure Cache for Redis
# -----------------------------------------------------------------------------
resource "azurerm_redis_cache" "main" {
  name                = "redis-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  capacity            = var.redis_capacity
  family              = var.redis_family
  sku_name            = var.redis_sku
  non_ssl_port_enabled = false
  minimum_tls_version = "1.2"

  redis_configuration {
    maxmemory_reserved              = 50
    maxmemory_delta                 = 50
    maxmemory_policy                = "allkeys-lru"
    maxfragmentationmemory_reserved = 50
  }

  public_network_access_enabled = false

  redis_version = "6"

  tags = local.common_tags
}
