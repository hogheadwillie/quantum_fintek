"""Async SQLAlchemy engine and session."""

from collections.abc import AsyncGenerator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_migrations() -> None:
    """Apply Alembic migrations to head (sync wrapper for startup)."""
    root = Path(__file__).resolve().parents[2]  # apps/api
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


async def init_db() -> None:
    # Run migrations in a thread to avoid blocking the event loop heavily
    import asyncio

    await asyncio.to_thread(run_migrations)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
