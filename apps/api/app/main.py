from typing import Any

from fastapi import APIRouter, FastAPI

from app.config import Settings, get_settings


def create_router(settings: Settings) -> APIRouter:
    """Create the versioned system router for the supplied settings."""
    router = APIRouter(prefix=settings.api_prefix)

    @router.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness endpoint for orchestrators and load balancers."""
        return {
            "status": "ok",
            "service": settings.app_name,
            "version": settings.version,
        }

    @router.get("/ready", tags=["system"])
    def readiness() -> dict[str, Any]:
        """Readiness endpoint; dependency checks will be added with new services."""
        return {"status": "ready", "checks": {"application": "ok"}}

    return router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application using explicit settings or the environment defaults."""
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.version,
        docs_url="/docs" if resolved_settings.environment != "production" else None,
        redoc_url=None,
    )
    application.include_router(create_router(resolved_settings))
    return application


app = create_app()
