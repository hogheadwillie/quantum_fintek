"""Authentication service for tenant-scoped identity flows."""

import jwt

from app.config import Settings
from app.identity.models import User
from app.identity.repository import TenantScopedUserRepository
from app.identity.security import create_access_token, decode_access_token, verify_password


class AuthenticationError(Exception):
    """Raised when bearer-token authentication cannot resolve an active user."""


class AuthenticationService:
    """Authenticate users and bearer tokens without exposing transport concerns."""

    def __init__(self, *, settings: Settings, users: TenantScopedUserRepository) -> None:
        self._settings = settings
        self._users = users

    def authenticate_user(
        self,
        *,
        organization_slug: str,
        email: str,
        password: str,
    ) -> User | None:
        user = self._users.get_by_identity(
            organization_slug=organization_slug,
            email=email,
        )
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_user_access_token(self, user: User) -> str:
        return create_access_token(str(user.id), self._settings)

    def authenticate_token(self, token: str) -> User:
        try:
            subject = decode_access_token(token, self._settings)
        except jwt.InvalidTokenError as error:
            raise AuthenticationError("invalid bearer token") from error

        user = self._users.get_by_id(subject)
        if user is None or not user.is_active:
            raise AuthenticationError("bearer token subject is not an active user")
        return user
