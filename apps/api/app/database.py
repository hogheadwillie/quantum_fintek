from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session to request handlers."""
    with SessionLocal() as session:
        yield session
