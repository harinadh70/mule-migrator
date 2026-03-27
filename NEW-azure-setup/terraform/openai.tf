# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Azure OpenAI Resources
# =============================================================================

# -----------------------------------------------------------------------------
# Azure Cognitive Services Account (OpenAI)
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-${local.resource_prefix}"
  resource_group_name   = azurerm_resource_group.main.name
  location              = "Southeast Asia"  # OpenAI with embeddings only available here (not East Asia)
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "oai-${local.resource_prefix}"

  network_acls {
    default_action = "Allow"
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# GPT-4o Model Deployment
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = var.openai_model
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.openai_model
    version = var.openai_model_version
  }

  scale {
    type     = "GlobalStandard"
    capacity = var.openai_tpm
  }
}

# -----------------------------------------------------------------------------
# Text Embedding Model Deployment
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.embedding_model
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = var.embedding_model
    version = "1"
  }

  scale {
    type     = "Standard"
    capacity = var.embedding_tpm
  }

  depends_on = [azurerm_cognitive_deployment.gpt4o]
}

# -----------------------------------------------------------------------------
# Role assignment - Allow AKS to access OpenAI
# -----------------------------------------------------------------------------
resource "azurerm_role_assignment" "aks_openai_user" {
  scope                            = azurerm_cognitive_account.openai.id
  role_definition_name             = "Cognitive Services OpenAI User"
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}
