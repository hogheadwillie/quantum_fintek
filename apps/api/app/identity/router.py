from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import get_session
from app.identity.models import ROLE_ADMIN, User
from app.identity.repository import TenantScopedUserRepository
from app.identity.schemas import LoginRequest, TokenResponse, UserResponse
from app.identity.service import AuthenticationError, AuthenticationService


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Organization administrator role required",
    )


def create_identity_router(settings: Settings) -> APIRouter:
    """Create tenant-scoped authentication routes."""

    router = APIRouter(prefix=f"{settings.api_prefix}/identity", tags=["identity"])
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/identity/login")

    def get_authentication_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> AuthenticationService:
        return AuthenticationService(
            settings=settings,
            users=TenantScopedUserRepository(session),
        )

    def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        authentication: Annotated[AuthenticationService, Depends(get_authentication_service)],
    ) -> User:
        try:
            return authentication.authenticate_token(token)
        except AuthenticationError as error:
            raise _unauthorized() from error

    def get_organization_admin(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.is_superuser and current_user.role != ROLE_ADMIN:
            raise _forbidden()
        return current_user

    @router.post("/login", response_model=TokenResponse)
    def login(
        credentials: LoginRequest,
        authentication: Annotated[AuthenticationService, Depends(get_authentication_service)],
    ) -> TokenResponse:
        user = authentication.authenticate_user(
            organization_slug=credentials.organization_slug,
            email=credentials.email,
            password=credentials.password,
        )
        if user is None:
            raise _unauthorized()

        return TokenResponse(access_token=authentication.create_user_access_token(user))

    @router.get("/me", response_model=UserResponse)
    def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        return current_user

    @router.get("/users", response_model=list[UserResponse])
    def list_users(
        administrator: Annotated[User, Depends(get_organization_admin)],
        session: Annotated[Session, Depends(get_session)],
    ) -> list[User]:
        return TenantScopedUserRepository(session).list_for_organization(
            administrator.organization_id
        )

    return router
