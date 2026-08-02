"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.redis import get_redis
from app.identity.security import SessionStore, TokenPayload, TokenService

bearer = HTTPBearer(auto_error=False)


async def get_token_service(
    settings: Settings = Depends(get_settings),
) -> TokenService:
    redis = await get_redis()
    store = SessionStore(redis)
    return TokenService(
        secret_key=settings.secret_key,
        algorithm=settings.jwt_algorithm,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        session_store=store,
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
    """Dependency factory: require at least one of the given roles (or admin)."""

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
