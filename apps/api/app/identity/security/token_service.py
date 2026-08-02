"""JWT Token Service with Redis session / denylist integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from jose import jwt, JWTError
from pydantic import BaseModel

from app.identity.security.session_store import SessionStore


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    iat: datetime
    jti: str
    type: str  # "access" | "refresh"
    org_id: Optional[str] = None
    roles: list[str] = []


class TokenService:
    """Authentication token service."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 14,
        session_store: Optional[SessionStore] = None,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.session_store = session_store

    @staticmethod
    def _seconds_until(exp: datetime) -> int:
        now = datetime.now(timezone.utc)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return max(int((exp - now).total_seconds()), 1)

    def create_access_token(
        self,
        subject: str,
        org_id: Optional[str] = None,
        roles: Optional[list[str]] = None,
        extra_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "access",
            "org_id": org_id,
            "roles": roles or [],
        }
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    async def create_refresh_token(
        self,
        subject: str,
        roles: Optional[list[str]] = None,
        org_id: Optional[str] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        jti = str(uuid.uuid4())
        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
            "jti": jti,
            "type": "refresh",
            "roles": roles or [],
            "org_id": org_id,
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        if self.session_store:
            ttl = self._seconds_until(expire)
            await self.session_store.store_refresh(jti, subject, ttl, roles=roles or [])
        return token

    def decode_token(self, token: str) -> TokenPayload:
        try:
            data = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenPayload(**data)
        except JWTError as exc:
            raise ValueError("Invalid or expired token") from exc

    async def validate_access_token(self, token: str) -> TokenPayload:
        payload = self.decode_token(token)
        if payload.type != "access":
            raise ValueError("Not an access token")
        if self.session_store and await self.session_store.is_denied(payload.jti):
            raise ValueError("Token has been revoked")
        return payload

    async def revoke_access_token(self, access_token: str) -> TokenPayload:
        """Decode access token and place its JTI on the Redis denylist until exp."""
        payload = self.decode_token(access_token)
        if payload.type != "access":
            raise ValueError("Not an access token")
        if self.session_store:
            ttl = self._seconds_until(payload.exp)
            await self.session_store.deny_access(payload.jti, ttl)
        return payload

    async def logout(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Revoke current access JTI; optionally revoke a refresh token."""
        access_payload = await self.revoke_access_token(access_token)
        refresh_revoked = False
        if refresh_token and self.session_store:
            try:
                refresh_payload = self.decode_token(refresh_token)
                if refresh_payload.type == "refresh":
                    await self.session_store.revoke_refresh(
                        refresh_payload.jti, subject=refresh_payload.sub
                    )
                    refresh_revoked = True
            except ValueError:
                # Expired/invalid refresh still counts as logged out client-side
                refresh_revoked = False
        return {
            "access_jti_denied": access_payload.jti,
            "subject": access_payload.sub,
            "refresh_revoked": refresh_revoked,
        }

    async def logout_all(self, access_token: str) -> dict[str, Any]:
        """Deny current access token and revoke all refresh tokens for the subject."""
        access_payload = await self.revoke_access_token(access_token)
        revoked_refresh = 0
        if self.session_store:
            revoked_refresh = await self.session_store.revoke_all_refresh_for_subject(
                access_payload.sub
            )
        return {
            "access_jti_denied": access_payload.jti,
            "subject": access_payload.sub,
            "refresh_tokens_revoked": revoked_refresh,
        }

    async def rotate_refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """Validate refresh token, revoke old JTI, issue new access + refresh."""
        payload = self.decode_token(refresh_token)
        if payload.type != "refresh":
            raise ValueError("Not a refresh token")

        roles = list(payload.roles or [])
        org_id = payload.org_id

        if self.session_store:
            record = await self.session_store.get_refresh_record(payload.jti)
            if not record or str(record.get("sub")) != payload.sub:
                raise ValueError("Refresh token revoked or unknown")
            # Prefer roles from Redis record if JWT omitted them
            stored_roles = record.get("roles") or []
            if not roles and isinstance(stored_roles, list):
                roles = [str(r) for r in stored_roles]
            await self.session_store.revoke_refresh(payload.jti, subject=payload.sub)

        access = self.create_access_token(payload.sub, org_id=org_id, roles=roles)
        new_refresh = await self.create_refresh_token(payload.sub, roles=roles, org_id=org_id)
        return access, new_refresh

    def is_access_token(self, token: str) -> bool:
        payload = self.decode_token(token)
        return payload.type == "access"
