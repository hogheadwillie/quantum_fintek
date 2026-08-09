"""FastAPI in-process smoke tests using TestClient.

No real database or Redis required — the app is patched with SQLite +
fakeredis exactly as dev_server.py does it, so these tests run in CI
with zero infrastructure.
"""

from __future__ import annotations

import sys
import os
import uuid

import pytest

# ── 1. path setup (mirrors dev_server.py) ────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))
for _pkg in ["quant-core", "ai-intel", "security", "zos-bridge"]:
    _src = os.path.join(ROOT, "packages", _pkg, "src")
    if os.path.isdir(_src):
        sys.path.insert(0, _src)

# ── 2. environment ────────────────────────────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-not-production-1234")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("REDIS_MODE", "standalone")
os.environ.setdefault("REDIS_KEY_PREFIX", "qftest")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# ── 3. patch SQLAlchemy → in-memory SQLite ────────────────────────────────────
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.pool import StaticPool

_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

import app.db.session as _session_mod
_session_mod.engine = _engine
_session_mod.AsyncSessionLocal = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)


async def _init_db_sqlite() -> None:
    import app.db.models  # noqa: F401
    from app.db.base import Base
    from sqlalchemy import String
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    import sqlalchemy.types as types

    class _UUIDStr(types.TypeDecorator):
        impl = String(36)
        cache_ok = True
        def process_bind_param(self, value, dialect):
            return str(value) if value is not None else None
        def process_result_value(self, value, dialect):
            return uuid.UUID(value) if value else None

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()

    async with _engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))


_session_mod.init_db = _init_db_sqlite

# ── 4. patch Redis → fakeredis ────────────────────────────────────────────────
import fakeredis.aioredis as _fakeredis
import app.core.redis as _redis_mod

_fake = _fakeredis.FakeRedis(decode_responses=True)

async def _get_redis():  return _fake
async def _close_redis(): pass

_redis_mod.get_redis   = _get_redis
_redis_mod.close_redis = _close_redis
_redis_mod._client     = _fake

import app.main as _main_mod
_main_mod.close_redis = _close_redis

# ── 5. create TestClient (lifespan=True triggers startup → init_db) ──────────
from fastapi.testclient import TestClient
from app.main import app

# `with TestClient` triggers ASGI lifespan (startup/shutdown), which calls
# our patched _init_db_sqlite and creates all SQLite tables before any test.
_client_ctx = TestClient(app, raise_server_exceptions=True)
_client_ctx.__enter__()   # run lifespan startup
client = _client_ctx


# ── helpers ───────────────────────────────────────────────────────────────────

