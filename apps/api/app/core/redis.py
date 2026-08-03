"""Redis client helpers — standalone or cluster."""

from __future__ import annotations

from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster

from app.core.config import get_settings

RedisClient = Union[redis.Redis, RedisCluster]

_client: Optional[RedisClient] = None


async def get_redis() -> RedisClient:
    """Return a shared async Redis client (standalone or cluster)."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    mode = (settings.redis_mode or "standalone").strip().lower()

    if mode == "cluster":
        _client = await _build_cluster_client(settings)
    else:
        _client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )

    return _client


async def _build_cluster_client(settings: Any) -> RedisCluster:
    """Build RedisCluster with timeouts aligned to cluster-node-timeout.

    Server-side NODE_TIMEOUT (compose default 5000ms) drives PFAIL/FAIL.
    Client socket timeouts should fail a dead connection *before* the next
    auth path blocks for the full gossip window, then retry onto a live node.
    """
    common: dict[str, Any] = {
        "decode_responses": True,
        "require_full_coverage": False,
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
        "socket_timeout": settings.redis_socket_timeout,
        "cluster_error_retry_attempts": settings.redis_cluster_error_retry_attempts,
    }

    nodes = settings.redis_cluster_node_list
    if not nodes:
        return RedisCluster.from_url(settings.redis_url, **common)

    startup_nodes = [{"host": h, "port": p} for h, p in nodes]
    return RedisCluster(startup_nodes=startup_nodes, **common)


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def is_cluster_client(client: RedisClient) -> bool:
    return isinstance(client, RedisCluster)
