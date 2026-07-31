"""JWT Token Service with optional Redis session / denylist integration."""

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

    async def create_refresh_token(self, subject: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        jti = str(uuid.uuid4())
        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
            "jti": jti,
            "type": "refresh",
        }
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        if self.session_store:
            ttl = int((expire - now).total_seconds())
            await self.session_store.store_refresh(jti, subject, ttl)
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

    async def rotate_refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """Validate refresh token, revoke old JTI, issue new access + refresh."""
        payload = self.decode_token(refresh_token)
        if payload.type != "refresh":
            raise ValueError("Not a refresh token")
        if self.session_store:
            stored = await self.session_store.get_refresh_subject(payload.jti)
            if not stored or stored != payload.sub:
                raise ValueError("Refresh token revoked or unknown")
            await self.session_store.revoke_refresh(payload.jti)
        access = self.create_access_token(payload.sub)
        new_refresh = await self.create_refresh_token(payload.sub)
        return access, new_refresh

    def is_access_token(self, token: str) -> bool:
        payload = self.decode_token(token)
        return payload.type == "access"
