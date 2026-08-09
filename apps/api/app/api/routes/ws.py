"""WebSocket endpoints — real-time market data stream."""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


@router.websocket("/market-data")
async def market_data_stream(
    websocket: WebSocket,
    symbols: str = "AAPL,MSFT,GOOGL,AMZN,NVDA",
    interval_ms: int = 1000,
) -> None:
    """Stream simulated real-time market quotes.

    Connect with:
        ws://localhost:8000/ws/market-data?symbols=AAPL,MSFT&interval_ms=500

    Each message is a JSON array of quote objects.
    The client can send ``{"action": "subscribe", "symbols": ["TSLA", "NVDA"]}``
    or ``{"action": "unsubscribe", "symbols": ["TSLA"]}`` to update the
    subscription at any time.
    """
    await websocket.accept()

    # Initialise prices from seed (random walk)
    current_prices: dict[str, float] = {}
    active_symbols: list[str] = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    for sym in active_symbols:
        current_prices[sym] = _SEED_PRICES.get(sym, 100.0) * (1 + random.uniform(-0.005, 0.005))

    interval = max(100, min(interval_ms, 10_000)) / 1_000  # clamp 100 ms – 10 s

    try:
        while True:
            # Non-blocking check for incoming control messages
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
                # Geometric Brownian Motion tick
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
                    }
                )

            await websocket.send_text(json.dumps(quotes))
            await asyncio.sleep(interval)

    except WebSocketDisconnect:
        pass
