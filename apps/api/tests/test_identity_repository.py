from collections.abc import Generator
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.config import Settings
from app.database import Base
from app.identity.models import Organization, User
from app.identity.repository import (
    TenantScopedUserRepository,
    get_user_by_id,
    get_user_by_identity,
)
from app.identity.schemas import LoginRequest, TokenResponse, UserResponse
from app.identity.security import hash_password
from app.identity.security.token_service import TokenService
from app.identity.service import AuthenticationError, AuthenticationService


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_identity_repository_is_tenant_scoped(session: Session) -> None:
    organization = Organization(name="Quantum Industrial", slug="quantum-industrial")
    user = User(
        organization=organization,
        email=" Admin@Example.COM ",
        password_hash=hash_password("correct horse battery staple"),
    )
    session.add(user)
    session.commit()
    repository = TenantScopedUserRepository(session)

    stored = repository.get_by_identity(
        organization_slug="quantum-industrial",
        email="ADMIN@EXAMPLE.COM",
    )

    assert stored is not None
    assert stored.id == user.id
    assert stored.email == "admin@example.com"
    assert (
        repository.get_by_identity(
            organization_slug="another-tenant",
            email="admin@example.com",
        )
        is None
    )
    assert (
        get_user_by_identity(
            session,
            organization_slug="quantum-industrial",
            email="admin@example.com",
        )
        is user
    )
    assert get_user_by_id(session, user.id) is user
    assert get_user_by_id(session, "not-a-uuid") is None
    assert get_user_by_id(session, str(uuid4())) is None


def test_authentication_service_accepts_only_active_users(session: Session) -> None:
    settings = Settings(
        environment="test",
        jwt_secret=SecretStr("test-secret-with-at-least-32-bytes"),
    )
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
    service = AuthenticationService(
        settings=settings,
        users=TenantScopedUserRepository(session),
    )

    authenticated = service.authenticate_user(
        organization_slug="quantum-industrial",
        email="ADMIN@example.com",
        password="correct horse battery staple",
    )

    assert authenticated is active_user
    assert (
        service.authenticate_user(
            organization_slug="quantum-industrial",
            email="admin@example.com",
            password="wrong-password",
        )
        is None
    )
    assert (
        service.authenticate_user(
            organization_slug="quantum-industrial",
            email="inactive@example.com",
            password="correct horse battery staple",
        )
        is None
    )
    assert service.authenticate_token(service.create_user_access_token(active_user)) is active_user
    with pytest.raises(AuthenticationError):
        service.authenticate_token(service.create_user_access_token(inactive_user))


def test_identity_schemas_serialize_contracts(session: Session) -> None:
    organization = Organization(name="Quantum Industrial", slug="quantum-industrial")
    user = User(
        organization=organization,
        email="Admin@Example.COM",
        password_hash="not-returned",
        is_superuser=True,
    )
    session.add(user)
    session.flush()

    login = LoginRequest(
        organization_slug=organization.slug,
        email=" ADMIN@EXAMPLE.COM ",
        password="secret",
    )
    token = TokenResponse(access_token="signed-token")
    response = UserResponse.model_validate(user)

    assert login.organization_slug == "quantum-industrial"
    assert login.email == "admin@example.com"
    assert token.token_type == "bearer"
    assert response.email == "admin@example.com"
    assert response.is_superuser is True
    assert "password_hash" not in response.model_dump()


def test_database_session_dependency_yields_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite+pysqlite://")
    factory = sessionmaker(bind=engine, class_=Session)
    monkeypatch.setattr(database, "SessionLocal", factory)

    dependency = database.get_session()
    yielded = next(dependency)

    assert isinstance(yielded, Session)
    dependency.close()


def test_token_service_creates_and_decodes_access_tokens() -> None:
    settings = Settings(
        environment="test",
        jwt_secret=SecretStr("test-secret-with-at-least-32-bytes"),
    )
    service = TokenService(settings)

    token = service.create_access_token("user-123")

    assert service.decode_access_token(token) == "user-123"
    with pytest.raises(NotImplementedError):
        service.create_refresh_token("user-123")
