"""Tests for qf_security."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from qf_security import JWTConfig, decode_token, encode_token, hash_password, verify_password


def test_hash_and_verify():
    pw = "s3cur3P@ss!"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h)
    assert not verify_password("wrong", h)


def test_encode_decode_token_hs256():
    cfg = JWTConfig(secret_key="test-secret", algorithm="HS256")
    payload = {"sub": "user123", "roles": ["analyst"]}
    token = encode_token(payload, cfg, expires_in=timedelta(minutes=5))
    decoded = decode_token(token, cfg)
    assert decoded["sub"] == "user123"
    assert decoded["roles"] == ["analyst"]


def test_expired_token_raises():
    cfg = JWTConfig(secret_key="test-secret", algorithm="HS256")
    token = encode_token({"sub": "x"}, cfg, expires_in=timedelta(seconds=-1))
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token, cfg)


def _rsa_pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


def test_rs256_encode_decode_and_rotation():
    priv1, pub1 = _rsa_pem_pair()
    priv2, pub2 = _rsa_pem_pair()

    cfg_old = JWTConfig(
        algorithm="RS256",
        private_key_pem=priv1,
        public_key_pem=pub1,
        key_id="qf-key-1",
    )
    token_old = encode_token({"sub": "u1"}, cfg_old, expires_in=timedelta(minutes=5))

    # After rotation: sign with key-2, still verify key-1 tokens
    cfg_new = JWTConfig(
        algorithm="RS256",
        private_key_pem=priv2,
        public_key_pem=pub2,
        key_id="qf-key-2",
        previous_public_keys={"qf-key-1": pub1},
    )
    token_new = encode_token({"sub": "u2"}, cfg_new, expires_in=timedelta(minutes=5))

    assert decode_token(token_old, cfg_new)["sub"] == "u1"
    assert decode_token(token_new, cfg_new)["sub"] == "u2"

    header = pyjwt.get_unverified_header(token_new)
    assert header["kid"] == "qf-key-2"
    assert header["alg"] == "RS256"
