"""Trading domain API routes — orders, positions, market data (JWT + RBAC protected)."""

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
from app.db.models import Order
from app.db.session import get_db
from app.identity.security import TokenPayload

router = APIRouter(prefix="/trading", tags=["trading"])

Trader = Depends(require_roles("analyst", "quant", "trader"))
Admin = Depends(require_roles("admin", "owner"))


# ── enums & schemas ──────────────────────────────────────────────────────────

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
    symbol: str = Field(..., min_length=1, max_length=16, description="Ticker symbol, e.g. AAPL")
    side: OrderSide
    order_type: OrderType = OrderType.market
    quantity: float = Field(..., gt=0, description="Number of units")
    limit_price: float | None = Field(None, gt=0, description="Required for limit orders")
    stop_price: float | None = Field(None, gt=0, description="Required for stop orders")
    notes: str = Field("", max_length=512)


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


# ── helpers ───────────────────────────────────────────────────────────────────

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
    )


# ── order routes ─────────────────────────────────────────────────────────────

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def place_order(
    body: PlaceOrderRequest,
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    """Place a new trading order (immediately simulates fill for market orders)."""
    if body.order_type == OrderType.limit and body.limit_price is None:
        raise HTTPException(status_code=400, detail="limit_price required for limit orders")
    if body.order_type == OrderType.stop and body.stop_price is None:
        raise HTTPException(status_code=400, detail="stop_price required for stop orders")

    # Simulate immediate fill for market orders; pending for others
    import random

    fill_price: float | None = None
    order_status = OrderStatus.pending.value

    if body.order_type == OrderType.market:
        # Simulated fill price ±0.1% around a fictional mid
        mid = round(100 + random.uniform(-5, 5), 2)
        spread = mid * 0.001
        fill_price = round(mid + (spread if body.side == OrderSide.buy else -spread), 4)
        order_status = OrderStatus.filled.value

    actor_uuid = uuid.UUID(user.sub) if user.sub else None
    order = Order(
        actor_id=actor_uuid,
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
        detail=f"symbol={order.symbol} side={order.side} qty={order.quantity} status={order.status}",
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
    """List the current user's orders (filtered optionally by symbol / status)."""
    actor_uuid = uuid.UUID(user.sub)
    stmt = (
        select(Order)
        .where(Order.actor_id == actor_uuid)
        .order_by(Order.created_at.desc())
    )
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
    """Get a single order by ID (must belong to the calling user)."""
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    actor_uuid = uuid.UUID(user.sub)
    order = await db.scalar(
        select(Order).where(Order.id == oid, Order.actor_id == actor_uuid)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return _order_to_out(order)


@router.delete("/orders/{order_id}", response_model=CancelOrderResponse)
async def cancel_order(
    order_id: str,
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> CancelOrderResponse:
    """Cancel a pending order."""
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order id")

    actor_uuid = uuid.UUID(user.sub)
    order = await db.scalar(
        select(Order).where(Order.id == oid, Order.actor_id == actor_uuid)
    )
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


# ── positions route ───────────────────────────────────────────────────────────

@router.get("/positions", response_model=PositionsResponse)
async def get_positions(
    user: TokenPayload = Trader,
    db: AsyncSession = Depends(get_db),
) -> PositionsResponse:
    """Aggregate filled orders into current positions."""
    actor_uuid = uuid.UUID(user.sub)
    rows = (
        await db.scalars(
            select(Order).where(
                Order.actor_id == actor_uuid,
                Order.status == OrderStatus.filled.value,
            )
        )
    ).all()

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


# ── market data stub ──────────────────────────────────────────────────────────

_SEED_PRICES = {
    "AAPL": 189.5, "MSFT": 415.0, "GOOGL": 175.2, "AMZN": 192.0,
    "NVDA": 875.0, "TSLA": 215.0, "JPM": 195.5, "GS": 472.0,
    "BTC-USD": 67_000.0, "ETH-USD": 3_500.0,
}


@router.get("/market-data", response_model=MarketDataResponse)
def get_market_data(
    symbols: str = Query(
        "AAPL,MSFT,GOOGL,AMZN,NVDA",
        description="Comma-separated symbols",
    ),
    _user: TokenPayload = Trader,
) -> MarketDataResponse:
    """Return simulated real-time market quotes for requested symbols."""
    import random

    now = datetime.now(timezone.utc).isoformat()
    quotes: list[MarketQuote] = []
    for sym in [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]:
        base = _SEED_PRICES.get(sym, 100.0)
        mid = round(base * (1 + random.uniform(-0.003, 0.003)), 2)
        spread = max(0.01, mid * 0.0002)
        change_pct = round(random.uniform(-2.5, 2.5), 3)
        quotes.append(
            MarketQuote(
                symbol=sym,
                bid=round(mid - spread / 2, 4),
                ask=round(mid + spread / 2, 4),
                last=mid,
                volume=random.randint(10_000, 5_000_000),
                change_pct=change_pct,
                timestamp=now,
            )
        )
    return MarketDataResponse(quotes=quotes)
