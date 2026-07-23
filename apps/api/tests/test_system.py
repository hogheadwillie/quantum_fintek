from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

client = TestClient(create_app())


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "QuantumFintek API",
        "version": "0.1.0",
    }


def test_readiness_endpoint() -> None:
    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"application": "ok"},
    }


def test_openapi_is_available_outside_production() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "QuantumFintek API"


def test_documentation_is_disabled_in_production() -> None:
    production_client = TestClient(create_app(Settings(environment="production")))

    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404
