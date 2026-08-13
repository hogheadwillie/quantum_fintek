"""RS256 (and HS256-dev) JWT key ring with rotation support.

Active key signs new tokens (``kid`` in JWT header).
Verification accepts the active public key plus any previous public keys
still in the rotation window so in-flight tokens remain valid.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from jose import jwk
from jose.backends.base import Key
from jose.exceptions import JWKError


def _normalize_pem(value: str) -> str:
    """Accept literal PEM or escaped newlines from env/.env files."""
    if not value:
        return ""
    text = value.strip()
    if "\\n" in text and "-----BEGIN" in text:
        text = text.replace("\\n", "\n")
    return text.strip()


def _b64url_uint(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class KeyMaterial:
    kid: str
    algorithm: str
    private_pem: str | None = None
    public_pem: str | None = None
    symmetric_secret: str | None = None

    def signing_key(self) -> str:
        if self.algorithm.startswith("HS"):
            if not self.symmetric_secret:
                raise ValueError(f"HS key {self.kid} missing secret")
            return self.symmetric_secret
        if not self.private_pem:
            raise ValueError(f"Signing key {self.kid} has no private PEM")
        return self.private_pem

    def verify_key(self) -> str:
        if self.algorithm.startswith("HS"):
            if not self.symmetric_secret:
                raise ValueError(f"HS key {self.kid} missing secret")
            return self.symmetric_secret
        if self.public_pem:
            return self.public_pem
        if self.private_pem:
            # Derive public from private via jose when only private is configured
            return self.private_pem
        raise ValueError(f"Verify key {self.kid} has no public material")


@dataclass
class JWTKeyRing:
    """Active signer + verification key set keyed by ``kid``."""

    algorithm: str
    active_kid: str
    keys: dict[str, KeyMaterial] = field(default_factory=dict)

    def get_active(self) -> KeyMaterial:
        try:
            return self.keys[self.active_kid]
        except KeyError as exc:
            raise ValueError(f"Active kid {self.active_kid!r} not in key ring") from exc

    def get_for_verify(self, kid: str | None) -> KeyMaterial:
        if kid and kid in self.keys:
            return self.keys[kid]
        # Legacy tokens without kid: only allow if single HS key or active
        if kid is None and len(self.keys) == 1:
            return next(iter(self.keys.values()))
        if kid is None and self.active_kid in self.keys:
            return self.keys[self.active_kid]
        raise ValueError(f"Unknown or missing JWT kid: {kid!r}")

    def allowed_algorithms(self) -> list[str]:
        return [self.algorithm]

    def jwks(self) -> dict[str, Any]:
        """Public JWKS for RS* keys (no private material)."""
        out: list[dict[str, Any]] = []
        for kid, mat in self.keys.items():
            if not mat.algorithm.startswith("RS"):
                continue
            pem = mat.public_pem or mat.private_pem
            if not pem:
                continue
            try:
                key_obj: Key = jwk.construct(pem, algorithm=mat.algorithm)
                data = key_obj.to_dict()
            except (JWKError, Exception):
                # Fallback: cryptography export
                data = _rsa_public_jwk_from_pem(pem)
            data["kid"] = kid
            data["use"] = "sig"
            data["alg"] = mat.algorithm
            # Never expose private components
            data.pop("d", None)
            data.pop("p", None)
            data.pop("q", None)
            data.pop("dp", None)
            data.pop("dq", None)
            data.pop("qi", None)
            out.append(data)
        return {"keys": out}


def _rsa_public_jwk_from_pem(pem: str) -> dict[str, Any]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    loaded = serialization.load_pem_private_key(
        pem.encode("utf-8"), password=None, backend=default_backend()
    ) if "PRIVATE" in pem else serialization.load_pem_public_key(
        pem.encode("utf-8"), backend=default_backend()
    )
    if hasattr(loaded, "public_key"):
        pub = loaded.public_key()
    else:
        pub = loaded
    numbers = pub.public_numbers()
    n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "n": _b64url_uint(n),
        "e": _b64url_uint(e),
    }


def build_key_ring(
    *,
    algorithm: str,
    secret_key: str,
    private_pem: str = "",
    public_pem: str = "",
    active_kid: str = "",
    previous_public_keys_json: str = "",
    app_env: str = "development",
) -> JWTKeyRing:
    """Build ring from settings.

    Production + RS256 requires private/public PEM.
    Development may fall back to HS256 with ``secret_key``.
    """
    algorithm = (algorithm or "RS256").upper()
    private_pem = _normalize_pem(private_pem)
    public_pem = _normalize_pem(public_pem)
    active_kid = (active_kid or "").strip() or "qf-key-1"

    keys: dict[str, KeyMaterial] = {}

    if algorithm.startswith("RS"):
        if not private_pem:
            if app_env.lower() in {"production", "prod", "staging"}:
                raise ValueError(
                    "JWT_PRIVATE_KEY_PEM is required for RS256 in production/staging"
                )
            # Dev fallback: HS256 so local boot works without key files
            algorithm = "HS256"
            keys[active_kid] = KeyMaterial(
                kid=active_kid,
                algorithm="HS256",
                symmetric_secret=secret_key,
            )
            return JWTKeyRing(algorithm="HS256", active_kid=active_kid, keys=keys)

        if not public_pem and private_pem:
            # Public can be derived at verify time from private; still prefer explicit public
            public_pem = ""

        keys[active_kid] = KeyMaterial(
            kid=active_kid,
            algorithm=algorithm,
            private_pem=private_pem,
            public_pem=public_pem or None,
        )

        # Previous keys: JSON object {"kid": "-----BEGIN PUBLIC KEY-----..."}
        prev_raw = (previous_public_keys_json or "").strip()
        if prev_raw:
            try:
                prev_map = json.loads(prev_raw)
            except json.JSONDecodeError as exc:
                raise ValueError("JWT_PREVIOUS_PUBLIC_KEYS_JSON must be valid JSON object") from exc
            if not isinstance(prev_map, dict):
                raise ValueError("JWT_PREVIOUS_PUBLIC_KEYS_JSON must be a JSON object of kid->PEM")
            for kid, pem in prev_map.items():
                kid_s = str(kid).strip()
                if not kid_s or kid_s == active_kid:
                    continue
                pem_s = _normalize_pem(str(pem))
                if not pem_s:
                    continue
                keys[kid_s] = KeyMaterial(
                    kid=kid_s,
                    algorithm=algorithm,
                    public_pem=pem_s,
                )

        return JWTKeyRing(algorithm=algorithm, active_kid=active_kid, keys=keys)

    # Explicit HS*
    if app_env.lower() in {"production", "prod"} and algorithm.startswith("HS"):
        raise ValueError("HS* JWT algorithms are not allowed when APP_ENV is production")

    if not secret_key or secret_key.startswith("change-me"):
        if app_env.lower() in {"production", "prod", "staging"}:
            raise ValueError("SECRET_KEY must be set to a strong value outside development")

    keys[active_kid] = KeyMaterial(
        kid=active_kid,
        algorithm=algorithm,
        symmetric_secret=secret_key,
    )
    return JWTKeyRing(algorithm=algorithm, active_kid=active_kid, keys=keys)
