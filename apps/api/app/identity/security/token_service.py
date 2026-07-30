"""JWT Token Service — foundation for authentication.

Production goals:
- Short-lived JWT access tokens (RS256 / ES256)
- Opaque refresh tokens with rotation
- Server-side revocation / denylist
- Optional session binding (IP, user-agent)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from jose import jwt, JWTError
from pydantic import BaseModel


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
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

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

    def create_refresh_token(self, subject: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> TokenPayload:
        try:
            data = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenPayload(**data)
        except JWTError as exc:
            raise ValueError("Invalid or expired token") from exc

    def is_access_token(self, token: str) -> bool:
        payload = self.decode_token(token)
        return payload.type == "access"
