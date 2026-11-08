"""WebSocket endpoints — authenticated real-time market data stream."""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.redis import get_redis
from app.identity.security import SessionStore, TokenService
from app.identity.security.key_rotation import get_key_ring_manager

router = APIRouter(prefix="/ws", tags=["websocket"])

_SEED_PRICES = {
    "AAPL": 189.5,
    "MSFT": 415.0,
    "GOOGL": 175.2,
    "AMZN": 192.0,
    "NVDA": 875.0,
    "TSLA": 215.0,
    "JPM": 195.5,
    "GS": 472.0,
    "BTC-USD": 67_000.0,
    "ETH-USD": 3_500.0,
}


def _extract_token(websocket: WebSocket) -> str | None:
    # Prefer Authorization: Bearer … ; fallback ?token=
    auth = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return websocket.query_params.get("token")


async def _build_token_service() -> TokenService:
    settings = get_settings()
    redis_client = await get_redis()
    store = SessionStore(
        redis_client,
        prefix=settings.redis_key_prefix,
        fail_closed=settings.auth_fail_closed,
    )
    return TokenService(
        key_ring=get_key_ring_manager().ring,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        session_store=store,
        fail_closed=settings.auth_fail_closed,
    )


@router.websocket("/market-data")
async def market_data_stream(
    websocket: WebSocket,
    symbols: str = "AAPL,MSFT,GOOGL,AMZN,NVDA",
    interval_ms: int = 1000,
) -> None:
    """Stream market quotes. Requires valid access JWT (query token= or Authorization).

    Periodically re-validates denylist so logout/revocation terminates the socket.
    """
    token = _extract_token(websocket)
    if not token:
        await websocket.close(code=4401, reason="Missing access token")
        return

    try:
        tokens = await _build_token_service()
        payload = await tokens.validate_access_token(token)
    except Exception:
        await websocket.close(code=4401, reason="Invalid or revoked token")
        return

    await websocket.accept()

    settings = get_settings()
    recheck = max(5, int(settings.ws_auth_recheck_seconds))
    last_auth = asyncio.get_event_loop().time()

    current_prices: dict[str, float] = {}
    active_symbols: list[str] = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    for sym in active_symbols:
        current_prices[sym] = _SEED_PRICES.get(sym, 100.0) * (1 + random.uniform(-0.005, 0.005))

    interval = max(100, min(interval_ms, 10_000)) / 1_000

    try:
        while True:
            now_t = asyncio.get_event_loop().time()
            if now_t - last_auth >= recheck:
                try:
                    await tokens.validate_access_token(token)
                    last_auth = now_t
                except Exception:
                    await websocket.close(code=4401, reason="Token revoked or expired")
                    return

            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.0)
                msg = json.loads(raw)
                action = msg.get("action", "")
                new_syms: list[str] = [s.upper() for s in msg.get("symbols", [])]
                if action == "subscribe":
                    for sym in new_syms:
                        if sym not in active_symbols:
                            active_symbols.append(sym)
                            current_prices[sym] = _SEED_PRICES.get(sym, 100.0)
                elif action == "unsubscribe":
                    active_symbols = [s for s in active_symbols if s not in new_syms]
            except (asyncio.TimeoutError, json.JSONDecodeError, KeyError):
                pass

            quotes = []
            now = datetime.now(timezone.utc).isoformat()
            for sym in active_symbols:
                prev = current_prices.get(sym, 100.0)
                drift = 0.0001
                vol = 0.001
                current_prices[sym] = round(prev * (1 + drift + vol * random.gauss(0, 1)), 4)
                mid = current_prices[sym]
                spread = max(0.01, mid * 0.0002)
                quotes.append(
                    {
                        "symbol": sym,
                        "bid": round(mid - spread / 2, 4),
                        "ask": round(mid + spread / 2, 4),
                        "last": mid,
                        "volume": random.randint(1_000, 100_000),
                        "change_pct": round((mid / _SEED_PRICES.get(sym, mid) - 1) * 100, 3),
                        "timestamp": now,
                        "user_id": payload.sub,
                    }
                )

            await websocket.send_text(json.dumps(quotes))
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        pass
