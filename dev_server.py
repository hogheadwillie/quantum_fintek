"""
dev_server.py — zero-infrastructure local launcher for QuantumFintek API.

Uses SQLite (aiosqlite) + fakeredis so no external services are required.

Usage:
    python dev_server.py

URLs:
    Web console  → http://localhost:3000  (start separately: cd apps/web && npm run dev)
    API          → http://localhost:8000
    Swagger UI   → http://localhost:8000/docs
"""

import sys
import os

# ── 1. Path setup ────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))
for pkg in ["quant-core", "ai-intel", "security", "zos-bridge"]:
    src = os.path.join(ROOT, "packages", pkg, "src")
    if os.path.isdir(src):
        sys.path.insert(0, src)

# ── 2. Environment ───────────────────────────────────────────────────────────
DB_PATH = os.path.join(ROOT, "dev_local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("SECRET_KEY", "dev-secret-key-not-for-production-1234567890abcd")
# SQLite URL — override whatever is in .env
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000")
os.environ.setdefault("REDIS_MODE", "standalone")
os.environ.setdefault("REDIS_KEY_PREFIX", "qf")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

# ── 3. Patch SQLAlchemy to use SQLite ────────────────────────────────────────
from sqlalchemy.ext.asyncio import (        # noqa: E402
    create_async_engine, async_sessionmaker, AsyncSession
)
from sqlalchemy.pool import StaticPool       # noqa: E402

_engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

import app.db.session as _session_mod        # noqa: E402
_session_mod.engine = _engine
_session_mod.AsyncSessionLocal = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)

async def _init_db_sqlite() -> None:
    """Create all tables directly — skip Alembic (SQLite-incompatible migrations)."""
    import app.db.models  # noqa: F401  — registers ORM metadata
    from app.db.base import Base

    # SQLite doesn't support UUID natively; patch column types before DDL
    from sqlalchemy import String
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    import sqlalchemy.types as types

    class _UUIDStr(types.TypeDecorator):
        """Store UUID as VARCHAR(36) in SQLite."""
        impl = String(36)
        cache_ok = True

        def process_bind_param(self, value, dialect):
            return str(value) if value is not None else None

        def process_result_value(self, value, dialect):
            import uuid
            return uuid.UUID(value) if value else None

    # Replace UUID columns in all mapped tables with the SQLite-compatible type
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()

    async with _engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True)
        )

_session_mod.init_db = _init_db_sqlite

# ── 4. Patch Redis with fakeredis ─────────────────────────────────────────────
import fakeredis.aioredis as _fakeredis      # noqa: E402
import app.core.redis as _redis_mod          # noqa: E402

_fake_client = _fakeredis.FakeRedis(decode_responses=True)

async def _get_redis():
    return _fake_client

async def _close_redis():
    pass

_redis_mod.get_redis = _get_redis
_redis_mod.close_redis = _close_redis
_redis_mod._client = _fake_client

# Also patch the lifespan close_redis reference
import app.main as _main_mod                 # noqa: E402
_main_mod.close_redis = _close_redis

# ── 5. Launch ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    from app.main import app  # noqa: F401

    print()
    print("=" * 62)
    print("  QuantumFintek API  —  dev mode (SQLite + fakeredis)")
    print("=" * 62)
    print(f"  Database : {DB_PATH}")
    print(f"  API      : http://localhost:8000")
    print(f"  Swagger  : http://localhost:8000/docs")
    print(f"  Health   : http://localhost:8000/health")
    print("=" * 62)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
