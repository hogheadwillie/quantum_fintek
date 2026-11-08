"""Redis client helpers — standalone or cluster, optional AUTH + TLS."""

from __future__ import annotations

from typing import Any, Optional, Union
from urllib.parse import quote, urlparse, urlunparse

import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster

from app.core.config import get_settings

RedisClient = Union[redis.Redis, RedisCluster]

_client: Optional[RedisClient] = None


def _inject_password(url: str, password: str) -> str:
    if not password or not url:
        return url
    parsed = urlparse(url)
    if parsed.password:
        return url
    user = parsed.username or ""
    host = parsed.hostname or "localhost"
    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{user}:{quote(password, safe='')}@" if user else f":{quote(password, safe='')}@"
    netloc = f"{auth}{host}{port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def _ssl_kwargs(settings: Any) -> dict[str, Any]:
    if not settings.redis_ssl:
        return {}
    import ssl

    req = (settings.redis_ssl_cert_reqs or "required").lower()
    mapping = {
        "none": ssl.CERT_NONE,
        "optional": ssl.CERT_OPTIONAL,
        "required": ssl.CERT_REQUIRED,
    }
    return {"ssl": True, "ssl_cert_reqs": mapping.get(req, ssl.CERT_REQUIRED)}


async def get_redis() -> RedisClient:
    """Return a shared async Redis client (standalone or cluster)."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    mode = (settings.redis_mode or "standalone").strip().lower()
    url = _inject_password(settings.redis_url, settings.redis_password or "")

    if mode == "cluster":
        _client = await _build_cluster_client(settings, url)
    else:
        kwargs: dict[str, Any] = {
            "decode_responses": True,
            "socket_connect_timeout": settings.redis_socket_connect_timeout,
            "socket_timeout": settings.redis_socket_timeout,
            **_ssl_kwargs(settings),
        }
        _client = redis.from_url(url, **kwargs)

    return _client


async def _build_cluster_client(settings: Any, url: str) -> RedisCluster:
    common: dict[str, Any] = {
        "decode_responses": True,
        "require_full_coverage": False,
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
        "socket_timeout": settings.redis_socket_timeout,
        "cluster_error_retry_attempts": settings.redis_cluster_error_retry_attempts,
        **_ssl_kwargs(settings),
    }
    if settings.redis_password:
        common["password"] = settings.redis_password

    nodes = settings.redis_cluster_node_list
    if not nodes:
        return RedisCluster.from_url(url, **common)

    startup_nodes = [{"host": h, "port": p} for h, p in nodes]
    return RedisCluster(startup_nodes=startup_nodes, **common)


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def is_cluster_client(client: RedisClient) -> bool:
    return isinstance(client, RedisCluster)
