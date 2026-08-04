"""CMMC / compliance evidence stubs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.models import AuditEvent
from app.db.session import get_db
from app.identity.security import TokenPayload

router = APIRouter(prefix="/compliance", tags=["compliance"])

Admin = Depends(require_roles("admin", "owner"))


class EvidenceItem(BaseModel):
    control: str
    title: str
    status: str
    evidence: str
    collected_at: str


class EvidenceResponse(BaseModel):
    framework: str = "CMMC L2 (subset)"
    items: list[EvidenceItem]
    audit_event_count: int


@router.get("/evidence", response_model=EvidenceResponse)
async def list_evidence(
    _user: TokenPayload = Admin,
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    """Return machine-readable evidence pointers for a CMMC control subset."""
    now = datetime.now(timezone.utc).isoformat()
    count = await db.scalar(select(func.count()).select_from(AuditEvent)) or 0

    items = [
        EvidenceItem(
            control="AC.L2-3.1.1",
            title="Authorized access control",
            status="partial",
            evidence="JWT + RBAC on /quant and /ai; register/login audit events",
            collected_at=now,
        ),
        EvidenceItem(
            control="AU.L2-3.3.1",
            title="System auditing",
            status="partial",
            evidence=f"audit_events table; {count} recorded events",
            collected_at=now,
        ),
        EvidenceItem(
            control="IA.L2-3.5.1",
            title="Identification and authentication",
            status="partial",
            evidence="bcrypt password hashes; Redis-backed refresh token rotation",
            collected_at=now,
        ),
        EvidenceItem(
            control="SC.L2-3.13.1",
            title="Boundary protection",
            status="partial",
            evidence="Traefik edge (TLS overlay, rate limits, ForwardAuth optional)",
            collected_at=now,
        ),
    ]
    return EvidenceResponse(items=items, audit_event_count=int(count))
