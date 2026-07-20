"""Application configuration.

Reads settings once from environment variables / .env via pydantic-settings.
Every other module imports the single `settings` instance below instead of
calling os.getenv() directly.

Instead of hardcoding one full database_url, we read the individual
pieces (user, password, host, port, db name) from .env and BUILD the
connection string ourselves. This means if you ever change the database
name, you only change it in ONE place (postgres_db) — the URL updates
itself automatically.
"""
from __future__ import annotations

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Individual pieces, read straight from .env
    postgres_user: str
    postgres_password: str
    postgres_host: str = "db"      # "db" matches the docker-compose service name
    postgres_port: int = 5432
    postgres_db: str

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

    @computed_field
    @property
    def database_url(self) -> str:
        """Build the full SQLAlchemy connection string from the pieces above."""
        return (
            f"postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


# Instantiated once, imported everywhere else.
settings = Settings()