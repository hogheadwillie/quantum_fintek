"""Authentication routes: register, login, refresh, logout, me, verify."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_payload, get_token_service
from app.core.security import hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.identity.security import TokenPayload, TokenService

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_optional = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class LogoutResponse(BaseModel):
    detail: str
    access_jti_denied: str
    subject: str
    refresh_revoked: bool = False
    refresh_tokens_revoked: int | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    status: str
    roles: list[str] = []


class TokenRequest(BaseModel):
    subject: str = Field(..., min_length=1)
    org_id: str | None = None
    roles: list[str] = []


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserResponse:
    existing = await db.scalar(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already registered")

    user = User(
        email=body.email.lower(),
        username=body.username,
        password_hash=hash_password(body.password),
        status="active",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        status=user.status,
        roles=["user", "analyst"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not active")

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    roles = ["user", "analyst"]
    access = tokens.create_access_token(str(user.id), roles=roles)
    refresh = await tokens.create_refresh_token(str(user.id), roles=roles)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshRequest,
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    try:
        access, refresh = await tokens.rotate_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    body: LogoutRequest | None = None,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
    tokens: TokenService = Depends(get_token_service),
) -> LogoutResponse:
    """Deny current access JTI in Redis; optionally revoke refresh token."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        result = await tokens.logout(
            access_token=creds.credentials,
            refresh_token=(body.refresh_token if body else None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return LogoutResponse(
        detail="Logged out",
        access_jti_denied=result["access_jti_denied"],
        subject=result["subject"],
        refresh_revoked=bool(result.get("refresh_revoked")),
    )


@router.post("/logout-all", response_model=LogoutResponse)
async def logout_all(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
    tokens: TokenService = Depends(get_token_service),
) -> LogoutResponse:
    """Deny current access token and revoke all refresh tokens for the subject."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        result = await tokens.logout_all(access_token=creds.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exp
    return LogoutResponse(
        detail="Logged out from all sessions",
        access_jti_denied=result["access_jti_denied"],
        subject=result["subject"],
        refresh_tokens_revoked=int(result.get("refresh_tokens_revoked") or 0),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    payload: TokenPayload = Depends(get_current_payload),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await db.scalar(select(User).where(User.id == payload.sub))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        status=user.status,
        roles=list(payload.roles or []),
    )


@router.get("/verify", status_code=status.HTTP_200_OK)
async def verify_for_forward_auth(
    payload: TokenPayload = Depends(get_current_payload),
) -> Response:
    """Traefik ForwardAuth endpoint — also respects Redis access denylist."""
    response = Response(status_code=status.HTTP_200_OK, content=b"")
    response.headers["X-QF-User-Id"] = payload.sub
    response.headers["X-QF-Roles"] = ",".join(payload.roles or [])
    if payload.org_id:
        response.headers["X-QF-Org-Id"] = payload.org_id
    return response


@router.post("/token", response_model=TokenResponse)
async def issue_tokens(
    body: TokenRequest,
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    """Dev-only token minting without password."""
    roles = body.roles or ["user", "analyst"]
    access = tokens.create_access_token(body.subject, org_id=body.org_id, roles=roles)
    refresh = await tokens.create_refresh_token(body.subject, roles=roles, org_id=body.org_id)
    return TokenResponse(access_token=access, refresh_token=refresh)
