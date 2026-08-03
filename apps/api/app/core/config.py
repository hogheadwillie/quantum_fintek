"""Application settings."""

from functools import lru_cache

from pydantic import Field
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

    # Client timeouts (seconds) — keep connect < node-timeout; socket ~ node-timeout
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
    jwt_algorithm: str = "HS256"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
