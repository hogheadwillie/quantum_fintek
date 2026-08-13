"""Automated RS256 JWT key rotation.

- Generates new RSA key pairs
- Promotes active signing key (kid)
- Retains previous *public* keys for verify overlap
- Persists state to a local JSON store (private keys never leave the host/volume)
- Optional background scheduler + admin-triggered rotate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.identity.security.jwt_keys import (
    JWTKeyRing,
    KeyMaterial,
    build_key_ring,
    _normalize_pem,
)

logger = logging.getLogger("quantum_fintek.jwt.rotation")


def generate_rsa_keypair(bits: int = 2048) -> tuple[str, str]:
    """Return (private_pem, public_pem) PKCS8 / SubjectPublicKeyInfo."""
    key = rsa.generate_private_key(
        public_exponent=65537, key_size=bits, backend=default_backend()
    )
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _new_kid(prefix: str = "qf-key") -> str:
    # sortable unique id: prefix-YYYYmmddHHMMSS-hex
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    suffix = os.urandom(3).hex()
    return f"{prefix}-{ts}-{suffix}"


@dataclass
class RotationState:
    algorithm: str = "RS256"
    active_kid: str = ""
    # kid -> {private_pem?, public_pem, created_at, retired_at?}
    keys: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_rotated_at: str | None = None
    rotation_count: int = 0

    def to_key_ring(self) -> JWTKeyRing:
        materials: dict[str, KeyMaterial] = {}
        for kid, meta in self.keys.items():
            materials[kid] = KeyMaterial(
                kid=kid,
                algorithm=self.algorithm,
                private_pem=meta.get("private_pem"),
                public_pem=meta.get("public_pem"),
            )
        if not self.active_kid or self.active_kid not in materials:
            raise ValueError("RotationState has no active signing key")
        return JWTKeyRing(
            algorithm=self.algorithm,
            active_kid=self.active_kid,
            keys=materials,
        )

    def public_snapshot(self) -> dict[str, Any]:
        """Safe status for admin API (no private PEMs)."""
        return {
            "algorithm": self.algorithm,
            "active_kid": self.active_kid,
            "last_rotated_at": self.last_rotated_at,
            "rotation_count": self.rotation_count,
            "keys": [
                {
                    "kid": kid,
                    "has_private": bool(meta.get("private_pem")),
                    "has_public": bool(meta.get("public_pem")),
                    "created_at": meta.get("created_at"),
                    "retired_at": meta.get("retired_at"),
                    "active": kid == self.active_kid,
                }
                for kid, meta in sorted(self.keys.items(), key=lambda x: x[0])
            ],
        }


class KeyRingManager:
    """Process-wide mutable JWT key ring with rotation."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ring: JWTKeyRing | None = None
        self._state: RotationState | None = None
        self._store_path: Path | None = None
        self._max_previous: int = 2
        self._key_bits: int = 2048
        self._kid_prefix: str = "qf-key"
        self._scheduler_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    @property
    def ring(self) -> JWTKeyRing:
        with self._lock:
            if self._ring is None:
                raise RuntimeError("KeyRingManager not initialized")
            return self._ring

    @property
    def state(self) -> RotationState:
        with self._lock:
            if self._state is None:
                raise RuntimeError("KeyRingManager not initialized")
            return self._state

    def initialize_from_settings(
        self,
        *,
        algorithm: str,
        secret_key: str,
        private_pem: str,
        public_pem: str,
        active_kid: str,
        previous_public_keys_json: str,
        app_env: str,
        store_path: str = "",
        max_previous_keys: int = 2,
        key_bits: int = 2048,
        kid_prefix: str = "qf-key",
        auto_bootstrap: bool = True,
    ) -> JWTKeyRing:
        """Load store if present, else env PEMs, else bootstrap RSA (non-prod)."""
        self._max_previous = max(0, int(max_previous_keys))
        self._key_bits = int(key_bits)
        self._kid_prefix = kid_prefix or "qf-key"
        self._store_path = Path(store_path).expanduser() if store_path else None

        if self._store_path and self._store_path.is_file():
            state = self._load_store(self._store_path)
            ring = state.to_key_ring()
            with self._lock:
                self._state = state
                self._ring = ring
            logger.info(
                "JWT key ring loaded from store path=%s active_kid=%s keys=%d",
                self._store_path,
                state.active_kid,
                len(state.keys),
            )
            return ring

        # Build from environment
        try:
            ring = build_key_ring(
                algorithm=algorithm,
                secret_key=secret_key,
                private_pem=private_pem,
                public_pem=public_pem,
                active_kid=active_kid,
                previous_public_keys_json=previous_public_keys_json,
                app_env=app_env,
            )
        except ValueError:
            if not auto_bootstrap or app_env.lower() in {"production", "prod"}:
                raise
            # Bootstrap a fresh RSA ring for local/staging convenience
            ring = self._bootstrap_rsa_ring()
            state = self._state_from_ring(ring)
            with self._lock:
                self._state = state
                self._ring = ring
            if self._store_path:
                self._save_store(self._store_path, state)
            logger.warning(
                "Bootstrapped ephemeral RS256 key kid=%s (set JWT_PRIVATE_KEY_PEM or store for prod)",
                ring.active_kid,
            )
            return ring

        state = self._state_from_ring(ring)
        with self._lock:
            self._state = state
            self._ring = ring
        if self._store_path and ring.algorithm.startswith("RS"):
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_store(self._store_path, state)
        return ring

    def _bootstrap_rsa_ring(self) -> JWTKeyRing:
        kid = _new_kid(self._kid_prefix)
        priv, pub = generate_rsa_keypair(self._key_bits)
        mat = KeyMaterial(kid=kid, algorithm="RS256", private_pem=priv, public_pem=pub)
        return JWTKeyRing(algorithm="RS256", active_kid=kid, keys={kid: mat})

    def _state_from_ring(self, ring: JWTKeyRing) -> RotationState:
        now = datetime.now(timezone.utc).isoformat()
        keys: dict[str, dict[str, Any]] = {}
        for kid, mat in ring.keys.items():
            keys[kid] = {
                "private_pem": mat.private_pem,
                "public_pem": mat.public_pem,
                "created_at": now,
                "retired_at": None if kid == ring.active_kid else now,
            }
        return RotationState(
            algorithm=ring.algorithm,
            active_kid=ring.active_kid,
            keys=keys,
            last_rotated_at=None,
            rotation_count=0,
        )

    def rotate(self, reason: str = "manual") -> dict[str, Any]:
        """Generate a new active RSA key; demote previous to verify-only."""
        with self._lock:
            if self._ring is None or self._state is None:
                raise RuntimeError("KeyRingManager not initialized")
            if not self._ring.algorithm.startswith("RS"):
                raise ValueError("Automated rotation requires RS* algorithm (not HS256 fallback)")

            old_kid = self._ring.active_kid
            new_kid = _new_kid(self._kid_prefix)
            priv, pub = generate_rsa_keypair(self._key_bits)
            now = datetime.now(timezone.utc).isoformat()

            # Retire old active: drop private from memory after promote (keep public)
            if old_kid in self._state.keys:
                self._state.keys[old_kid]["retired_at"] = now
                # Keep private briefly only if needed; prefer strip private for retired
                self._state.keys[old_kid]["private_pem"] = None

            self._state.keys[new_kid] = {
                "private_pem": priv,
                "public_pem": pub,
                "created_at": now,
                "retired_at": None,
            }
            self._state.active_kid = new_kid
            self._state.last_rotated_at = now
            self._state.rotation_count += 1

            # Prune oldest retired publics beyond max_previous
            self._prune_previous_locked()

            self._ring = self._state.to_key_ring()
            if self._store_path:
                self._save_store(self._store_path, self._state)

            snapshot = self._state.public_snapshot()
            snapshot["reason"] = reason
            snapshot["previous_active_kid"] = old_kid
            logger.info(
                "JWT key rotated reason=%s old_kid=%s new_kid=%s retained=%d",
                reason,
                old_kid,
                new_kid,
                len(self._state.keys),
            )
            return snapshot

    def _prune_previous_locked(self) -> None:
        assert self._state is not None
        active = self._state.active_kid
        retired = [
            (kid, meta)
            for kid, meta in self._state.keys.items()
            if kid != active
        ]
        # Sort by retired_at / created_at ascending (oldest first)
        def sort_key(item: tuple[str, dict[str, Any]]) -> str:
            meta = item[1]
            return str(meta.get("retired_at") or meta.get("created_at") or "")

        retired.sort(key=sort_key)
        excess = len(retired) - self._max_previous
        for i in range(max(0, excess)):
            kid = retired[i][0]
            del self._state.keys[kid]
            logger.info("Pruned expired JWT verify key kid=%s", kid)

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._state is None:
                return {"initialized": False}
            data = self._state.public_snapshot()
            data["initialized"] = True
            data["store_path"] = str(self._store_path) if self._store_path else None
            data["max_previous_keys"] = self._max_previous
            return data

    def _load_store(self, path: Path) -> RotationState:
        raw = json.loads(path.read_text(encoding="utf-8"))
        keys = raw.get("keys") or {}
        # Normalize PEMs
        for kid, meta in keys.items():
            if meta.get("private_pem"):
                meta["private_pem"] = _normalize_pem(meta["private_pem"])
            if meta.get("public_pem"):
                meta["public_pem"] = _normalize_pem(meta["public_pem"])
        return RotationState(
            algorithm=str(raw.get("algorithm") or "RS256"),
            active_kid=str(raw["active_kid"]),
            keys=keys,
            last_rotated_at=raw.get("last_rotated_at"),
            rotation_count=int(raw.get("rotation_count") or 0),
        )

    def _save_store(self, path: Path, state: RotationState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "algorithm": state.algorithm,
            "active_kid": state.active_kid,
            "keys": state.keys,
            "last_rotated_at": state.last_rotated_at,
            "rotation_count": state.rotation_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    async def start_scheduler(self, interval_seconds: int) -> None:
        """Background rotation loop. interval_seconds <= 0 disables."""
        if interval_seconds <= 0:
            logger.info("JWT auto-rotation scheduler disabled")
            return
        if self._scheduler_task and not self._scheduler_task.done():
            return
        self._stop_event = asyncio.Event()

        async def _loop() -> None:
            logger.info("JWT auto-rotation scheduler started interval_s=%s", interval_seconds)
            assert self._stop_event is not None
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                    break  # stop requested
                except asyncio.TimeoutError:
                    pass
                try:
                    self.rotate(reason="scheduled")
                except Exception:
                    logger.exception("Scheduled JWT rotation failed")

        self._scheduler_task = asyncio.create_task(_loop(), name="jwt-key-rotation")

    async def stop_scheduler(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._scheduler_task:
            try:
                await asyncio.wait_for(self._scheduler_task, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._scheduler_task.cancel()
            self._scheduler_task = None
        logger.info("JWT auto-rotation scheduler stopped")


# Process singleton
_manager = KeyRingManager()


def get_key_ring_manager() -> KeyRingManager:
    return _manager
