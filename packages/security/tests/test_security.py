"""Tests for qf_security."""

from __future__ import annotations

from datetime import timedelta

import pytest

from qf_security import JWTConfig, decode_token, encode_token, hash_password, verify_password


def test_hash_and_verify():
    pw = "s3cur3P@ss!"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)


def test_encode_decode_token():
    cfg = JWTConfig(secret_key="test-secret")
    payload = {"sub": "user123", "roles": ["analyst"]}
    token = encode_token(payload, cfg, expires_in=timedelta(minutes=5))
    decoded = decode_token(token, cfg)
    assert decoded["sub"] == "user123"
    assert decoded["roles"] == ["analyst"]


def test_expired_token_raises():
    import jwt as pyjwt
    cfg = JWTConfig(secret_key="test-secret")
    token = encode_token({"sub": "x"}, cfg, expires_in=timedelta(seconds=-1))
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token, cfg)
