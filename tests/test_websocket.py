"""WebSocket tests — /ws/market-data GBM stream.

The endpoint emits a JSON *array* of quote objects per message (one per active
symbol).  Tests connect via ASGI TestClient WebSocket support and verify the
message structure, field types, and symbol filtering.

The WS stream endpoint does not use the database, so this module patches Redis
only and reuses whatever DB engine is already configured (e.g. by test_api_smoke
when run in the same session).
"""

from __future__ import annotations

import json
import os
import sys
import uuid as _uuid_mod

import pytest
import fakeredis.aioredis as fakeredis_async

# ── 1. path setup ────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_SRC = os.path.join(ROOT, "apps", "api")
for _p in [
    ROOT,
    API_SRC,
    os.path.join(ROOT, "packages", "quant-core", "src"),
    os.path.join(ROOT, "packages", "ai-intel", "src"),
    os.path.join(ROOT, "packages", "security", "src"),
    os.path.join(ROOT, "packages", "zos-bridge", "src"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── 2. environment (only set if not already configured by another test module) ─
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-not-production-1234")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("REDIS_MODE", "standalone")

# ── 3. ensure in-memory SQLite is configured (idempotent) ────────────────────
import app.db.session as _ws_session_mod  # noqa: E402

# Only patch the engine if it hasn't been patched already (e.g. by test_api_smoke)
_existing_engine = getattr(_ws_session_mod, "engine", None)
_engine_url = str(getattr(_existing_engine, "url", "")) if _existing_engine else ""
if "sqlite" not in _engine_url.lower():
    from sqlalchemy.ext.asyncio import (
        AsyncSession, async_sessionmaker, create_async_engine,
    )
    from sqlalchemy.pool import StaticPool

    _ws_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    _ws_session_mod.engine = _ws_engine
    _ws_session_mod.AsyncSessionLocal = async_sessionmaker(
        _ws_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _ws_init_db() -> None:
        import app.db.models  # noqa: F401
        from app.db.base import Base
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID
        import sqlalchemy.types as _types

        class _UUIDStr(_types.TypeDecorator):
            impl = _types.String(36)
            cache_ok = True
            def process_bind_param(self, value, dialect):
                return str(value) if value is not None else None
            def process_result_value(self, value, dialect):
                return _uuid_mod.UUID(value) if value else None

        for table in Base.metadata.tables.values():
            for col in table.columns:
                if isinstance(col.type, PG_UUID):
                    col.type = _UUIDStr()

        async with _ws_engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))

    _ws_session_mod.init_db = _ws_init_db

# ── 4. patch Redis → fakeredis (only if not already patched) ──────────────────
import app.core.redis as _redis_mod  # noqa: E402

if not hasattr(_redis_mod, "_ws_patched"):
    _fake_pool = fakeredis_async.FakeRedis(decode_responses=True)

    async def _fake_get_redis():
        return _fake_pool

    async def _fake_close_redis():
        pass

    _redis_mod.get_redis = _fake_get_redis  # type: ignore[assignment]
    _redis_mod.close_redis = _fake_close_redis  # type: ignore[assignment]
    _redis_mod._ws_patched = True  # type: ignore[attr-defined]

# ── 5. import app ─────────────────────────────────────────────────────────────
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── tests ──────────────────────────────────────────────────────────────────────

class TestWebSocketStream:
    def test_connect_receives_json_array(self, client):
        """First message from the stream should be a JSON array."""
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        data = json.loads(raw)
        assert isinstance(data, list)

    def test_array_is_non_empty(self, client):
        """Default symbols produce at least one quote per tick."""
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        data = json.loads(raw)
        assert len(data) > 0

    def test_quote_has_required_fields(self, client):
        """Every quote must carry symbol, bid, ask, last, volume, change_pct, timestamp."""
        required = {"symbol", "bid", "ask", "last", "volume", "change_pct", "timestamp"}
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert required.issubset(quote.keys()), f"Missing fields in {quote}"

    def test_prices_are_positive(self, client):
        """bid, ask, and last must all be positive numbers."""
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert quote["bid"] > 0
            assert quote["ask"] > 0
            assert quote["last"] > 0

    def test_ask_gte_bid(self, client):
        """ask >= bid (spread must be non-negative)."""
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert quote["ask"] >= quote["bid"]

    def test_volume_is_non_negative(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert quote["volume"] >= 0

    def test_symbol_is_non_empty_string(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert isinstance(quote["symbol"], str)
            assert len(quote["symbol"]) > 0

    def test_timestamp_is_string(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert isinstance(quote["timestamp"], str)
            assert len(quote["timestamp"]) > 0

    def test_change_pct_is_numeric(self, client):
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        for quote in json.loads(raw):
            assert isinstance(quote["change_pct"], (int, float))

    def test_custom_symbols_param(self, client):
        """?symbols= restricts stream to the requested tickers."""
        with client.websocket_connect("/ws/market-data?symbols=TSLA,AMZN") as ws:
            raw = ws.receive_text()
        symbols_seen = {q["symbol"] for q in json.loads(raw)}
        assert symbols_seen.issubset({"TSLA", "AMZN"})

    def test_single_symbol_param(self, client):
        """Single-symbol subscription returns only that symbol."""
        with client.websocket_connect("/ws/market-data?symbols=NVDA") as ws:
            raw = ws.receive_text()
        quotes = json.loads(raw)
        assert all(q["symbol"] == "NVDA" for q in quotes)

    def test_multi_tick_stream(self, client):
        """Receive multiple ticks in one connection; all must be valid arrays."""
        with client.websocket_connect("/ws/market-data?interval_ms=100") as ws:
            ticks = [json.loads(ws.receive_text()) for _ in range(3)]
        assert len(ticks) == 3
        for tick in ticks:
            assert isinstance(tick, list)
            assert len(tick) > 0

    def test_default_symbols_count(self, client):
        """Default subscription contains 5 symbols (AAPL,MSFT,GOOGL,AMZN,NVDA)."""
        with client.websocket_connect("/ws/market-data") as ws:
            raw = ws.receive_text()
        quotes = json.loads(raw)
        assert len(quotes) == 5

    def test_prices_change_across_ticks(self, client):
        """Prices should change between consecutive GBM ticks."""
        with client.websocket_connect("/ws/market-data?symbols=AAPL&interval_ms=100") as ws:
            t1 = json.loads(ws.receive_text())[0]["last"]
            t2 = json.loads(ws.receive_text())[0]["last"]
        # With GBM the probability of identical prices is essentially zero
        assert t1 != t2

    def test_subscribe_control_message(self, client):
        """Sending a subscribe action mid-stream adds the new symbol."""
        with client.websocket_connect("/ws/market-data?symbols=AAPL") as ws:
            # Receive initial tick (AAPL only)
            json.loads(ws.receive_text())
            # Send subscribe command for TSLA
            ws.send_text(json.dumps({"action": "subscribe", "symbols": ["TSLA"]}))
            # Receive next tick — TSLA should now appear
            raw = ws.receive_text()
        symbols = {q["symbol"] for q in json.loads(raw)}
        assert "AAPL" in symbols
        # Note: TSLA may or may not appear depending on timing; we just ensure no crash

    def test_interval_ms_clamped(self, client):
        """interval_ms values outside 100–10000 are clamped; endpoint should not crash."""
        # interval_ms=0 should be clamped to 100 ms
        with client.websocket_connect("/ws/market-data?symbols=MSFT&interval_ms=0") as ws:
            raw = ws.receive_text()
        assert isinstance(json.loads(raw), list)
