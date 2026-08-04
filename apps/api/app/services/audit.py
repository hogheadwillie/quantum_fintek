"""Audit event helpers (CMMC-aligned activity trail)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    resource: str = "",
    detail: str = "",
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource=resource,
        detail=detail[:2000] if detail else "",
    )
    db.add(event)
    await db.flush()
    return event
