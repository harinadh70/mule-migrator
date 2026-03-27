# ═══════════════════════════════════════════════════════════════════════════
#  Variables — all configurable with sensible defaults
# ═══════════════════════════════════════════════════════════════════════════

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "project_name" {
  description = "Short project name used as a naming prefix"
  type        = string
  default     = "mulesoft-migrator"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "location" {
  description = "Primary Azure region for all resources (except OpenAI)"
  type        = string
  default     = "eastasia"
}

variable "openai_location" {
  description = "Azure region for OpenAI resources"
  type        = string
  default     = "southeastasia"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = ""
}

# ── PostgreSQL ─────────────────────────────────────────────────────────────

variable "postgresql_sku" {
  description = "PostgreSQL Flexible Server SKU"
  type        = string
  default     = "B_Standard_B1ms"
}

variable "postgresql_storage_mb" {
  description = "PostgreSQL storage in MB"
  type        = number
  default     = 32768
}

variable "postgresql_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}

variable "postgresql_admin_username" {
  description = "PostgreSQL administrator username"
  type        = string
  default     = "pgadmin"
}

variable "postgresql_auto_stop_minutes" {
  description = "Minutes of inactivity before auto-stop (0 = disabled)"
  type        = number
  default     = 60
}

# ── Redis ──────────────────────────────────────────────────────────────────

variable "redis_sku" {
  description = "Redis Cache SKU name"
  type        = string
  default     = "Basic"
}

variable "redis_family" {
  description = "Redis Cache family"
  type        = string
  default     = "C"
}

variable "redis_capacity" {
  description = "Redis Cache capacity (size)"
  type        = number
  default     = 0
}

# ── Azure OpenAI ──────────────────────────────────────────────────────────

variable "openai_chat_model" {
  description = "OpenAI chat model deployment name"
  type        = string
  default     = "gpt-41"
}

variable "openai_chat_model_version" {
  description = "OpenAI chat model version"
  type        = string
  default     = "2025-04-14"
}

variable "openai_chat_capacity" {
  description = "OpenAI chat model capacity (TPM in thousands)"
  type        = number
  default     = 30
}

variable "openai_embedding_model" {
  description = "OpenAI embedding model deployment name"
  type        = string
  default     = "text-embedding-3-large"
}

variable "openai_embedding_model_version" {
  description = "OpenAI embedding model version"
  type        = string
  default     = "1"
}

variable "openai_embedding_capacity" {
  description = "OpenAI embedding model capacity (TPM in thousands)"
  type        = number
  default     = 120
}

# ── Function App ──────────────────────────────────────────────────────────

variable "function_app_python_version" {
  description = "Python version for the Function App"
  type        = string
  default     = "3.12"
}

variable "function_timeout_seconds" {
  description = "Function execution timeout in seconds"
  type        = number
  default     = 600
}

# ── Networking ────────────────────────────────────────────────────────────

variable "vnet_address_space" {
  description = "Address space for the VNet"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "subnet_function_prefix" {
  description = "Subnet prefix for Function App delegation"
  type        = list(string)
  default     = ["10.0.1.0/24"]
}

variable "subnet_private_endpoints_prefix" {
  description = "Subnet prefix for private endpoints"
  type        = list(string)
  default     = ["10.0.2.0/24"]
}

# ── Azure AD ──────────────────────────────────────────────────────────────

variable "azure_ad_admin_group_id" {
  description = "Azure AD group ID for admin access (optional)"
  type        = string
  default     = ""
}

# ── Alerts ─────────────────────────────────────────────────────────────────

variable "alert_email" {
  description = "Email address for alert notifications"
  type        = string
  default     = ""
}

# ── Tags ──────────────────────────────────────────────────────────────────

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default = {
    project     = "mulesoft-migrator"
    managed_by  = "terraform"
  }
}
