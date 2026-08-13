"""Admin-only routes: audit log, user management, JWT rotation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.audit import log_event
from app.db.models import AuditEvent, User
from app.db.session import get_db
from app.identity.security import TokenPayload
from app.identity.security.key_rotation import get_key_ring_manager

router = APIRouter(prefix="/admin", tags=["admin"])

Admin = Depends(require_roles("admin"))


class AuditEventOut(BaseModel):
    id: str
    actor_id: str | None
    action: str
    resource: str
    detail: str
    created_at: datetime


class AuditListResponse(BaseModel):
    events: list[AuditEventOut]
    total: int
    page: int
    page_size: int


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    status: str
    created_at: datetime
    last_login: datetime | None


class UserListResponse(BaseModel):
    users: list[UserOut]
    total: int


class JwtRotateResponse(BaseModel):
    detail: str
    status: dict[str, Any]


@router.get("/audit", response_model=AuditListResponse)
async def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    action: str | None = Query(None, description="Filter by action prefix"),
    actor_id: str | None = Query(None, description="Filter by actor UUID"),
    _user: TokenPayload = Admin,
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    """Return paginated audit events (admin only)."""
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())

    if action:
        stmt = stmt.where(AuditEvent.action.startswith(action))
    if actor_id:
        try:
            actor_uuid = uuid.UUID(actor_id)
            stmt = stmt.where(AuditEvent.actor_id == actor_uuid)
        except ValueError:
            pass

    count_stmt = stmt.with_only_columns(AuditEvent.id)
    total_result = await db.scalars(count_stmt)
    total = len(total_result.all())

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    rows = (await db.scalars(stmt)).all()

    events = [
        AuditEventOut(
            id=str(ev.id),
            actor_id=str(ev.actor_id) if ev.actor_id else None,
            action=ev.action,
            resource=ev.resource,
            detail=ev.detail,
            created_at=ev.created_at,
        )
        for ev in rows
    ]
    return AuditListResponse(events=events, total=total, page=page, page_size=page_size)


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: TokenPayload = Admin,
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    """List all users (admin only)."""
    stmt = select(User).order_by(User.created_at.desc())
    count_result = await db.scalars(stmt.with_only_columns(User.id))
    total = len(count_result.all())

    offset = (page - 1) * page_size
    rows = (await db.scalars(stmt.offset(offset).limit(page_size))).all()
    users = [
        UserOut(
            id=str(u.id),
            email=u.email,
            username=u.username,
            status=u.status,
            created_at=u.created_at,
            last_login=u.last_login,
        )
        for u in rows
    ]
    return UserListResponse(users=users, total=total)


@router.get("/jwt/keys")
async def jwt_key_status(_user: TokenPayload = Admin) -> dict[str, Any]:
    """Public metadata about the JWT key ring (no private PEMs)."""
    return get_key_ring_manager().status()


@router.post("/jwt/rotate", response_model=JwtRotateResponse)
async def jwt_rotate_now(
    _user: TokenPayload = Admin,
    db: AsyncSession = Depends(get_db),
) -> JwtRotateResponse:
    """Force an RS256 key rotation (admin only)."""
    mgr = get_key_ring_manager()
    try:
        snapshot = mgr.rotate(reason="admin")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    await log_event(
        db,
        action="security.jwt.rotate",
        actor_id=_user.sub,
        resource="jwt:keyring",
        detail=(
            f"previous={snapshot.get('previous_active_kid')} "
            f"active={snapshot.get('active_kid')} count={snapshot.get('rotation_count')}"
        ),
    )
    return JwtRotateResponse(detail="JWT signing key rotated", status=snapshot)
