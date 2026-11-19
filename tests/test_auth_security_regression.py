"""Regression checks for the removed arbitrary token issuance endpoint."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
os.environ.setdefault("APP_ENV", "test")

from app.api.routes.auth import router


def test_public_arbitrary_token_issuer_is_not_registered():
    """No client may mint JWTs for arbitrary subjects and roles."""
    assert not any(
        getattr(route, "path", None) == "/auth/token"
        for route in router.routes
    )


def test_standard_authentication_routes_remain_registered():
    paths = {getattr(route, "path", None) for route in router.routes}
    assert {"/auth/register", "/auth/login", "/auth/refresh", "/auth/logout", "/auth/me"}.issubset(paths)
