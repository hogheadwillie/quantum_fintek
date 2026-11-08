"""QuantumFintek API entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, ai, auth, compliance, notifications, orgs, quant, trading, ws, zos
from app.core.config import get_settings
from app.core.logging import StructuredLoggingMiddleware, setup_logging
from app.core.redis import close_redis
from app.db.session import init_db
from app.identity.security.key_rotation import get_key_ring_manager
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    settings = get_settings()
    mgr = get_key_ring_manager()
    mgr.initialize_from_settings(
        algorithm=settings.jwt_algorithm,
        secret_key=settings.secret_key,
        private_pem=settings.jwt_private_key_pem,
        public_pem=settings.jwt_public_key_pem,
        active_kid=settings.jwt_key_id,
        previous_public_keys_json=settings.jwt_previous_public_keys_json,
        app_env=settings.app_env,
        store_path=settings.jwt_key_store_path,
        max_previous_keys=settings.jwt_max_previous_keys,
        key_bits=settings.jwt_key_bits,
        kid_prefix=settings.jwt_kid_prefix,
        auto_bootstrap=settings.jwt_auto_bootstrap,
    )
    await init_db()
    if settings.jwt_auto_rotate:
        await mgr.start_scheduler(settings.jwt_rotation_interval_seconds)
    yield
    await mgr.stop_scheduler()
    await close_redis()


settings = get_settings()

_docs_url = "/docs" if settings.openapi_enabled else None
_redoc_url = "/redoc" if settings.openapi_enabled else None
_openapi_url = "/openapi.json" if settings.openapi_enabled else None

app = FastAPI(
    title="QuantumFintek API",
    description="Enterprise quantitative finance platform",
    version="0.9.2",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
)
app.add_middleware(
    RateLimitMiddleware,
    trading_limit=getattr(settings, "rate_limit_trading", 60),
    global_limit=getattr(settings, "rate_limit_global", 600),
    window_seconds=getattr(settings, "rate_limit_window", 60),
)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.enable_hsts,
    hsts_max_age=settings.hsts_max_age,
)

app.include_router(auth.router)
app.include_router(quant.router)
app.include_router(ai.router)
app.include_router(admin.router)
app.include_router(compliance.router)
app.include_router(trading.router)
app.include_router(orgs.router)
app.include_router(ws.router)
app.include_router(zos.router)
app.include_router(notifications.router)

app.add_middleware(StructuredLoggingMiddleware)


@app.get("/health")
def health():
    return {"status": "ok", "service": "quantum-fintek-api", "version": "0.9.2"}


@app.get("/")
def root():
    endpoints = {
        "register": "/auth/register",
        "login": "/auth/login",
        "jwks": "/auth/jwks.json",
        "me": "/auth/me",
        "admin_jwt_keys": "/admin/jwt/keys",
        "admin_jwt_rotate": "/admin/jwt/rotate",
    }
    if settings.openapi_enabled:
        endpoints["docs"] = "/docs"
    return {
        "name": "QuantumFintek",
        "version": "0.9.2",
        "env": settings.app_env,
        "domains": [
            "trading",
            "quantitative",
            "ai-intelligence",
            "enterprise",
            "security",
            "compliance",
        ],
        "endpoints": endpoints,
    }
