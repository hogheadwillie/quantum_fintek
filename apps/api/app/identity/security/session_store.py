"""Redis-backed refresh-token / denylist session store."""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis


class SessionStore:
    """Tracks active refresh JTIs and revoked access JTIs."""

    def __init__(self, client: redis.Redis, prefix: str = "qf") -> None:
        self.client = client
        self.prefix = prefix

    def _refresh_key(self, jti: str) -> str:
        return f"{self.prefix}:refresh:{jti}"

    def _deny_key(self, jti: str) -> str:
        return f"{self.prefix}:deny:{jti}"

    async def store_refresh(self, jti: str, subject: str, ttl_seconds: int) -> None:
        await self.client.setex(self._refresh_key(jti), ttl_seconds, subject)

    async def get_refresh_subject(self, jti: str) -> Optional[str]:
        return await self.client.get(self._refresh_key(jti))

    async def revoke_refresh(self, jti: str) -> None:
        await self.client.delete(self._refresh_key(jti))

    async def deny_access(self, jti: str, ttl_seconds: int) -> None:
        """Put an access-token JTI on the denylist until it would have expired."""
        await self.client.setex(self._deny_key(jti), max(ttl_seconds, 1), "1")

    async def is_denied(self, jti: str) -> bool:
        return bool(await self.client.exists(self._deny_key(jti)))
