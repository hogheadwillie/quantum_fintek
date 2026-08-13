"""Application settings."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    database_url: str = "postgresql+asyncpg://quantum:quantum@localhost:5432/quantum_fintek"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_mode: str = Field(default="standalone", description="standalone | cluster")
    redis_cluster_nodes: str = Field(
        default="",
        description="Comma-separated host:port list when redis_mode=cluster",
    )
    redis_key_prefix: str = "qf"

    redis_socket_connect_timeout: float = Field(default=2.0, description="TCP connect timeout")
    redis_socket_timeout: float = Field(default=5.0, description="Per-command socket timeout")
    redis_cluster_error_retry_attempts: int = Field(
        default=5,
        description="Retries on ConnectionError/TimeoutError/ClusterDownError",
    )

    cors_origins: str = (
        "http://localhost:3000,http://app.localhost,http://api.localhost,http://localhost"
    )

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # JWT — prefer RS256 with rotatable PEM keys
    jwt_algorithm: str = Field(default="RS256", description="RS256 (prod) or HS256 (dev fallback)")
    jwt_key_id: str = Field(default="qf-key-1", description="Active signing key id (kid)")
    jwt_private_key_pem: str = Field(
        default="",
        description="Active RSA private key PEM (PKCS#8 or PKCS#1). Required for RS256 outside pure local HS fallback.",
    )
    jwt_public_key_pem: str = Field(
        default="",
        description="Active RSA public key PEM. Recommended even when private is present.",
    )
    jwt_previous_public_keys_json: str = Field(
        default="",
        description='JSON object of previous kid->public PEM still accepted for verify, e.g. {"qf-key-0":"-----BEGIN PUBLIC KEY-----\\n..."}',
    )

    rate_limit_trading: int = 60
    rate_limit_global: int = 600
    rate_limit_window: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def redis_cluster_node_list(self) -> list[tuple[str, int]]:
        nodes: list[tuple[str, int]] = []
        for part in self.redis_cluster_nodes.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                host, port_s = part.rsplit(":", 1)
                nodes.append((host.strip(), int(port_s)))
            else:
                nodes.append((part, 6379))
        return nodes

    @model_validator(mode="after")
    def _validate_jwt_for_env(self) -> "Settings":
        env = (self.app_env or "").lower()
        alg = (self.jwt_algorithm or "").upper()
        if env in {"production", "prod"}:
            if alg.startswith("HS"):
                raise ValueError("jwt_algorithm HS* is not allowed in production; use RS256")
            if alg.startswith("RS") and not (self.jwt_private_key_pem or "").strip():
                raise ValueError("jwt_private_key_pem is required for RS256 in production")
            if self.secret_key.startswith("change-me"):
                raise ValueError("secret_key must be changed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
