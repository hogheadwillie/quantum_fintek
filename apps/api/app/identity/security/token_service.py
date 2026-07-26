"""Token management foundation.

Production implementation will provide:
- JWT access tokens
- Refresh token rotation
- Token revocation
- Session binding
"""

from app.config import Settings
from app.identity.security import create_access_token, decode_access_token


class TokenService:
    """Authentication token service interface."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create_access_token(self, subject: str) -> str:
        return create_access_token(subject, self._settings)

    def decode_access_token(self, token: str) -> str:
        return decode_access_token(token, self._settings)

    def create_refresh_token(self, subject: str) -> str:
        raise NotImplementedError
