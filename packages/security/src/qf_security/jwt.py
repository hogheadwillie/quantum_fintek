"""JWT encode / decode helpers with optional RS256 key id.

Thin wrappers around PyJWT. Stateful denylist / refresh rotation stays in ``apps/api``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


@dataclass
class JWTConfig:
    """HS256 uses ``secret_key``; RS256 uses PEM fields + ``key_id``."""

    algorithm: str = "RS256"
    secret_key: str | None = None
    private_key_pem: str | None = None
    public_key_pem: str | None = None
    key_id: str = "qf-key-1"
    access_token_expire_minutes: int = 30
    # Optional map of previous kid -> public PEM for rotation verify
    previous_public_keys: dict[str, str] | None = None

    def signing_key(self) -> str:
        if self.algorithm.upper().startswith("HS"):
            if not self.secret_key:
                raise ValueError("secret_key required for HS*")
            return self.secret_key
        if not self.private_key_pem:
            raise ValueError("private_key_pem required for RS*")
        return self.private_key_pem

    def verify_key_for_kid(self, kid: str | None) -> str:
        if self.algorithm.upper().startswith("HS"):
            if not self.secret_key:
                raise ValueError("secret_key required for HS*")
            return self.secret_key
        if kid and self.previous_public_keys and kid in self.previous_public_keys:
            return self.previous_public_keys[kid]
        if self.public_key_pem:
            return self.public_key_pem
        if self.private_key_pem:
            return self.private_key_pem
        raise ValueError("No verify key material")


def encode_token(
    payload: dict[str, Any],
    config: JWTConfig,
    expires_in: timedelta | None = None,
) -> str:
    data = dict(payload)
    if expires_in is not None:
        data["exp"] = datetime.now(timezone.utc) + expires_in
    headers = {"kid": config.key_id, "typ": "JWT"}
    return jwt.encode(
        data,
        config.signing_key(),
        algorithm=config.algorithm,
        headers=headers,
    )


def decode_token(
    token: str,
    config: JWTConfig,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg")
    if alg != config.algorithm:
        raise jwt.InvalidAlgorithmError(f"alg {alg} != {config.algorithm}")
    kid = header.get("kid")
    key = config.verify_key_for_kid(kid)
    return jwt.decode(
        token,
        key,
        algorithms=[config.algorithm],
        options=options or {},
    )
