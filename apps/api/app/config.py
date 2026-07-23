from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="QF_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "QuantumFintek API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    jwt_secret: SecretStr = SecretStr("development-only-change-me")
    access_token_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
