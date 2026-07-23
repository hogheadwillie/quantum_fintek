from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.identity.models import Organization, User
from app.identity.security import hash_password


def test_organization_user_relationship_and_constraints() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        organization = Organization(name="Quantum Industrial", slug="quantum-industrial")
        user = User(
            organization=organization,
            email="admin@example.com",
            password_hash=hash_password("correct horse battery staple"),
            is_superuser=True,
        )
        session.add(user)
        session.commit()

        stored = session.scalar(select(User).where(User.email == "admin@example.com"))
        assert stored is not None
        assert stored.organization.slug == "quantum-industrial"
        assert stored.is_active is True
        assert stored.is_superuser is True
