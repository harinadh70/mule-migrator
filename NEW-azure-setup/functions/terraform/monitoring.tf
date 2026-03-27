# ═══════════════════════════════════════════════════════════════════════════
#  Monitoring — Application Insights, Log Analytics, Alert Rules
# ═══════════════════════════════════════════════════════════════════════════

# ── Log Analytics Workspace ────────────────────────────────────────────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.prefix}-law"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.tags
}

# ── Application Insights ──────────────────────────────────────────────────

resource "azurerm_application_insights" "main" {
  name                = "${local.prefix}-appinsights"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = local.tags
}

# ── Action Group (email notifications) ─────────────────────────────────────

resource "azurerm_monitor_action_group" "email" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.prefix}-alerts"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "migrator"

  email_receiver {
    name                    = "admin"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  tags = local.tags
}

# ── Alert: Function App errors (5xx) ──────────────────────────────────────

resource "azurerm_monitor_metric_alert" "func_errors" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.prefix}-func-5xx-errors"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_linux_function_app.main.id]
  description         = "Alert when Function App returns 5xx errors"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "Http5xx"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 5
  }

  action {
    action_group_id = azurerm_monitor_action_group.email[0].id
  }

  tags = local.tags
}

# ── Alert: Function execution failures ─────────────────────────────────────

resource "azurerm_monitor_metric_alert" "func_failures" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.prefix}-func-failures"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_linux_function_app.main.id]
  description         = "Alert when functions fail execution"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "FunctionExecutionCount"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0

    dimension {
      name     = "FunctionExecutionResult"
      operator = "Include"
      values   = ["Failed"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.email[0].id
  }

  tags = local.tags
}

# ── Alert: PostgreSQL CPU > 80% ────────────────────────────────────────────

resource "azurerm_monitor_metric_alert" "pg_cpu" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.prefix}-pg-high-cpu"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_postgresql_flexible_server.main.id]
  description         = "PostgreSQL CPU usage exceeds 80%"
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.DBforPostgreSQL/flexibleServers"
    metric_name      = "cpu_percent"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email[0].id
  }

  tags = local.tags
}

# ── Alert: Redis memory > 80% ─────────────────────────────────────────────

resource "azurerm_monitor_metric_alert" "redis_memory" {
  count               = var.alert_email != "" ? 1 : 0
  name                = "${local.prefix}-redis-high-memory"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_redis_cache.main.id]
  description         = "Redis memory usage exceeds 80%"
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Cache/redis"
    metric_name      = "usedmemorypercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email[0].id
  }

  tags = local.tags
}

# ── Diagnostic settings — send Function App logs to Log Analytics ──────────

resource "azurerm_monitor_diagnostic_setting" "func" {
  name                       = "${local.prefix}-func-diag"
  target_resource_id         = azurerm_linux_function_app.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "FunctionAppLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "pg" {
  name                       = "${local.prefix}-pg-diag"
  target_resource_id         = azurerm_postgresql_flexible_server.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "PostgreSQLLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
