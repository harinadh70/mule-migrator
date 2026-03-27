# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Monitoring & Alerting
# =============================================================================

# -----------------------------------------------------------------------------
# Log Analytics Workspace
# -----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Application Insights (connected to Log Analytics)
# -----------------------------------------------------------------------------
resource "azurerm_application_insights" "main" {
  name                = "appi-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Diagnostic Settings for AKS
# -----------------------------------------------------------------------------
resource "azurerm_monitor_diagnostic_setting" "aks" {
  name                       = "diag-aks-${local.resource_prefix}"
  target_resource_id         = azurerm_kubernetes_cluster.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "kube-apiserver"
  }

  enabled_log {
    category = "kube-controller-manager"
  }

  enabled_log {
    category = "kube-scheduler"
  }

  enabled_log {
    category = "kube-audit"
  }

  enabled_log {
    category = "kube-audit-admin"
  }

  enabled_log {
    category = "guard"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# -----------------------------------------------------------------------------
# Diagnostic Settings for PostgreSQL
# -----------------------------------------------------------------------------
resource "azurerm_monitor_diagnostic_setting" "postgres" {
  name                       = "diag-psql-${local.resource_prefix}"
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

# -----------------------------------------------------------------------------
# Action Group for Alerts
# -----------------------------------------------------------------------------
resource "azurerm_monitor_action_group" "critical" {
  name                = "ag-critical-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "critical"

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Alert Rule: API 5xx Error Rate > 5%
# -----------------------------------------------------------------------------
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "api_5xx_rate" {
  name                = "alert-api-5xx-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  description         = "Fires when API 5xx error rate exceeds 5%"
  severity            = 1
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"

  criteria {
    query = <<-QUERY
      let total_requests = ContainerLog
      | where LogEntry has "HTTP"
      | summarize total = count() by bin(TimeGenerated, 5m);
      let error_requests = ContainerLog
      | where LogEntry has "HTTP" and LogEntry has_any ("500", "501", "502", "503", "504")
      | summarize errors = count() by bin(TimeGenerated, 5m);
      total_requests
      | join kind=leftouter error_requests on TimeGenerated
      | extend error_rate = iff(total > 0, todouble(coalesce(errors, 0)) / todouble(total) * 100, 0.0)
      | where error_rate > 5
      | project TimeGenerated, total, errors=coalesce(errors, 0), error_rate
    QUERY

    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  auto_mitigation_enabled = true

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Alert Rule: Pod Restart Count > 3
# -----------------------------------------------------------------------------
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "pod_restarts" {
  name                = "alert-pod-restarts-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  description         = "Fires when any pod restarts more than 3 times in 15 minutes"
  severity            = 2
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"

  criteria {
    query = <<-QUERY
      KubePodInventory
      | where Namespace == "migrator"
      | summarize RestartCount = sum(PodRestartCount) by Name, bin(TimeGenerated, 15m)
      | where RestartCount > 3
      | project TimeGenerated, PodName=Name, RestartCount
    QUERY

    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  auto_mitigation_enabled = true

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Alert Rule: CPU Usage > 80%
# -----------------------------------------------------------------------------
resource "azurerm_monitor_metric_alert" "cpu_high" {
  name                = "alert-cpu-high-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_kubernetes_cluster.main.id]
  description         = "Fires when node CPU utilization exceeds 80%"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "node_cpu_usage_percentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Alert Rule: Memory Usage > 85%
# -----------------------------------------------------------------------------
resource "azurerm_monitor_metric_alert" "memory_high" {
  name                = "alert-memory-high-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_kubernetes_cluster.main.id]
  description         = "Fires when node memory utilization exceeds 85%"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT15M"
  enabled             = true

  criteria {
    metric_namespace = "Microsoft.ContainerService/managedClusters"
    metric_name      = "node_memory_working_set_percentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 85
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = local.common_tags
}
