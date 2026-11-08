"""Add org_id to orders for tenant isolation.

Revision ID: 0004_order_org_id
Revises: 0003_add_mainframe_audit
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_order_org_id"
down_revision = "0003_add_mainframe_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_orders_org_id", "orders", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_org_id", table_name="orders")
    op.drop_column("orders", "org_id")
