# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Variable Definitions
# =============================================================================

# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------
variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "migrator"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project_name))
    error_message = "Project name must be lowercase alphanumeric with hyphens, 2-21 characters."
  }
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "East Asia"
}

# -----------------------------------------------------------------------------
# AKS
# -----------------------------------------------------------------------------
variable "aks_node_count" {
  description = "Number of nodes in the default AKS node pool"
  type        = number
  default     = 3

  validation {
    condition     = var.aks_node_count >= 1 && var.aks_node_count <= 10
    error_message = "AKS node count must be between 1 and 10."
  }
}

variable "aks_vm_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_D2s_v3"
}

variable "aks_worker_min_count" {
  description = "Minimum nodes in the worker node pool"
  type        = number
  default     = 2
}

variable "aks_worker_max_count" {
  description = "Maximum nodes in the worker node pool"
  type        = number
  default     = 6
}

variable "kubernetes_version" {
  description = "Kubernetes version for AKS"
  type        = string
  default     = "1.33.7"
}

# -----------------------------------------------------------------------------
# PostgreSQL
# -----------------------------------------------------------------------------
variable "postgres_sku" {
  description = "SKU name for PostgreSQL Flexible Server"
  type        = string
  default     = "B_Standard_B2s"
}

variable "postgres_storage_mb" {
  description = "Storage size in MB for PostgreSQL"
  type        = number
  default     = 32768

  validation {
    condition     = var.postgres_storage_mb >= 32768
    error_message = "PostgreSQL storage must be at least 32768 MB (32 GB)."
  }
}

variable "postgres_version" {
  description = "PostgreSQL major version"
  type        = string
  default     = "16"
}

variable "postgres_admin_username" {
  description = "Administrator username for PostgreSQL"
  type        = string
  default     = "pgadmin"
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Redis
# -----------------------------------------------------------------------------
variable "redis_sku" {
  description = "SKU tier for Azure Cache for Redis"
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.redis_sku)
    error_message = "Redis SKU must be Basic, Standard, or Premium."
  }
}

variable "redis_capacity" {
  description = "Size of the Redis cache (C0-C6 for Basic/Standard, P1-P5 for Premium)"
  type        = number
  default     = 1
}

variable "redis_family" {
  description = "Redis cache family (C for Basic/Standard, P for Premium)"
  type        = string
  default     = "C"
}

# -----------------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------------
variable "openai_model" {
  description = "OpenAI model to deploy"
  type        = string
  default     = "gpt-4.1"
}

variable "openai_model_version" {
  description = "Version of the OpenAI model"
  type        = string
  default     = "2025-04-14"
}

variable "openai_tpm" {
  description = "Tokens per minute capacity for GPT model (in thousands)"
  type        = number
  default     = 10
}

variable "embedding_model" {
  description = "Embedding model to deploy"
  type        = string
  default     = "text-embedding-3-large"
}

variable "embedding_tpm" {
  description = "Tokens per minute capacity for embedding model (in thousands)"
  type        = number
  default     = 20
}

# -----------------------------------------------------------------------------
# Container Registry
# -----------------------------------------------------------------------------
variable "acr_sku" {
  description = "SKU for Azure Container Registry"
  type        = string
  default     = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.acr_sku)
    error_message = "ACR SKU must be Basic, Standard, or Premium."
  }
}

# -----------------------------------------------------------------------------
# Tags
# -----------------------------------------------------------------------------
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "mulesoft-to-springboot-migrator"
    ManagedBy   = "terraform"
    Application = "migrator-platform"
  }
}
