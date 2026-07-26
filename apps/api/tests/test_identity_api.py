from collections.abc import Generator
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
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
    organization_id: UUID
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
            email="Admin@Example.COM",
            password_hash=hash_password("correct horse battery staple"),
        )
        inactive_user = User(
            organization=organization,
            email="inactive@example.com",
            password_hash=hash_password("correct horse battery staple"),
            is_active=False,
        )
        session.add_all([active_user, inactive_user])
        session.flush()
        organization_id = organization.id
        active_user_id = active_user.id
        inactive_user_id = inactive_user.id
        session.commit()

    with TestClient(application) as client:
        yield IdentityApi(client, settings, organization_id, active_user_id, inactive_user_id)


def login(
    identity_api: IdentityApi,
    *,
    email: str = " ADMIN@EXAMPLE.COM ",
    password: str = "correct horse battery staple",
    organization_slug: str = "quantum-industrial",
) -> Response:
    return cast(
        Response,
        identity_api.client.post(
            "/api/v1/identity/login",
            json={
                "organization_slug": organization_slug,
                "email": email,
                "password": password,
            },
        ),
    )


def test_login_returns_bearer_token_for_normalized_email(identity_api: IdentityApi) -> None:
    response = login(identity_api)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert isinstance(response.json()["access_token"], str)


def test_login_rejects_invalid_password(identity_api: IdentityApi) -> None:
    response = login(identity_api, password="wrong-password")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_unknown_tenant(identity_api: IdentityApi) -> None:
    response = login(identity_api, organization_slug="another-tenant")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_inactive_user(identity_api: IdentityApi) -> None:
    response = login(identity_api, email="inactive@example.com")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_returns_authenticated_user(identity_api: IdentityApi) -> None:
    token = login(identity_api).json()["access_token"]

    response = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(identity_api.active_user_id),
        "organization_id": str(identity_api.organization_id),
        "email": "admin@example.com",
        "is_active": True,
        "is_superuser": False,
    }
    assert "password_hash" not in response.json()


def test_current_user_rejects_invalid_token(identity_api: IdentityApi) -> None:
    response = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_unknown_subject(identity_api: IdentityApi) -> None:
    token = create_access_token(str(uuid4()), identity_api.settings)

    response = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_current_user_rejects_inactive_user(identity_api: IdentityApi) -> None:
    token = create_access_token(str(identity_api.inactive_user_id), identity_api.settings)

    response = identity_api.client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
