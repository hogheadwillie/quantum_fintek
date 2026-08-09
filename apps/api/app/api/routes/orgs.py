"""Organisation management API routes."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.audit import log_event
from app.db.models import Membership, Organization, User
from app.db.session import get_db
from app.identity.security import TokenPayload

router = APIRouter(prefix="/orgs", tags=["orgs"])

Member = Depends(require_roles("user", "analyst", "quant", "trader"))
Admin = Depends(require_roles("admin", "owner"))


# ── schemas ───────────────────────────────────────────────────────────────────

class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    subscription_level: str


class MemberOut(BaseModel):
    user_id: str
    username: str
    email: str
    role: str


class OrgDetailResponse(BaseModel):
    org: OrgOut
    members: list[MemberOut]


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")


class InviteMemberRequest(BaseModel):
    email: str
    role: str = Field("member", pattern=r"^(owner|admin|analyst|quant|trader|member)$")


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|analyst|quant|trader|member)$")


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_org_or_404(db: AsyncSession, org_id: str) -> Organization:
    try:
        oid = uuid.UUID(org_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid org id")
    org = await db.scalar(select(Organization).where(Organization.id == oid))
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


async def _require_org_role(
    db: AsyncSession,
    user: TokenPayload,
    org_id: uuid.UUID,
    required: set[str],
) -> Membership:
    roles = set(user.roles or [])
    if "admin" in roles:
        # Platform admins bypass org membership checks
        membership = await db.scalar(
            select(Membership).where(
                Membership.user_id == uuid.UUID(user.sub),
                Membership.organization_id == org_id,
            )
        )
        if membership:
            return membership
        # Still return a synthetic check pass for admins
        return None  # type: ignore[return-value]
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == uuid.UUID(user.sub),
            Membership.organization_id == org_id,
        )
    )
    if membership is None or membership.role not in required:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient org role",
        )
    return membership


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[OrgOut])
async def list_my_orgs(
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> list[OrgOut]:
    """List organisations the calling user belongs to."""
    actor_uuid = uuid.UUID(user.sub)
    rows = (
        await db.scalars(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == actor_uuid)
        )
    ).all()
    return [OrgOut(id=str(o.id), name=o.name, slug=o.slug, subscription_level=o.subscription_level) for o in rows]


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: CreateOrgRequest,
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> OrgOut:
    """Create a new organisation; the creator becomes owner."""
    existing = await db.scalar(select(Organization).where(Organization.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already taken")

    org = Organization(name=body.name, slug=body.slug)
    db.add(org)
    await db.flush()

    membership = Membership(
        user_id=uuid.UUID(user.sub),
        organization_id=org.id,
        role="owner",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(org)
    await log_event(
        db,
        action="org.create",
        actor_id=user.sub,
        resource=f"org:{org.id}",
        detail=f"slug={org.slug}",
    )
    return OrgOut(id=str(org.id), name=org.name, slug=org.slug, subscription_level=org.subscription_level)


@router.get("/{org_id}", response_model=OrgDetailResponse)
async def get_org(
    org_id: str,
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> OrgDetailResponse:
    """Get org details + member list."""
    org = await _get_org_or_404(db, org_id)
    await _require_org_role(db, user, org.id, {"owner", "admin", "analyst", "quant", "trader", "member"})

    memberships = (
        await db.scalars(
            select(Membership).where(Membership.organization_id == org.id)
        )
    ).all()

    members: list[MemberOut] = []
    for m in memberships:
        u = await db.scalar(select(User).where(User.id == m.user_id))
        if u:
            members.append(MemberOut(user_id=str(u.id), username=u.username, email=u.email, role=m.role))

    return OrgDetailResponse(
        org=OrgOut(id=str(org.id), name=org.name, slug=org.slug, subscription_level=org.subscription_level),
        members=members,
    )


@router.post("/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    """Invite a registered user to the organisation by email (owner/admin only)."""
    org = await _get_org_or_404(db, org_id)
    await _require_org_role(db, user, org.id, {"owner", "admin"})

    target = await db.scalar(select(User).where(User.email == body.email.lower()))
    if target is None:
        raise HTTPException(status_code=404, detail="No user with that email")

    existing = await db.scalar(
        select(Membership).where(
            Membership.user_id == target.id,
            Membership.organization_id == org.id,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")

    m = Membership(user_id=target.id, organization_id=org.id, role=body.role)
    db.add(m)
    await db.commit()
    await log_event(
        db,
        action="org.member.invite",
        actor_id=user.sub,
        resource=f"org:{org.id}/user:{target.id}",
        detail=f"role={body.role}",
    )
    return MemberOut(user_id=str(target.id), username=target.username, email=target.email, role=body.role)


@router.patch("/{org_id}/members/{member_user_id}", response_model=MemberOut)
async def update_member_role(
    org_id: str,
    member_user_id: str,
    body: UpdateRoleRequest,
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> MemberOut:
    """Update a member's role within the org (owner/admin only)."""
    org = await _get_org_or_404(db, org_id)
    await _require_org_role(db, user, org.id, {"owner", "admin"})

    try:
        target_uuid = uuid.UUID(member_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == target_uuid,
            Membership.organization_id == org.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    target = await db.scalar(select(User).where(User.id == target_uuid))
    membership.role = body.role
    await db.commit()
    await log_event(
        db,
        action="org.member.role_update",
        actor_id=user.sub,
        resource=f"org:{org.id}/user:{target_uuid}",
        detail=f"new_role={body.role}",
    )
    return MemberOut(
        user_id=member_user_id,
        username=target.username if target else "",
        email=target.email if target else "",
        role=body.role,
    )


@router.delete("/{org_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: str,
    member_user_id: str,
    user: TokenPayload = Member,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a member from the org."""
    org = await _get_org_or_404(db, org_id)
    await _require_org_role(db, user, org.id, {"owner", "admin"})

    try:
        target_uuid = uuid.UUID(member_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user id")

    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == target_uuid,
            Membership.organization_id == org.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(membership)
    await db.commit()
    await log_event(
        db,
        action="org.member.remove",
        actor_id=user.sub,
        resource=f"org:{org.id}/user:{target_uuid}",
        detail="",
    )
