"""Redis-backed refresh-token store and access-token denylist.

Cluster-safe keys use hash tags. Denylist checks honor fail-closed semantics
when ``fail_closed`` is True (Redis errors → treat as denied / raise).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Union

import redis.asyncio as redis
from redis.asyncio.cluster import RedisCluster
from redis.exceptions import RedisError

RedisClient = Union[redis.Redis, RedisCluster]
logger = logging.getLogger("quantum_fintek.session_store")


class SessionStore:
    """Tracks active refresh JTIs and revoked access JTIs."""

    def __init__(
        self,
        client: RedisClient,
        prefix: str = "qf",
        *,
        fail_closed: bool = True,
    ) -> None:
        self.client = client
        self.prefix = prefix
        self.fail_closed = fail_closed

    def _deny_key(self, jti: str) -> str:
        return f"{self.prefix}:deny:{{{jti}}}"

    def _refresh_key(self, subject: str, jti: str) -> str:
        return f"{self.prefix}:{{{subject}}}:rt:{jti}"

    def _user_refresh_key(self, subject: str) -> str:
        return f"{self.prefix}:{{{subject}}}:rts"

    def _rtidx_key(self, jti: str) -> str:
        return f"{self.prefix}:rtidx:{jti}"

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
        try:
            pipe = self.client.pipeline(transaction=False)
            pipe.setex(rt_key, ttl, payload)
            pipe.sadd(set_key, jti)
            pipe.expire(set_key, ttl)
            await pipe.execute()
            await self.client.setex(idx_key, ttl, subject)
        except RedisError:
            logger.exception("store_refresh failed")
            if self.fail_closed:
                raise

    async def get_refresh_record(self, jti: str) -> Optional[dict[str, Any]]:
        try:
            subject = await self.client.get(self._rtidx_key(jti))
            if not subject:
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
        except RedisError:
            logger.exception("get_refresh_record failed jti=%s", jti)
            if self.fail_closed:
                raise
            return None

    async def get_refresh_subject(self, jti: str) -> Optional[str]:
        record = await self.get_refresh_record(jti)
        return None if record is None else str(record.get("sub"))

    async def revoke_refresh(self, jti: str, subject: Optional[str] = None) -> None:
        try:
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
            await self.client.delete(f"{self.prefix}:refresh:{jti}")
        except RedisError:
            logger.exception("revoke_refresh failed")
            if self.fail_closed:
                raise

    async def list_refresh_jtis(self, subject: str) -> list[str]:
        try:
            members = await self.client.smembers(self._user_refresh_key(subject))
            return sorted(str(m) for m in members)
        except RedisError:
            logger.exception("list_refresh_jtis failed")
            if self.fail_closed:
                raise
            return []

    async def revoke_all_refresh_for_subject(self, subject: str) -> int:
        jtis = await self.list_refresh_jtis(subject)
        if not jtis:
            try:
                await self.client.delete(self._user_refresh_key(subject))
            except RedisError:
                if self.fail_closed:
                    raise
            return 0
        try:
            pipe = self.client.pipeline(transaction=False)
            for jti in jtis:
                pipe.delete(self._refresh_key(subject, jti))
            pipe.delete(self._user_refresh_key(subject))
            await pipe.execute()
            for jti in jtis:
                await self.client.delete(self._rtidx_key(jti))
            return len(jtis)
        except RedisError:
            logger.exception("revoke_all_refresh_for_subject failed")
            if self.fail_closed:
                raise
            return 0

    async def deny_access(self, jti: str, ttl_seconds: int) -> None:
        try:
            await self.client.setex(self._deny_key(jti), max(int(ttl_seconds), 1), "1")
        except RedisError:
            logger.exception("deny_access failed")
            if self.fail_closed:
                raise

    async def is_denied(self, jti: str) -> bool:
        """Return True if JTI is denylisted.

        On Redis failure: raise if fail_closed else return False (fail-open).
        """
        try:
            return bool(await self.client.exists(self._deny_key(jti)))
        except RedisError as exc:
            logger.exception("is_denied Redis error jti=%s", jti)
            if self.fail_closed:
                raise RuntimeError("Session store unavailable") from exc
            return False

    async def deny_ttl_remaining(self, jti: str) -> int:
        try:
            return int(await self.client.ttl(self._deny_key(jti)))
        except RedisError:
            if self.fail_closed:
                raise
            return -2