def _register_and_login(email: str = None, username: str = None) -> str:
    """Register a user and return a valid access token."""
    uid = uuid.uuid4().hex[:8]
    email    = email    or f"user_{uid}@test.com"
    username = username or f"user_{uid}"
    r = client.post("/auth/register", json={
        "email": email, "username": username, "password": "Password1!"
    })
    assert r.status_code == 201, r.text
    r2 = client.post("/auth/login", json={"email": email, "password": "Password1!"})
    assert r2.status_code == 200, r2.text
    return r2.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── health / root ─────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.8.0"

    def test_root_returns_endpoints(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "endpoints" in data
        assert "zos_health" in data["endpoints"]


# ── auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register(self):
        uid = uuid.uuid4().hex[:8]
        r = client.post("/auth/register", json={
            "email": f"reg_{uid}@test.com",
            "username": f"reg_{uid}",
            "password": "SecurePass1!",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["email"] == f"reg_{uid}@test.com"
        assert "analyst" in data["roles"]

    def test_duplicate_registration(self):
        uid = uuid.uuid4().hex[:8]
        body = {"email": f"dup_{uid}@test.com", "username": f"dup_{uid}", "password": "Pass12345!"}
        client.post("/auth/register", json=body)
        r = client.post("/auth/register", json=body)
        assert r.status_code == 409

    def test_login_returns_tokens(self):
        uid = uuid.uuid4().hex[:8]
        client.post("/auth/register", json={
            "email": f"log_{uid}@test.com", "username": f"log_{uid}", "password": "Pass12345!",
        })
        r = client.post("/auth/login", json={
            "email": f"log_{uid}@test.com", "password": "Pass12345!",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self):
        uid = uuid.uuid4().hex[:8]
        client.post("/auth/register", json={
            "email": f"wp_{uid}@test.com", "username": f"wp_{uid}", "password": "RealPass1!",
        })
        r = client.post("/auth/login", json={
            "email": f"wp_{uid}@test.com", "password": "WrongPass!",
        })
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_with_valid_token(self):
        token = _register_and_login()
        r = client.get("/auth/me", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()
        assert "email" in data
        assert "roles" in data

    def test_logout(self):
        token = _register_and_login()
        r = client.post("/auth/logout", headers=_auth(token))
        assert r.status_code == 200

    def test_token_invalid_after_logout(self):
        token = _register_and_login()
        client.post("/auth/logout", headers=_auth(token))
        r = client.get("/auth/me", headers=_auth(token))
        assert r.status_code == 401


# ── quant ─────────────────────────────────────────────────────────────────────

class TestQuantRoutes:
    @pytest.fixture(autouse=True)
    def token(self):
        self._token = _register_and_login()

    def test_optimize(self):
        r = client.post("/quant/optimize", headers=_auth(self._token), json={
            "expected_returns": [0.05, 0.07, 0.06],
            "covariance": [[0.01, 0.002, 0.001], [0.002, 0.015, 0.003], [0.001, 0.003, 0.012]],
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["weights"]) == 3
        assert abs(sum(data["weights"]) - 1.0) < 1e-6

    def test_optimize_bad_cov_shape(self):
        r = client.post("/quant/optimize", headers=_auth(self._token), json={
            "expected_returns": [0.05, 0.07],
            "covariance": [[0.01, 0.002, 0.001]],  # wrong shape
        })
        assert r.status_code == 400

    def test_risk(self):
        import random
        returns = [0.001 * (i % 7 - 3) for i in range(300)]
        r = client.post("/quant/risk", headers=_auth(self._token), json={
            "returns": returns, "confidence": 0.95,
        })
        assert r.status_code == 200
        data = r.json()
        assert "historical_var" in data
        assert "cvar" in data
        assert "volatility_annual" in data

    def test_backtest(self):
        import random
        random.seed(1)
        ret_matrix = [[random.gauss(0.001, 0.01) for _ in range(3)] for _ in range(60)]
        r = client.post("/quant/backtest", headers=_auth(self._token), json={
            "returns": ret_matrix, "weights": [0.5, 0.3, 0.2],
        })
        assert r.status_code == 200
        data = r.json()
        assert data["n_periods"] == 60
        assert len(data["equity"]) == 60

    def test_factor(self):
        import random
        random.seed(2)
        T = 50
        asset = [random.gauss(0.001, 0.01) for _ in range(T)]
        factors = [[random.gauss(0, 0.01) for _ in range(2)] for _ in range(T)]
        r = client.post("/quant/factor", headers=_auth(self._token), json={
            "asset_returns": asset,
            "factor_returns": factors,
            "factor_names": ["Mkt", "SMB"],
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["betas"]) == 2
        assert 0.0 <= data["r_squared"] <= 1.0

    def test_qubo(self):
        r = client.post("/quant/qubo", headers=_auth(self._token), json={
            "expected_returns": [0.05, 0.07, 0.06],
            "covariance": [[0.01, 0.002, 0.001], [0.002, 0.015, 0.003], [0.001, 0.003, 0.012]],
        })
        assert r.status_code == 200
        assert r.json()["n_assets"] == 3

    def test_requires_auth(self):
        r = client.post("/quant/optimize", json={
            "expected_returns": [0.05, 0.07], "covariance": [[0.01, 0.002], [0.002, 0.015]],
        })
        assert r.status_code == 401


# ── ai ────────────────────────────────────────────────────────────────────────

class TestAIRoutes:
    @pytest.fixture(autouse=True)
    def token(self):
        self._token = _register_and_login()

    def test_anomaly(self):
        import random
        random.seed(3)
        samples = [[random.gauss(0, 1) for _ in range(4)] for _ in range(30)]
        r = client.post("/ai/anomaly", headers=_auth(self._token), json={
            "samples": samples, "contamination": 0.1,
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["labels"]) == 30
        assert len(data["scores"]) == 30
        assert set(data["labels"]).issubset({-1, 1})

    def test_sentiment(self):
        r = client.post("/ai/sentiment", headers=_auth(self._token), json={
            "texts": [
                "Record profit growth beats expectations with strong revenue",
                "Loss and risk of default amid volatile market conditions",
            ]
        })
        assert r.status_code == 200
        data = r.json()
        assert data["n_positive"] + data["n_neutral"] + data["n_negative"] == 2
        assert -1.0 <= data["average_score"] <= 1.0

    def test_sentiment_requires_at_least_one_text(self):
        r = client.post("/ai/sentiment", headers=_auth(self._token), json={"texts": []})
        assert r.status_code == 422

    def test_anomaly_requires_10_samples_minimum(self):
        r = client.post("/ai/anomaly", headers=_auth(self._token), json={
            "samples": [[1.0, 2.0]], "contamination": 0.1,
        })
        assert r.status_code == 422


# ── trading ───────────────────────────────────────────────────────────────────

class TestTradingRoutes:
    @pytest.fixture(autouse=True)
    def token(self):
        self._token = _register_and_login()

    def test_place_market_order(self):
        r = client.post("/trading/orders", headers=_auth(self._token), json={
            "symbol": "AAPL", "side": "buy", "order_type": "market", "quantity": 10,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "filled"
        assert data["fill_price"] is not None

    def test_place_limit_order_without_price_rejected(self):
        r = client.post("/trading/orders", headers=_auth(self._token), json={
            "symbol": "MSFT", "side": "buy", "order_type": "limit", "quantity": 5,
        })
        assert r.status_code == 400

    def test_list_orders(self):
        # Place one first
        client.post("/trading/orders", headers=_auth(self._token), json={
            "symbol": "TSLA", "side": "sell", "order_type": "market", "quantity": 2,
        })
        r = client.get("/trading/orders", headers=_auth(self._token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1

    def test_get_order_by_id(self):
        placed = client.post("/trading/orders", headers=_auth(self._token), json={
            "symbol": "NVDA", "side": "buy", "order_type": "market", "quantity": 1,
        }).json()
        r = client.get(f"/trading/orders/{placed['id']}", headers=_auth(self._token))
        assert r.status_code == 200
        assert r.json()["id"] == placed["id"]

    def test_get_nonexistent_order_404(self):
        r = client.get(f"/trading/orders/{uuid.uuid4()}", headers=_auth(self._token))
        assert r.status_code == 404

    def test_positions_empty_initially(self):
        # Fresh user → no positions
        token = _register_and_login()
        r = client.get("/trading/positions", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["total_symbols"] == 0

    def test_positions_populated_after_fill(self):
        client.post("/trading/orders", headers=_auth(self._token), json={
            "symbol": "AMZN", "side": "buy", "order_type": "market", "quantity": 3,
        })
        r = client.get("/trading/positions", headers=_auth(self._token))
        assert r.status_code == 200
        assert r.json()["total_symbols"] >= 1

    def test_market_data(self):
        token = _register_and_login()
        r = client.get("/trading/market-data?symbols=AAPL,MSFT", headers=_auth(token))
        assert r.status_code == 200
        quotes = r.json()["quotes"]
        assert len(quotes) == 2
        symbols = {q["symbol"] for q in quotes}
        assert symbols == {"AAPL", "MSFT"}


# ── z/OS routes ───────────────────────────────────────────────────────────────

class TestZOSRoutes:
    @pytest.fixture(autouse=True)
    def token(self):
        self._token = _register_and_login()

    def test_health(self):
        r = client.get("/zos/health", headers=_auth(self._token))
        assert r.status_code == 200
        data = r.json()
        assert "lpars" in data
        assert data["total_lpars"] == 2
        assert data["online_lpars"] == 2

    def test_lpars(self):
        r = client.get("/zos/lpars", headers=_auth(self._token))
        assert r.status_code == 200
        lpars = r.json()
        assert len(lpars) == 2
        names = {l["lpar_name"] for l in lpars}
        assert "SYSA" in names and "SYSB" in names

    def test_transcode_encode(self):
        r = client.post("/zos/transcode", headers=_auth(self._token), json={
            "text": "HELLO WORLD", "code_page": "cp037", "record_length": 80, "mode": "fixed",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["byte_count"] == 80
        assert len(data["ebcdic_b64"]) > 0

    def test_transcode_roundtrip(self):
        text = "QUANTUMFINTEK MAINFRAME TEST"
        enc = client.post("/zos/transcode", headers=_auth(self._token), json={
            "text": text, "code_page": "cp037", "mode": "raw",
        }).json()
        dec = client.post("/zos/transcode/decode", headers=_auth(self._token), json={
            "ebcdic_b64": enc["ebcdic_b64"], "code_page": "cp037", "mode": "raw",
        }).json()
        assert dec["lines"][0].strip() == text

    def test_transcode_bad_codepage(self):
        r = client.post("/zos/transcode", headers=_auth(self._token), json={
            "text": "test", "code_page": "cp9999",
        })
        assert r.status_code == 400

    def test_datasets_list(self):
        r = client.get("/zos/datasets?hlq=QFINTEK", headers=_auth(self._token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] > 0
        assert all(d["dsn"].startswith("QFINTEK") for d in data["datasets"])

    def test_dataset_upload(self):
        r = client.post("/zos/datasets/upload", headers=_auth(self._token), json={
            "dsn": "QFINTEK.JCL.LIB",
            "lines": ["RECORD ONE", "RECORD TWO", "RECORD THREE"],
            "recfm": "FB", "lrecl": 80, "code_page": "cp037",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["records_written"] == 3
        assert data["byte_count"] == 240  # 3 × 80

    def test_dataset_download(self):
        r = client.post("/zos/datasets/download", headers=_auth(self._token), json={
            "dsn": "QFINTEK.PAYROLL.MASTER", "code_page": "cp037", "max_records": 5,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["record_count"] <= 5
        assert data["dsn"] == "QFINTEK.PAYROLL.MASTER"

    def test_dataset_download_not_found(self):
        r = client.post("/zos/datasets/download", headers=_auth(self._token), json={
            "dsn": "NOEXIST.DATA.SET",
        })
        assert r.status_code == 404

    def test_submit_job(self):
        r = client.post("/zos/jobs", headers=_auth(self._token), json={
            "job_name": "TESTJOB",
            "lpar": "SYSA",
            "program": "IEFBR14",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["job_name"] == "TESTJOB"
        assert data["status"] in ("OUTPUT", "ACTIVE", "INPUT", "CANCELLED")
        assert data["job_id"].startswith("JOB")

    def test_list_jobs(self):
        client.post("/zos/jobs", headers=_auth(self._token), json={
            "job_name": "LISTTEST", "lpar": "SYSA", "program": "IEFBR14",
        })
        r = client.get("/zos/jobs", headers=_auth(self._token))
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_get_job_by_id(self):
        submitted = client.post("/zos/jobs", headers=_auth(self._token), json={
            "job_name": "GETTEST", "lpar": "SYSA", "program": "SORT",
        }).json()
        r = client.get(f"/zos/jobs/{submitted['job_id']}", headers=_auth(self._token))
        assert r.status_code == 200
        assert r.json()["job_id"] == submitted["job_id"]

    def test_get_nonexistent_job_404(self):
        r = client.get("/zos/jobs/JOB00000", headers=_auth(self._token))
        assert r.status_code == 404

    def test_submit_to_unknown_lpar_404(self):
        r = client.post("/zos/jobs", headers=_auth(self._token), json={
            "job_name": "BADLPAR", "lpar": "UNKNOWN_LPAR",
        })
        assert r.status_code == 404

    def test_mq_status(self):
        r = client.get("/zos/mqbridge", headers=_auth(self._token))
        assert r.status_code == 200
        data = r.json()
        assert data["connected"] is True
        assert isinstance(data["queues"], dict)

    def test_mq_put(self):
        r = client.post("/zos/mqbridge/put", headers=_auth(self._token), json={
            "queue_name": "QFINTEK.ORDERS.LOCAL",
            "payload": "BUY 100 AAPL @ MKT",
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["msg_id"]) > 0
        assert data["queue_depth"] >= 1

    def test_mq_get_returns_message(self):
        # Put first, then get
        client.post("/zos/mqbridge/put", headers=_auth(self._token), json={
            "queue_name": "QFINTEK.TRADES.LOCAL",
            "payload": "SELL 50 MSFT @ 415.00",
        })
        r = client.get(
            "/zos/mqbridge/get?queue_name=QFINTEK.TRADES.LOCAL",
            headers=_auth(self._token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["payload"] is not None
        assert "MSFT" in data["payload"]

    def test_mq_get_empty_queue(self):
        r = client.get(
            "/zos/mqbridge/get?queue_name=QFINTEK.RISK.LOCAL",
            headers=_auth(self._token),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["msg_id"] is None
        assert data["payload"] is None

    def test_racf_check(self):
        r = client.post("/zos/racf/check", headers=_auth(self._token), json={
            "userid": "JDOE",
            "groups": ["FINGRP"],
            "resource_name": "QFINTEK.PAYROLL.MASTER",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["userid"] == "JDOE"
        assert data["effective_permission"] in ("NONE", "READ", "UPDATE", "CONTROL", "ALTER")

    def test_racf_special_user_gets_alter(self):
        r = client.post("/zos/racf/check", headers=_auth(self._token), json={
            "userid": "SYSADM",
            "attributes": ["SPECIAL"],
            "resource_name": "QFINTEK.PAYROLL.MASTER",
        })
        assert r.status_code == 200
        assert r.json()["effective_permission"] == "ALTER"
