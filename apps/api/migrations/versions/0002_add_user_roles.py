"""Add organization roles to users.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the organization-scoped role assigned to each user."""
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
    )
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    """Remove organization-scoped user roles."""
    op.drop_column("users", "role")
