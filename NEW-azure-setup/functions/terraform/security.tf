# ═══════════════════════════════════════════════════════════════════════════
#  Security — Azure AD app registration, managed identity, WAF
# ═══════════════════════════════════════════════════════════════════════════

data "azuread_client_config" "current" {}

# ── Azure AD Application Registration ─────────────────────────────────────

resource "azuread_application" "migrator" {
  display_name = "${var.project_name}-${var.environment}"
  owners       = [data.azuread_client_config.current.object_id]

  sign_in_audience = "AzureADMyOrg"

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allow the application to access the Migrator API"
      admin_consent_display_name = "Access Migrator API"
      enabled                    = true
      id                         = "00000000-0000-0000-0000-000000000001"
      type                       = "User"
      user_consent_description   = "Allow the application to access the Migrator API on your behalf"
      user_consent_display_name  = "Access Migrator API"
      value                      = "api.access"
    }
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Administrator role with full access"
    display_name         = "Admin"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000010"
    value                = "admin"
  }

  app_role {
    allowed_member_types = ["User"]
    description          = "Standard user role"
    display_name         = "User"
    enabled              = true
    id                   = "00000000-0000-0000-0000-000000000011"
    value                = "user"
  }

  web {
    redirect_uris = [
      "https://${azurerm_static_web_app.frontend.default_host_name}/.auth/login/aad/callback",
    ]

    implicit_grant {
      access_token_issuance_enabled = false
      id_token_issuance_enabled     = true
    }
  }

  single_page_application {
    redirect_uris = [
      "http://localhost:3000/",
      "http://localhost:5173/",
      "https://${azurerm_static_web_app.frontend.default_host_name}/",
    ]
  }

  required_resource_access {
    resource_app_id = "00000003-0000-0000-c000-000000000000" # Microsoft Graph

    resource_access {
      id   = "e1fe6dd8-ba31-4d61-89e7-88639da4683d" # User.Read
      type = "Scope"
    }
  }
}

# ── Service Principal ──────────────────────────────────────────────────────

resource "azuread_service_principal" "migrator" {
  client_id                    = azuread_application.migrator.client_id
  app_role_assignment_required = false
  owners                       = [data.azuread_client_config.current.object_id]
}

# ── Function App auth settings (EasyAuth with Azure AD) ────────────────────
# Auth is configured post-deployment via CLI:
#   az webapp auth microsoft update \
#     --name <func-app-name> \
#     --resource-group <rg-name> \
#     --client-id <client-id> \
#     --issuer "https://login.microsoftonline.com/<tenant-id>/v2.0" \
#     --allowed-audiences "api://<client-id>"

# ── Role assignments for Function App managed identity ─────────────────────

# Storage Blob Data Contributor (for queue and table operations)
resource "azurerm_role_assignment" "func_storage" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "func_storage_queue" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Queue Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}

resource "azurerm_role_assignment" "func_storage_table" {
  scope                = azurerm_storage_account.func.id
  role_definition_name = "Storage Table Data Contributor"
  principal_id         = azurerm_linux_function_app.main.identity[0].principal_id
}
