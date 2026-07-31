"""Authentication routes (dev-friendly token issuance)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import get_token_service
from app.identity.security import TokenService

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    subject: str = Field(..., min_length=1, examples=["demo-user"])
    org_id: str | None = None
    roles: list[str] = []


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/token", response_model=TokenResponse)
async def issue_tokens(
    body: TokenRequest,
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    """Issue access + refresh tokens for a subject (replace with real login later)."""
    access = tokens.create_access_token(body.subject, org_id=body.org_id, roles=body.roles)
    refresh = await tokens.create_refresh_token(body.subject)
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
