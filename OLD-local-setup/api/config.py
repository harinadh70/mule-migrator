"""
Application configuration using Pydantic BaseSettings (12-factor app pattern).

Settings are loaded from environment variables and .env files.
Nested settings classes provide logical grouping for database, Redis,
Qdrant, LLM, RAG, and security configuration.
"""

from __future__ import annotations

import secrets
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# ── Nested Settings ───────────────────────────────────────────────


class DatabaseSettings(BaseSettings):
    """PostgreSQL + SQLAlchemy async connection settings."""

    model_config = SettingsConfigDict(env_prefix="")

    url: str = Field(
        default="postgresql+asyncpg://migrator:migrator_secret@localhost:5432/migrator",
        alias="DATABASE_URL",
    )
    pool_min_size: int = Field(default=5, alias="DB_POOL_MIN")
    pool_max_size: int = Field(default=20, alias="DB_POOL_MAX")
    pool_recycle_seconds: int = Field(default=3600, alias="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, alias="DB_ECHO")

    @property
    def sync_url(self) -> str:
        """Return a synchronous URL for Alembic migrations."""
        return self.url.replace("asyncpg", "psycopg2")


class RedisSettings(BaseSettings):
    """Redis connection settings for cache and Celery broker."""

    model_config = SettingsConfigDict(env_prefix="")

    url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_RESULT_BACKEND",
    )
    max_connections: int = Field(default=20, alias="REDIS_MAX_CONNECTIONS")
    socket_timeout: float = Field(default=5.0, alias="REDIS_SOCKET_TIMEOUT")


class QdrantSettings(BaseSettings):
    """Qdrant vector store settings for RAG retrieval."""

    model_config = SettingsConfigDict(env_prefix="")

    url: str = Field(
        default="http://localhost:6333",
        alias="QDRANT_URL",
    )
    collection: str = Field(
        default="mulesoft_knowledge",
        alias="QDRANT_COLLECTION",
    )
    api_key: Optional[str] = Field(default=None, alias="QDRANT_API_KEY")
    grpc_port: int = Field(default=6334, alias="QDRANT_GRPC_PORT")
    prefer_grpc: bool = Field(default=False, alias="QDRANT_PREFER_GRPC")


