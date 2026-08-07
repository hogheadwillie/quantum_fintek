"""Audit event helpers — fire-and-forget async writes to the audit_events table."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


async def log_event(
    db: AsyncSession,
    action: str,
    *,
    actor_id: Optional[str] = None,
    resource: str = "",
    detail: str = "",
) -> None:
    """Insert an audit event row.

    Silently swallows errors so that audit failures never block business logic.
    """
    try:
        actor_uuid: Optional[uuid.UUID] = uuid.UUID(actor_id) if actor_id else None
        ev = AuditEvent(
            actor_id=actor_uuid,
            action=action,
            resource=resource,
            detail=detail,
        )
        db.add(ev)
        await db.commit()
    except Exception:  # noqa: BLE001
        # Audit failure must never crash the calling request.
        await db.rollback()
