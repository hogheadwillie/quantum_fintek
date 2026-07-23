import jwt
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.identity.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("incorrect", password_hash)


def test_access_token_round_trip() -> None:
    settings = Settings(
        environment="test",
        jwt_secret=SecretStr("test-secret-with-sufficient-entropy"),
    )

    token = create_access_token("user-123", settings)

    assert decode_access_token(token, settings) == "user-123"


def test_access_token_rejects_wrong_secret() -> None:
    issuer = Settings(environment="test", jwt_secret=SecretStr("issuer-secret"))
    verifier = Settings(environment="test", jwt_secret=SecretStr("verifier-secret"))
    token = create_access_token("user-123", issuer)

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, verifier)
