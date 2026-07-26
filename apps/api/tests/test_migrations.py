from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine


def alembic_config(api_root: Path, database_url: str) -> Config:
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_initial_migration_creates_identity_tables(tmp_path: Path) -> None:
    api_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "identity.db"
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    config = alembic_config(api_root, database_url)

    command.upgrade(config, "head")
    engine: Engine = create_engine(database_url)

    try:
        inspector = inspect(engine)
        assert {"alembic_version", "organizations", "users"} <= set(inspector.get_table_names())
        assert {"id", "name", "slug", "created_at"} == {
            column["name"] for column in inspector.get_columns("organizations")
        }
        assert {
            "id",
            "organization_id",
            "email",
            "password_hash",
            "role",
            "is_active",
            "is_superuser",
            "created_at",
        } == {column["name"] for column in inspector.get_columns("users")}
        assert "ix_users_email" in {index["name"] for index in inspector.get_indexes("users")}
        assert "ix_users_organization_id" in {
            index["name"] for index in inspector.get_indexes("users")
        }
    finally:
        engine.dispose()

    command.downgrade(config, "base")
