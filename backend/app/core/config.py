"""
HirePilot Configuration Module

Centralized settings management using pydantic-settings.
All configuration is loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    app_name: str = "HirePilot"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: SecretStr = Field(default=SecretStr("change-me"))
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://hirepilot:hirepilot@localhost:5432/hirepilot"
    database_echo: bool = False
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ── Redis ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ──────────────────────────────────────────────────────
    jwt_secret_key: SecretStr = Field(default=SecretStr("change-me-jwt"))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # ── OAuth ────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: SecretStr = Field(default=SecretStr(""))
    github_client_id: str = ""
    github_client_secret: SecretStr = Field(default=SecretStr(""))
    oauth_redirect_base_url: str = "http://localhost:3000"

    # ── OpenAI ───────────────────────────────────────────────────
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4-turbo-preview"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.3

    # ── S3/MinIO ─────────────────────────────────────────────────
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: SecretStr = Field(default=SecretStr("minioadmin"))
    s3_secret_key: SecretStr = Field(default=SecretStr("minioadmin"))
    s3_bucket_name: str = "hirepilot-resumes"
    s3_region: str = "us-east-1"

    # ── Credential Encryption ────────────────────────────────────
    credential_encryption_key: SecretStr = Field(default=SecretStr(""))

    # ── Rate Limiting ────────────────────────────────────────────
    scraping_rate_limit_per_minute: int = 10
    outreach_rate_limit_per_day: int = 50
    application_rate_limit_per_day: int = 20

    # ── Celery ───────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── LaTeX ────────────────────────────────────────────────────
    latex_compiler_path: str = "/usr/bin/pdflatex"
    latex_compile_timeout: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
