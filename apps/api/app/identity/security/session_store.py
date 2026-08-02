"""Redis-backed refresh-token store and access-token denylist."""

from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as redis


class SessionStore:
    """Tracks active refresh JTIs and revoked access JTIs.

    Keys:
      {prefix}:refresh:{jti}       -> JSON {"sub": ..., "roles": [...]}  (TTL = refresh lifetime)
      {prefix}:user_refresh:{sub}  -> SET of refresh JTIs
      {prefix}:deny:{jti}          -> "1" (TTL = remaining access lifetime)
    """

    def __init__(self, client: redis.Redis, prefix: str = "qf") -> None:
        self.client = client
        self.prefix = prefix

    def _refresh_key(self, jti: str) -> str:
        return f"{self.prefix}:refresh:{jti}"

    def _user_refresh_key(self, subject: str) -> str:
        return f"{self.prefix}:user_refresh:{subject}"

    def _deny_key(self, jti: str) -> str:
        return f"{self.prefix}:deny:{jti}"

    async def store_refresh(
        self,
        jti: str,
        subject: str,
        ttl_seconds: int,
        roles: Optional[list[str]] = None,
    ) -> None:
        ttl = max(int(ttl_seconds), 1)
        payload = json.dumps({"sub": subject, "roles": roles or []})
        pipe = self.client.pipeline(transaction=True)
        pipe.setex(self._refresh_key(jti), ttl, payload)
        pipe.sadd(self._user_refresh_key(subject), jti)
        pipe.expire(self._user_refresh_key(subject), ttl)
        await pipe.execute()

    async def get_refresh_record(self, jti: str) -> Optional[dict[str, Any]]:
        raw = await self.client.get(self._refresh_key(jti))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "sub" in data:
                return data
        except json.JSONDecodeError:
            # Legacy plain-string subject values
            return {"sub": raw, "roles": []}
        return {"sub": str(raw), "roles": []}

    async def get_refresh_subject(self, jti: str) -> Optional[str]:
        record = await self.get_refresh_record(jti)
        return None if record is None else str(record.get("sub"))

    async def revoke_refresh(self, jti: str, subject: Optional[str] = None) -> None:
        if subject is None:
            record = await self.get_refresh_record(jti)
            subject = None if record is None else str(record.get("sub"))
        pipe = self.client.pipeline(transaction=True)
        pipe.delete(self._refresh_key(jti))
        if subject:
            pipe.srem(self._user_refresh_key(subject), jti)
        await pipe.execute()

    async def list_refresh_jtis(self, subject: str) -> list[str]:
        members = await self.client.smembers(self._user_refresh_key(subject))
        return sorted(str(m) for m in members)

    async def revoke_all_refresh_for_subject(self, subject: str) -> int:
        """Delete all refresh tokens for a subject. Returns count removed."""
        jtis = await self.list_refresh_jtis(subject)
        if not jtis:
            await self.client.delete(self._user_refresh_key(subject))
            return 0
        pipe = self.client.pipeline(transaction=True)
        for jti in jtis:
            pipe.delete(self._refresh_key(jti))
        pipe.delete(self._user_refresh_key(subject))
        await pipe.execute()
        return len(jtis)

    async def deny_access(self, jti: str, ttl_seconds: int) -> None:
        """Put an access-token JTI on the denylist until it would have expired."""
        await self.client.setex(self._deny_key(jti), max(int(ttl_seconds), 1), "1")

    async def is_denied(self, jti: str) -> bool:
        return bool(await self.client.exists(self._deny_key(jti)))

    async def deny_ttl_remaining(self, jti: str) -> int:
        """Remaining denylist TTL in seconds, or -2 if absent / -1 if no expiry."""
        return int(await self.client.ttl(self._deny_key(jti)))
