"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.redis import get_redis
from app.identity.security import SessionStore, TokenPayload, TokenService
from app.identity.security.jwt_keys import JWTKeyRing
from app.identity.security.key_rotation import get_key_ring_manager

bearer = HTTPBearer(auto_error=False)


def get_key_ring() -> JWTKeyRing:
    return get_key_ring_manager().ring


async def get_token_service(
    settings: Settings = Depends(get_settings),
) -> TokenService:
    redis_client = await get_redis()
    store = SessionStore(
        redis_client,
        prefix=settings.redis_key_prefix,
        fail_closed=settings.auth_fail_closed,
    )
    return TokenService(
        key_ring=get_key_ring(),
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        session_store=store,
        fail_closed=settings.auth_fail_closed,
    )


async def get_current_payload(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    tokens: TokenService = Depends(get_token_service),
) -> TokenPayload:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return await tokens.validate_access_token(creds.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_roles(*allowed: str) -> Callable:
    allowed_set = set(allowed)

    async def _checker(payload: TokenPayload = Depends(get_current_payload)) -> TokenPayload:
        roles = set(payload.roles or [])
        if "admin" in roles:
            return payload
        if roles.isdisjoint(allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(sorted(allowed_set))}",
            )
        return payload

    return _checker


def require_org_claim(optional: bool = False) -> Callable:
    """Require JWT org_id claim for tenant-scoped routes (unless platform admin)."""

    async def _checker(payload: TokenPayload = Depends(get_current_payload)) -> TokenPayload:
        roles = set(payload.roles or [])
        if "admin" in roles:
            return payload
        if not payload.org_id and not optional:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization context required (org_id claim)",
            )
        return payload

    return _checker
