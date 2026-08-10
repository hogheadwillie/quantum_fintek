"""add mainframe_audit_events table

Revision ID: 0003_add_mainframe_audit
Revises: 0002_add_orders
Create Date: 2025-01-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_add_mainframe_audit"
down_revision = "0002_add_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mainframe_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lpar_name", sa.String(8), nullable=False, server_default=""),
        sa.Column("sysplex_name", sa.String(8), nullable=False, server_default=""),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("resource", sa.String(255), nullable=False, server_default=""),
        sa.Column("action", sa.String(128), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="success"),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mainframe_audit_actor_id",  "mainframe_audit_events", ["actor_id"])
    op.create_index("ix_mainframe_audit_lpar_name",  "mainframe_audit_events", ["lpar_name"])
    op.create_index("ix_mainframe_audit_event_type", "mainframe_audit_events", ["event_type"])
    op.create_index("ix_mainframe_audit_created_at", "mainframe_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_mainframe_audit_created_at", table_name="mainframe_audit_events")
    op.drop_index("ix_mainframe_audit_event_type",  table_name="mainframe_audit_events")
    op.drop_index("ix_mainframe_audit_lpar_name",   table_name="mainframe_audit_events")
    op.drop_index("ix_mainframe_audit_actor_id",    table_name="mainframe_audit_events")
    op.drop_table("mainframe_audit_events")
