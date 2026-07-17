"""Token management foundation.

Production implementation will provide:
- JWT access tokens
- Refresh token rotation
- Token revocation
- Session binding
"""


class TokenService:
    """Authentication token service interface."""

    def create_access_token(self, subject: str) -> str:
        raise NotImplementedError

    def create_refresh_token(self, subject: str) -> str:
        raise NotImplementedError
