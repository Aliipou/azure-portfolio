"""Application settings loaded from environment variables / Key Vault."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = Field("dev", alias="APP_ENV")
    app_version: str = "1.0.0"
    log_level: str = Field("info", alias="LOG_LEVEL")

    # Database
    database_url: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/calibration_db",
        alias="DATABASE_URL",
    )

    # Azure AD
    azure_tenant_id: str = Field("", alias="AZURE_TENANT_ID")
    azure_client_id: str = Field("", alias="AZURE_CLIENT_ID")

    # Key Vault
    azure_keyvault_url: str = Field("", alias="AZURE_KEYVAULT_URL")

    # Service Bus / Redis
    servicebus_connection_string: str = Field("", alias="SERVICEBUS_CONNECTION_STRING")
    servicebus_queue_name: str = Field("calibration-measurements", alias="SERVICEBUS_QUEUE_NAME")
    use_redis_queue: bool = Field(True, alias="USE_REDIS_QUEUE")
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")

    # Blob Storage
    azure_storage_account_name: str = Field("", alias="AZURE_STORAGE_ACCOUNT_NAME")
    azure_storage_container_raw: str = Field("raw-measurements", alias="AZURE_STORAGE_CONTAINER_RAW")
    azure_storage_container_reports: str = Field("reports", alias="AZURE_STORAGE_CONTAINER_REPORTS")

    # Dev mode (bypass JWT)
    dev_mode: bool = Field(True, alias="DEV_MODE")

    # CORS
    allowed_origins: list[str] = Field(
        ["http://localhost:3000", "http://localhost:8000"],
        alias="ALLOWED_ORIGINS",
    )

    # Rate limiting
    rate_limit_per_minute: int = Field(60, alias="RATE_LIMIT_PER_MINUTE")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
