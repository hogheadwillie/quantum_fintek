"""Trading domain API routes — orders, positions, market data (JWT + RBAC + org scope)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.audit import log_event
from app.db.models import Membership, Order
from app.db.session import get_db
from app.identity.security import TokenPayload

router = APIRouter(prefix="/trading", tags=["trading"])

Trader = Depends(require_roles("analyst", "quant", "trader"))


class OrderSide(str, Enum):
    buy = "buy"
    sell = "sell"


class OrderType(str, Enum):
    market = "market"
    limit = "limit"
    stop = "stop"


class OrderStatus(str, Enum):
    pending = "pending"
    filled = "filled"
    cancelled = "cancelled"
    rejected = "rejected"


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    side: OrderSide
    order_type: OrderType = OrderType.market
    quantity: float = Field(..., gt=0)
    limit_price: float | None = Field(None, gt=0)
    stop_price: float | None = Field(None, gt=0)
    notes: str = Field("", max_length=512)
    org_id: str | None = Field(None, description="Optional org; defaults to JWT org_id claim")


class OrderOut(BaseModel):
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    limit_price: float | None
    stop_price: float | None
    status: str
    fill_price: float | None
    notes: str
    created_at: datetime
    updated_at: datetime
    actor_id: str
    org_id: str | None = None


class OrderListResponse(BaseModel):
    orders: list[OrderOut]
    total: int
    page: int
    page_size: int


class CancelOrderResponse(BaseModel):
    id: str
    status: str
    detail: str


class PositionItem(BaseModel):
    symbol: str
    quantity: float
    avg_fill_price: float
    current_value_estimate: float
    side: str


class PositionsResponse(BaseModel):
    positions: list[PositionItem]
    total_symbols: int


class MarketQuote(BaseModel):
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    change_pct: float
    timestamp: str


class MarketDataResponse(BaseModel):
    quotes: list[MarketQuote]


def _order_to_out(o: Order) -> OrderOut:
    return OrderOut(
        id=str(o.id),
        symbol=o.symbol,
        side=o.side,
        order_type=o.order_type,
        quantity=o.quantity,
        limit_price=o.limit_price,
        stop_price=o.stop_price,
        status=o.status,
        fill_price=o.fill_price,
        notes=o.notes,
        created_at=o.created_at,
        updated_at=o.updated_at,
        actor_id=str(o.actor_id) if o.actor_id else "",
        org_id=str(o.org_id) if o.org_id else None,
    )


async def _assert_org_membership(
    db: AsyncSession,
    user: TokenPayload,
    org_uuid: uuid.UUID,
) -> None:
    """Prevent IDOR: user must be member of org (platform admin exempt)."""
    if "admin" in set(user.roles or []):
        return
    m = await db.scalar(
        select(Membership).where(
            Membership.user_id == uuid.UUID(user.sub),
            Membership.organization_id == org_uuid,
        )
    )
    if m is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")


def _resolve_org_id(user: TokenPayload, body_org: str | None) -> uuid.UUID | None:
    raw = body_org or user.org_id
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid org_id")


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    body: PlaceOrderRequest,
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    if body.order_type == OrderType.limit and body.limit_price is None:
        raise HTTPException(status_code=400, detail="limit_price required for limit orders")
    if body.order_type == OrderType.stop and body.stop_price is None:
        raise HTTPException(status_code=400, detail="stop_price required for stop orders")

    org_uuid = _resolve_org_id(user, body.org_id)
    if org_uuid is not None:
        await _assert_org_membership(db, user, org_uuid)

    import random

    fill_price: float | None = None
    order_status = OrderStatus.pending.value
    if body.order_type == OrderType.market:
        mid = round(100 + random.uniform(-5, 5), 2)
        spread = mid * 0.001
        fill_price = round(mid + (spread if body.side == OrderSide.buy else -spread), 4)
        order_status = OrderStatus.filled.value

    actor_uuid = uuid.UUID(user.sub) if user.sub else None
    order = Order(
        actor_id=actor_uuid,
        org_id=org_uuid,
        symbol=body.symbol.upper(),
        side=body.side.value,
        order_type=body.order_type.value,
        quantity=body.quantity,
        limit_price=body.limit_price,
        stop_price=body.stop_price,
        status=order_status,
        fill_price=fill_price,
        notes=body.notes,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    await log_event(
        db,
        action="trading.order.place",
        actor_id=user.sub,
        resource=f"order:{order.id}",
        detail=(
            f"symbol={order.symbol} side={order.side} qty={order.quantity} "
            f"status={order.status} org_id={order.org_id}"
        ),
    )
    return _order_to_out(order)


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    symbol: str | None = Query(None),
    order_status: str | None = Query(None, alias="status"),
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    actor_uuid = uuid.UUID(user.sub)
    stmt = select(Order).where(Order.actor_id == actor_uuid).order_by(Order.created_at.desc())

    # Tenant isolation: when JWT carries org_id, only that org's rows
    if user.org_id and "admin" not in set(user.roles or []):
        try:
            org_uuid = uuid.UUID(user.org_id)
            stmt = stmt.where(Order.org_id == org_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid org_id in token")

    if symbol:
        stmt = stmt.where(Order.symbol == symbol.upper())
    if order_status:
        stmt = stmt.where(Order.status == order_status)

    count_rows = await db.scalars(stmt.with_only_columns(Order.id))
    total = len(count_rows.all())
    offset = (page - 1) * page_size
    rows = (await db.scalars(stmt.offset(offset).limit(page_size))).all()
    return OrderListResponse(
        orders=[_order_to_out(o) for o in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    actor_uuid = uuid.UUID(user.sub)
    conditions = [Order.id == oid, Order.actor_id == actor_uuid]
    if user.org_id and "admin" not in set(user.roles or []):
        try:
            conditions.append(Order.org_id == uuid.UUID(user.org_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid org_id in token")

    order = await db.scalar(select(Order).where(*conditions))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_out(order)


@router.delete("/orders/{order_id}", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: str,
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> CancelOrderResponse:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    actor_uuid = uuid.UUID(user.sub)
    conditions = [Order.id == oid, Order.actor_id == actor_uuid]
    if user.org_id and "admin" not in set(user.roles or []):
        try:
            conditions.append(Order.org_id == uuid.UUID(user.org_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid org_id in token")

    order = await db.scalar(select(Order).where(*conditions))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Cannot cancel order with status '{order.status}'")

    order.status = OrderStatus.cancelled.value
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await log_event(
        db,
        action="trading.order.cancel",
        actor_id=user.sub,
        resource=f"order:{order.id}",
        detail=f"symbol={order.symbol}",
    )
    return CancelOrderResponse(id=order_id, status="cancelled", detail="Order cancelled successfully")


@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> PositionsResponse:
    actor_uuid = uuid.UUID(user.sub)
    conditions = [Order.actor_id == actor_uuid, Order.status == OrderStatus.filled.value]
    if user.org_id and "admin" not in set(user.roles or []):
        try:
            conditions.append(Order.org_id == uuid.UUID(user.org_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid org_id in token")

    rows = (await db.scalars(select(Order).where(*conditions))).all()

    pos: dict[str, dict] = {}
    for o in rows:
        sym = o.symbol
        if sym not in pos:
            pos[sym] = {"buy_qty": 0.0, "sell_qty": 0.0, "cost_basis": 0.0}
        fp = o.fill_price or 0.0
        if o.side == OrderSide.buy.value:
            pos[sym]["buy_qty"] += o.quantity
            pos[sym]["cost_basis"] += o.quantity * fp
        else:
            pos[sym]["sell_qty"] += o.quantity
            pos[sym]["cost_basis"] -= o.quantity * fp

    positions: list[PositionItem] = []
    for sym, data in pos.items():
        net_qty = data["buy_qty"] - data["sell_qty"]
        if abs(net_qty) < 1e-9:
            continue
        avg = data["cost_basis"] / net_qty if net_qty != 0 else 0.0
        positions.append(
            PositionItem(
                symbol=sym,
                quantity=round(net_qty, 6),
                avg_fill_price=round(avg, 4),
                current_value_estimate=round(net_qty * avg, 2),
                side="long" if net_qty > 0 else "short",
            )
        )

    return PositionsResponse(positions=positions, total_symbols=len(positions))


_SEED_PRICES = {
    "AAPL": 189.5, "MSFT": 415.0, "GOOGL": 175.2, "AMZN": 192.0,
    "NVDA": 875.0, "TSLA": 215.0, "JPM": 195.5, "GS": 472.0,
    "BTC-USD": 67_000.0, "ETH-USD": 3_500.0,
}


@router.get("/market-data", response_model=MarketDataResponse)
def get_market_data(
    symbols: str = Query("AAPL,MSFT,GOOGL,AMZN,NVDA"),
    _user: TokenPayload = Trader,
) -> MarketDataResponse:
    import random

    now = datetime.now(timezone.utc).isoformat()
    quotes: list[MarketQuote] = []
    for sym in [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]:
        base = _SEED_PRICES.get(sym, 100.0)
        mid = round(base * (1 + random.uniform(-0.003, 0.003)), 2)
        spread = max(0.01, mid * 0.0002)
        quotes.append(
            MarketQuote(
                symbol=sym,
                bid=round(mid - spread / 2, 4),
                ask=round(mid + spread / 2, 4),
                last=mid,
                volume=random.randint(10_000, 5_000_000),
                change_pct=round(random.uniform(-2.5, 2.5), 3),
                timestamp=now,
            )
        )
    return MarketDataResponse(quotes=quotes)
