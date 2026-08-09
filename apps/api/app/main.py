"""QuantumFintek API entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, ai, auth, compliance, orgs, quant, trading, ws
from app.core.config import get_settings
from app.core.redis import close_redis
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await close_redis()


settings = get_settings()

app = FastAPI(
    title="QuantumFintek API",
    description="Enterprise quantitative finance platform",
    version="0.7.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(quant.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(compliance.router)
app.include_router(trading.router)
app.include_router(orgs.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "quantum-fintek-api", "version": "0.7.0"}


@app.get("/")
def root():
    return {
        "name": "QuantumFintek",
        "version": "0.7.0",
        "domains": ["trading", "quantitative", "ai-intelligence", "enterprise", "security", "compliance"],
        "endpoints": {
            "register": "/auth/register",
            "login": "/auth/login",
            "me": "/auth/me",
            "quant_optimize": "/quant/optimize",
            "quant_risk": "/quant/risk",
            "quant_backtest": "/quant/backtest",
            "quant_factor": "/quant/factor",
            "ai_anomaly": "/ai/anomaly",
            "ai_sentiment": "/ai/sentiment",
            "admin_audit": "/admin/audit",
            "admin_users": "/admin/users",
            "compliance_evidence": "/compliance/evidence",
            "trading_orders": "/trading/orders",
            "trading_positions": "/trading/positions",
            "trading_market_data": "/trading/market-data",
            "orgs": "/orgs",
            "docs": "/docs",
        },
    }
