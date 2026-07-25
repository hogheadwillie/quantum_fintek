from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base
from app.identity.models import Organization, User
from app.identity.repository import get_user_by_id, get_user_by_identity
from app.identity.schemas import LoginRequest, TokenResponse, UserResponse
from app.identity.security import hash_password
from app.identity.security.token_service import TokenService


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
        email="admin@example.com",
        password_hash=hash_password("correct horse battery staple"),
    )
    session.add(user)
    session.commit()

    stored = get_user_by_identity(
        session,
        organization_slug="quantum-industrial",
        email="ADMIN@EXAMPLE.COM",
    )

    assert stored is not None
    assert stored.id == user.id
    assert (
        get_user_by_identity(
            session,
            organization_slug="another-tenant",
            email="admin@example.com",
        )
        is None
    )
    assert get_user_by_id(session, str(user.id)) is user
    assert get_user_by_id(session, "not-a-uuid") is None
    assert get_user_by_id(session, str(uuid4())) is None


def test_identity_schemas_serialize_contracts(session: Session) -> None:
    organization = Organization(name="Quantum Industrial", slug="quantum-industrial")
    user = User(
        organization=organization,
        email="admin@example.com",
        password_hash="not-returned",
        is_superuser=True,
    )
    session.add(user)
    session.flush()

    login = LoginRequest(
        organization_slug=organization.slug,
        email=user.email,
        password="secret",
    )
    token = TokenResponse(access_token="signed-token")
    response = UserResponse.model_validate(user)

    assert login.organization_slug == "quantum-industrial"
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


def test_token_service_contract_is_explicitly_unimplemented() -> None:
    service = TokenService()

    with pytest.raises(NotImplementedError):
        service.create_access_token("user-123")
    with pytest.raises(NotImplementedError):
        service.create_refresh_token("user-123")
