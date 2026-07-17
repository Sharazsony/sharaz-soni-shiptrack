"""Application configuration.

Reads settings once from environment variables / .env via pydantic-settings.
Every other module imports the single `settings` instance below instead of
calling os.getenv() directly.
"""
from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    app_env: str = "local"
    log_level: str = "INFO"
    api_key: str
    audit_log_path: str = "/app/logs/audit.log"

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, v: str) -> str:
        # Startup guard: refuse to boot without a real API key. This is not
        # a silent-open-door situation — an empty/missing key is a hard fail.
        if v is None or v.strip() == "":
            raise ValueError(
                "API_KEY environment variable must be set to a non-empty value"
            )
        return v


settings = Settings()
