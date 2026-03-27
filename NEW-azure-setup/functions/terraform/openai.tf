# ═══════════════════════════════════════════════════════════════════════════
#  Azure OpenAI — GPT-4.1 (Singapore) + text-embedding-3-large
# ═══════════════════════════════════════════════════════════════════════════

resource "azurerm_cognitive_account" "openai" {
  name                  = "${local.prefix}-openai-${random_string.suffix.result}"
  resource_group_name   = azurerm_resource_group.main.name
  location              = var.openai_location  # Southeast Asia (Singapore)
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "${local.alphanum}oai${random_string.suffix.result}"

  identity {
    type = "SystemAssigned"
  }

  network_acls {
    default_action = "Allow"
  }

  tags = local.tags
}

# ── GPT-4.1 Deployment (GlobalStandard) ───────────────────────────────────

resource "azurerm_cognitive_deployment" "gpt41" {
  name                 = var.openai_chat_model
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4.1"
    version = var.openai_chat_model_version
  }

  sku {
    name     = "GlobalStandard"
    capacity = var.openai_chat_capacity
  }
}

# ── text-embedding-3-large Deployment (Standard) ──────────────────────────

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.openai_embedding_model
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-large"
    version = var.openai_embedding_model_version
  }

  sku {
    name     = "Standard"
    capacity = var.openai_embedding_capacity
  }
}

# ── Grant Function App access to OpenAI via managed identity ──────────────

resource "azurerm_role_assignment" "func_openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}
