"""Redis-backed refresh-token store and access-token denylist.

Cluster-safe key design uses Redis hash tags so multi-key operations for a
single subject land in the same hash slot:

  Denylist (sharded by JTI):
    {prefix}:deny:{{jti}}              -> "1"

  Refresh (sharded by subject):
    {prefix}:{{sub}}:rt:{jti}          -> JSON {sub, roles}
    {prefix}:{{sub}}:rts               -> SET of JTIs

  Reverse index (lookup subject from JTI; single-key):
    {prefix}:rtidx:{jti}               -> subject
"""

from __future__ import annotations

import json
from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster

RedisClient = Union[redis.Redis, RedisCluster]


class SessionStore:
    """Tracks active refresh JTIs and revoked access JTIs."""

    def __init__(self, client: RedisClient, prefix: str = "qf") -> None:
        self.client = client
        self.prefix = prefix

    # --- key builders (hash tags for cluster) ---

    def _deny_key(self, jti: str) -> str:
        # Shard denylist entries across slots by JTI
        return f"{self.prefix}:deny:{{{jti}}}"

    def _refresh_key(self, subject: str, jti: str) -> str:
        return f"{self.prefix}:{{{subject}}}:rt:{jti}"

    def _user_refresh_key(self, subject: str) -> str:
        return f"{self.prefix}:{{{subject}}}:rts"

    def _rtidx_key(self, jti: str) -> str:
        return f"{self.prefix}:rtidx:{jti}"

    # --- refresh tokens ---

    async def store_refresh(
        self,
        jti: str,
        subject: str,
        ttl_seconds: int,
        roles: Optional[list[str]] = None,
    ) -> None:
        ttl = max(int(ttl_seconds), 1)
        payload = json.dumps({"sub": subject, "roles": roles or []})
        rt_key = self._refresh_key(subject, jti)
        set_key = self._user_refresh_key(subject)
        idx_key = self._rtidx_key(jti)

        # Same-slot keys (subject-tagged) can be pipelined; index is separate.
        pipe = self.client.pipeline(transaction=False)
        pipe.setex(rt_key, ttl, payload)
        pipe.sadd(set_key, jti)
        pipe.expire(set_key, ttl)
        await pipe.execute()
        await self.client.setex(idx_key, ttl, subject)

    async def get_refresh_record(self, jti: str) -> Optional[dict[str, Any]]:
        subject = await self.client.get(self._rtidx_key(jti))
        if not subject:
            # Legacy fallback: old key shape qf:refresh:{jti}
            legacy = await self.client.get(f"{self.prefix}:refresh:{jti}")
            if not legacy:
                return None
            try:
                data = json.loads(legacy)
                if isinstance(data, dict) and "sub" in data:
                    return data
            except json.JSONDecodeError:
                return {"sub": str(legacy), "roles": []}
            return {"sub": str(legacy), "roles": []}

        raw = await self.client.get(self._refresh_key(str(subject), jti))
        if not raw:
            return {"sub": str(subject), "roles": []}
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "sub" in data:
                return data
        except json.JSONDecodeError:
            pass
        return {"sub": str(subject), "roles": []}

    async def get_refresh_subject(self, jti: str) -> Optional[str]:
        record = await self.get_refresh_record(jti)
        return None if record is None else str(record.get("sub"))

    async def revoke_refresh(self, jti: str, subject: Optional[str] = None) -> None:
        if subject is None:
            subject = await self.client.get(self._rtidx_key(jti))
            if subject is not None:
                subject = str(subject)
        if subject:
            pipe = self.client.pipeline(transaction=False)
            pipe.delete(self._refresh_key(subject, jti))
            pipe.srem(self._user_refresh_key(subject), jti)
            await pipe.execute()
        await self.client.delete(self._rtidx_key(jti))
        # Legacy cleanup
        await self.client.delete(f"{self.prefix}:refresh:{jti}")

    async def list_refresh_jtis(self, subject: str) -> list[str]:
        members = await self.client.smembers(self._user_refresh_key(subject))
        return sorted(str(m) for m in members)

    async def revoke_all_refresh_for_subject(self, subject: str) -> int:
        """Delete all refresh tokens for a subject. Returns count removed."""
        jtis = await self.list_refresh_jtis(subject)
        if not jtis:
            await self.client.delete(self._user_refresh_key(subject))
            return 0

        # Subject-tagged keys share a slot — safe to pipeline.
        pipe = self.client.pipeline(transaction=False)
        for jti in jtis:
            pipe.delete(self._refresh_key(subject, jti))
        pipe.delete(self._user_refresh_key(subject))
        await pipe.execute()

        # Index keys are on other slots — delete individually / small batches.
        for jti in jtis:
            await self.client.delete(self._rtidx_key(jti))
        return len(jtis)

    # --- access denylist (sharded by JTI) ---

    async def deny_access(self, jti: str, ttl_seconds: int) -> None:
        """Put an access-token JTI on the denylist until it would have expired."""
        await self.client.setex(self._deny_key(jti), max(int(ttl_seconds), 1), "1")

    async def is_denied(self, jti: str) -> bool:
        return bool(await self.client.exists(self._deny_key(jti)))

    async def deny_ttl_remaining(self, jti: str) -> int:
        return int(await self.client.ttl(self._deny_key(jti)))
