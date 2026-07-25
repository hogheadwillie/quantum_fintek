from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_session
from app.identity.models import Organization, User
from app.identity.security import create_access_token, hash_password
from app.main import create_app


@dataclass(frozen=True)
class IdentityApi:
    client: TestClient
    settings: Settings
    active_user_id: UUID
    inactive_user_id: UUID


@pytest.fixture
def identity_api() -> Generator[IdentityApi, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    settings = Settings(
        environment="test",
        jwt_secret=SecretStr("test-secret-with-at-least-32-bytes"),
    )
    application = create_app(settings)

    def override_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_session] = override_session

    with Session(engine) as session:
        organization = Organization(name="Quantum Industrial", slug="quantum-industrial")
        active_user = User(
            organization=organization,
            email="admin@example.com",
            password_hash=hash_password("correct horse battery staple"),
        )
        inactive_user = User(
            organization=organization,
            email="inactive@example.com",
            password_hash=hash_password("correct horse battery staple"),
            is_active=False,
        )
        session.add_all([active_user, inactive_user])
        session.commit()
        active_user_id = active_user.id
        inactive_user_id = inactive_user.id

    with TestClient(application) as client:
        yield IdentityApi(client, settings, active_user_id, inactive_user_id)


def test_login_and_current_user(identity_api: IdentityApi) -> None:
    login = identity_api.client.post(
        "/api/v1/identity/login",
        json={
            "organization_slug": "quantum-industrial",
            "email": "ADMIN@EXAMPLE.COM",
            "password": "correct horse battery staple",
        },
    )

    assert login.status_code == 200
    token = login.json()["access_token"]

    current_user = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert current_user.status_code == 200
    assert current_user.json() == {
        "id": str(identity_api.active_user_id),
        "organization_id": current_user.json()["organization_id"],
        "email": "admin@example.com",
        "is_active": True,
        "is_superuser": False,
    }
    assert "password_hash" not in current_user.json()


@pytest.mark.parametrize(
    ("email", "password", "organization_slug"),
    [
        ("admin@example.com", "wrong-password", "quantum-industrial"),
        ("missing@example.com", "wrong-password", "quantum-industrial"),
        ("inactive@example.com", "correct horse battery staple", "quantum-industrial"),
        ("admin@example.com", "correct horse battery staple", "another-tenant"),
    ],
)
def test_login_rejects_invalid_credentials(
    identity_api: IdentityApi,
    email: str,
    password: str,
    organization_slug: str,
) -> None:
    response = identity_api.client.post(
        "/api/v1/identity/login",
        json={
            "organization_slug": organization_slug,
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_invalid_and_unknown_subjects(identity_api: IdentityApi) -> None:
    invalid = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": "Bearer not-a-token"},
    )
    missing_user_token = create_access_token(str(uuid4()), identity_api.settings)
    missing = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {missing_user_token}"},
    )
    inactive_token = create_access_token(str(identity_api.inactive_user_id), identity_api.settings)
    inactive = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {inactive_token}"},
    )

    assert invalid.status_code == 401
    assert missing.status_code == 401
    assert inactive.status_code == 401
