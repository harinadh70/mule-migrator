# ═══════════════════════════════════════════════════════════════════════════
#  Networking — VNet, subnets, private endpoints, DNS zones
# ═══════════════════════════════════════════════════════════════════════════

# ── Virtual Network ────────────────────────────────────────────────────────

resource "azurerm_virtual_network" "main" {
  name                = "${local.prefix}-vnet"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  address_space       = var.vnet_address_space

  tags = local.tags
}

# ── Subnet for Function App (delegated) ───────────────────────────────────

resource "azurerm_subnet" "function_app" {
  name                 = "snet-function-app"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = var.subnet_function_prefix

  delegation {
    name = "function-app-delegation"
    service_delegation {
      name = "Microsoft.Web/serverFarms"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/action",
      ]
    }
  }
}

# ── Subnet for Private Endpoints ──────────────────────────────────────────

resource "azurerm_subnet" "private_endpoints" {
  name                                          = "snet-private-endpoints"
  resource_group_name                           = azurerm_resource_group.main.name
  virtual_network_name                          = azurerm_virtual_network.main.name
  address_prefixes                              = var.subnet_private_endpoints_prefix
  private_endpoint_network_policies             = "Disabled"
}

# ── Subnet for PostgreSQL (requires delegation) ──────────────────────────

resource "azurerm_subnet" "postgresql" {
  name                 = "snet-postgresql"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.3.0/24"]
  service_endpoints    = ["Microsoft.Storage"]

  delegation {
    name = "postgresql-delegation"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

# ── Function App VNet integration ──────────────────────────────────────────
# Disabled: Consumption plan doesn't support VNet integration.
# DB/Redis secured via SSL + firewall rules instead.

# ═══════════════════════════════════════════════════════════════════════════
#  Private DNS Zones
# ═══════════════════════════════════════════════════════════════════════════

# ── PostgreSQL ─────────────────────────────────────────────────────────────

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "pg-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = azurerm_virtual_network.main.id
}

# ── Redis ──────────────────────────────────────────────────────────────────

resource "azurerm_private_dns_zone" "redis" {
  name                = "privatelink.redis.cache.windows.net"
  resource_group_name = azurerm_resource_group.main.name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "redis" {
  name                  = "redis-dns-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.redis.name
  virtual_network_id    = azurerm_virtual_network.main.id
}

# ═══════════════════════════════════════════════════════════════════════════
#  Private Endpoints
# ═══════════════════════════════════════════════════════════════════════════

# ── Redis Private Endpoint ─────────────────────────────────────────────────

resource "azurerm_private_endpoint" "redis" {
  name                = "${local.prefix}-redis-pe"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "redis-psc"
    private_connection_resource_id = azurerm_redis_cache.main.id
    is_manual_connection           = false
    subresource_names              = ["redisCache"]
  }

  private_dns_zone_group {
    name                 = "redis-dns-group"
    private_dns_zone_ids = [azurerm_private_dns_zone.redis.id]
  }

  tags = local.tags
}
