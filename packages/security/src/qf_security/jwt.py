"""JWT encode / decode helpers.

These are thin, stateless wrappers around PyJWT.  The heavy stateful logic
(refresh token rotation, Redis denylist) stays in ``apps/api``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


@dataclass
class JWTConfig:
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


def encode_token(
    payload: dict[str, Any],
    config: JWTConfig,
    expires_in: timedelta | None = None,
) -> str:
    """Encode a JWT with the given payload and expiry.

    If *expires_in* is None, the payload's existing ``exp`` is used as-is.
    """
    data = dict(payload)
    if expires_in is not None:
        data["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(data, config.secret_key, algorithm=config.algorithm)


def decode_token(
    token: str,
    config: JWTConfig,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decode and verify a JWT.

    Raises ``jwt.PyJWTError`` on invalid / expired tokens.
    """
    return jwt.decode(
        token,
        config.secret_key,
        algorithms=[config.algorithm],
        options=options or {},
    )
