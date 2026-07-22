from typing import Any

from fastapi import APIRouter, FastAPI

from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix=settings.api_prefix)


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness endpoint for orchestrators and load balancers."""
    return {"status": "ok", "service": settings.app_name, "version": settings.version}


@router.get("/ready", tags=["system"])
def readiness() -> dict[str, Any]:
    """Readiness endpoint; dependency checks will be added as services are introduced."""
    return {"status": "ready", "checks": {"application": "ok"}}


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.include_router(router)
    return app


app = create_app()
