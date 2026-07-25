from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_session
from app.identity.models import User
from app.identity.repository import get_user_by_id, get_user_by_identity
from app.identity.schemas import LoginRequest, TokenResponse, UserResponse
from app.identity.security import create_access_token, decode_access_token, verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/identity/login")
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid authentication credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_identity_router(settings: Settings) -> APIRouter:
    """Create tenant-scoped authentication routes."""

    router = APIRouter(prefix=f"{settings.api_prefix}/identity", tags=["identity"])

    def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        session: Annotated[Session, Depends(get_session)],
    ) -> User:
        try:
            subject = decode_access_token(token, settings)
        except jwt.InvalidTokenError as error:
            raise _UNAUTHORIZED from error

        user = get_user_by_id(session, subject)
        if user is None or not user.is_active:
            raise _UNAUTHORIZED
        return user

    @router.post("/login", response_model=TokenResponse)
    def login(
        credentials: LoginRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> TokenResponse:
        user = get_user_by_identity(
            session,
            organization_slug=credentials.organization_slug,
            email=credentials.email,
        )
        if (
            user is None
            or not user.is_active
            or not verify_password(credentials.password, user.password_hash)
        ):
            raise _UNAUTHORIZED

        return TokenResponse(access_token=create_access_token(str(user.id), settings))

    @router.get("/me", response_model=UserResponse)
    def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        return current_user

    return router
