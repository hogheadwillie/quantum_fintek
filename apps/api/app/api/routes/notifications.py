"""Notifications API — in-app alert centre.

Notifications are stored per-user in Redis as a capped sorted-set
(score = Unix timestamp, value = JSON blob).  The endpoint supports:

  GET  /notifications         list (newest-first, default 50)
  POST /notifications         create (admin/system use; validated payload)
  POST /notifications/mark-read        mark one or all as read
  DELETE /notifications/{nid}  delete one notification

Each notification JSON shape:
  {
    "id":         str (UUID hex),
    "user_id":    str,
    "title":      str,
    "body":       str,
    "level":      "info" | "warning" | "error" | "success",
    "read":       bool,
    "created_at": ISO-8601 str
  }
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.core.redis import get_redis
from app.identity.security import TokenPayload

router = APIRouter(prefix="/notifications", tags=["notifications"])

_Member = Depends(require_roles("user", "analyst", "quant", "trader", "admin", "owner"))

# Redis key pattern
_KEY = "qf:notif:{user_id}"
_CAP = 200  # max notifications per user


# ── schemas ───────────────────────────────────────────────────────────────────

NotifLevel = Literal["info", "warning", "error", "success"]


class NotificationOut(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    level: NotifLevel = "info"
    read: bool = False
    created_at: str


class CreateNotificationRequest(BaseModel):
    user_id: str = Field(..., description="Target user UUID")
    title: str = Field(..., min_length=1, max_length=160)
    body: str = Field("", max_length=1024)
    level: NotifLevel = "info"


class MarkReadRequest(BaseModel):
    id: str | None = Field(None, description="Notification id; omit to mark all read")


class NotificationListResponse(BaseModel):
    notifications: list[NotificationOut]
    total: int
    unread: int


# ── helpers ───────────────────────────────────────────────────────────────────

def _key(user_id: str) -> str:
    return _KEY.format(user_id=user_id)


async def _get_all(redis_client, user_id: str) -> list[dict]:
    raw_items = await redis_client.zrevrange(_key(user_id), 0, -1)
    result = []
    for raw in raw_items:
        try:
            result.append(json.loads(raw))
        except Exception:
            pass
    return result


async def _save(redis_client, user_id: str, notif: dict) -> None:
    ts = datetime.fromisoformat(notif["created_at"]).timestamp()
    k = _key(user_id)
    await redis_client.zadd(k, {json.dumps(notif): ts})
    # Trim to cap (keep highest scores = newest)
    count = await redis_client.zcard(k)
    if count > _CAP:
        await redis_client.zremrangebyrank(k, 0, count - _CAP - 1)


async def _replace_all(redis_client, user_id: str, notifs: list[dict]) -> None:
    k = _key(user_id)
    await redis_client.delete(k)
    if notifs:
        mapping = {
            json.dumps(n): datetime.fromisoformat(n["created_at"]).timestamp()
            for n in notifs
        }
        await redis_client.zadd(k, mapping)


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    user: TokenPayload = _Member,
) -> NotificationListResponse:
    redis_client = await get_redis()
    all_notifs = await _get_all(redis_client, user.sub)
    if unread_only:
        all_notifs = [n for n in all_notifs if not n.get("read")]
    total = len(all_notifs)
    unread = sum(1 for n in all_notifs if not n.get("read"))
    page = all_notifs[offset: offset + limit]
    return NotificationListResponse(
        notifications=[NotificationOut(**n) for n in page],
        total=total,
        unread=unread,
    )


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: CreateNotificationRequest,
    user: TokenPayload = Depends(require_roles("admin", "owner")),
) -> NotificationOut:
    """Create a notification for a specific user (admin-only)."""
    redis_client = await get_redis()
    now = datetime.now(timezone.utc).isoformat()
    notif: dict = {
        "id": uuid.uuid4().hex,
        "user_id": body.user_id,
        "title": body.title,
        "body": body.body,
        "level": body.level,
        "read": False,
        "created_at": now,
    }
    await _save(redis_client, body.user_id, notif)
    return NotificationOut(**notif)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    body: MarkReadRequest,
    user: TokenPayload = _Member,
) -> None:
    """Mark one notification (by id) or all notifications as read."""
    redis_client = await get_redis()
    all_notifs = await _get_all(redis_client, user.sub)
    if body.id:
        updated = [
            {**n, "read": True} if n["id"] == body.id else n
            for n in all_notifs
        ]
    else:
        updated = [{**n, "read": True} for n in all_notifs]
    await _replace_all(redis_client, user.sub, updated)


@router.delete("/{notif_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notif_id: str,
    user: TokenPayload = _Member,
) -> None:
    """Delete a notification."""
    redis_client = await get_redis()
    all_notifs = await _get_all(redis_client, user.sub)
    filtered = [n for n in all_notifs if n["id"] != notif_id]
    if len(filtered) == len(all_notifs):
        raise HTTPException(status_code=404, detail="Notification not found")
    await _replace_all(redis_client, user.sub, filtered)