class LLMSettings(BaseSettings):
    """LLM provider API keys and model configuration."""

    model_config = SettingsConfigDict(env_prefix="")

    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    deepseek_api_key: Optional[str] = Field(default=None, alias="DEEPSEEK_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    default_provider: str = Field(default="anthropic", alias="DEFAULT_LLM_PROVIDER")
    default_model: str = Field(
        default="claude-sonnet-4-20250514", alias="DEFAULT_LLM_MODEL"
    )
    max_tokens: int = Field(default=8192, alias="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    request_timeout: float = Field(default=120.0, alias="LLM_REQUEST_TIMEOUT")

    @property
    def available_providers(self) -> list[str]:
        """Return a list of providers that have API keys configured."""
        providers = []
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.openai_api_key:
            providers.append("openai")
        if self.google_api_key:
            providers.append("google")
        if self.deepseek_api_key:
            providers.append("deepseek")
        if self.groq_api_key:
            providers.append("groq")
        return providers


class RAGSettings(BaseSettings):
    """RAG pipeline settings: embedding model, chunking, retrieval."""

    model_config = SettingsConfigDict(env_prefix="")

    enabled: bool = Field(default=True, alias="RAG_ENABLED")
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")
    chunk_size: int = Field(default=512, alias="RAG_CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="RAG_CHUNK_OVERLAP")
    top_k: int = Field(default=5, alias="RAG_TOP_K")
    score_threshold: float = Field(default=0.65, alias="RAG_SCORE_THRESHOLD")
    knowledge_dir: str = Field(
        default="api/rag/{knowledge", alias="RAG_KNOWLEDGE_DIR"
    )

    @field_validator("score_threshold")
    @classmethod
    def validate_score_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("score_threshold must be between 0.0 and 1.0")
        return v


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI Service connection settings."""

    model_config = SettingsConfigDict(env_prefix="")

    azure_openai_endpoint: str = Field(
        default="", alias="AZURE_OPENAI_ENDPOINT"
    )
    azure_openai_key: str = Field(
        default="", alias="AZURE_OPENAI_KEY"
    )
    azure_openai_api_version: str = Field(
        default="2024-02-01", alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_chat_deployment: str = Field(
        default="gpt-4o", alias="AZURE_OPENAI_CHAT_DEPLOYMENT"
    )
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-3-small", alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )

    @property
    def is_configured(self) -> bool:
        """Return True if the Azure OpenAI endpoint and key are set."""
        return bool(self.azure_openai_endpoint and self.azure_openai_key)


class AzureSettings(BaseSettings):
    """Azure platform integration settings (AD, Key Vault, App Insights)."""

    model_config = SettingsConfigDict(env_prefix="")

    azure_ad_tenant_id: str = Field(
        default="", alias="AZURE_AD_TENANT_ID"
    )
    azure_ad_client_id: str = Field(
        default="", alias="AZURE_AD_CLIENT_ID"
    )
    azure_ad_client_secret: str = Field(
        default="", alias="AZURE_AD_CLIENT_SECRET"
    )
    key_vault_uri: str = Field(
        default="", alias="KEY_VAULT_URI"
    )
    app_insights_connection_string: str = Field(
        default="", alias="APP_INSIGHTS_CONNECTION_STRING"
    )

    @property
    def is_ad_configured(self) -> bool:
        """Return True if Azure AD tenant and client ID are set."""
        return bool(self.azure_ad_tenant_id and self.azure_ad_client_id)


class SecuritySettings(BaseSettings):
    """Authentication, JWT, and rate-limiting settings."""

    model_config = SettingsConfigDict(env_prefix="")

    jwt_algorithm: str = Field(default="RS256", alias="JWT_ALGORITHM")
    jwt_private_key: Optional[str] = Field(default=None, alias="JWT_PRIVATE_KEY")
    jwt_public_key: Optional[str] = Field(default=None, alias="JWT_PUBLIC_KEY")
    access_token_expire_minutes: int = Field(
        default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    trusted_hosts: str = Field(default="*", alias="TRUSTED_HOSTS")

    # OAuth — GitHub
    github_client_id: Optional[str] = Field(default=None, alias="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(
        default=None, alias="GITHUB_CLIENT_SECRET"
    )
    github_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/github/callback",
        alias="GITHUB_REDIRECT_URI",
    )

    # API key encryption
    api_key_fernet_key: Optional[str] = Field(
        default=None, alias="API_KEY_FERNET_KEY"
    )

    @property
    def trusted_hosts_list(self) -> list[str]:
        if self.trusted_hosts == "*":
            return ["*"]
        return [h.strip() for h in self.trusted_hosts.split(",")]


# ── Root Settings ─────────────────────────────────────────────────


class Settings(BaseSettings):
    """
    Root application settings. Aggregates all nested settings groups.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ────────────────────────────────────────────────
    app_name: str = "MuleSoft-to-SpringBoot Migrator"
    environment: Environment = Field(
        default=Environment.PRODUCTION, alias="ENVIRONMENT"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(48),
        alias="SECRET_KEY",
    )
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )

    # ── Feature Flags ──────────────────────────────────────────
    agents_enabled: bool = Field(default=True, alias="AGENTS_ENABLED")
    enable_azure_ad: bool = Field(default=False, alias="ENABLE_AZURE_AD")
    enable_azure_openai: bool = Field(default=False, alias="ENABLE_AZURE_OPENAI")

    # ── Nested Settings ────────────────────────────────────────
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    azure: AzureSettings = Field(default_factory=AzureSettings)

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton factory for application settings."""
    return Settings()
