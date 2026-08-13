"""JWKS document cache helpers (ETag + HTTP cache metadata)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CachedJWKS:
    """Immutable snapshot of a public JWKS document."""

    body: dict[str, Any]
    body_json: str
    etag: str
    generation: int
    active_kid: str

    @staticmethod
    def build(body: dict[str, Any], generation: int, active_kid: str) -> "CachedJWKS":
        # Canonical JSON for stable ETag
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(body_json.encode("utf-8")).hexdigest()[:32]
        etag = f'W/"jwks-{generation}-{digest}"'
        return CachedJWKS(
            body=body,
            body_json=body_json,
            etag=etag,
            generation=generation,
            active_kid=active_kid,
        )


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    """Return True if client If-None-Match validates against our ETag."""
    if not if_none_match:
        return False
    # Header may list multiple tags or *
    raw = if_none_match.strip()
    if raw == "*":
        return True
    candidates = [p.strip() for p in raw.split(",")]
    # Compare loosely (with/without weak validator prefix)
    norm = etag.strip()
    strong = norm[2:] if norm.startswith("W/") else norm
    for c in candidates:
        c = c.strip()
        if c == norm or c == strong:
            return True
        if c.startswith("W/") and c[2:] == strong:
            return True
    return False
