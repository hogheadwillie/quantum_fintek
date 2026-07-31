"""Authentication routes: register, login, refresh, me."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_payload, get_token_service
from app.core.security import hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.identity.security import TokenPayload, TokenService

router = APIRouter(prefix="/auth", tags=["auth"])


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


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    status: str


class TokenRequest(BaseModel):
    """Dev helper: issue tokens without password (disabled in production)."""

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
    return UserResponse(id=str(user.id), email=user.email, username=user.username, status=user.status)


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

    access = tokens.create_access_token(str(user.id), roles=["user"])
    refresh = await tokens.create_refresh_token(str(user.id))
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


@router.get("/me", response_model=UserResponse)
async def me(
    payload: TokenPayload = Depends(get_current_payload),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await db.scalar(select(User).where(User.id == payload.sub))
    if user is None:
        # payload.sub may be a non-UUID dev subject
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(id=str(user.id), email=user.email, username=user.username, status=user.status)


@router.post("/token", response_model=TokenResponse)
async def issue_tokens(
    body: TokenRequest,
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    """Dev-only token minting without password."""
    access = tokens.create_access_token(body.subject, org_id=body.org_id, roles=body.roles or ["user"])
    refresh = await tokens.create_refresh_token(body.subject)
    return TokenResponse(access_token=access, refresh_token=refresh)
