from __future__ import annotations

import pytest

from src.config import clear_settings_cache, get_settings
from src.security import (
    CSRF_EXEMPT_PATHS,
    FRONTEND_CSRF_EXEMPT_PATHS,
    build_content_security_policy,
    is_csrf_exempt_path,
    requires_strict_security,
)


def test_csrf_exempt_paths_include_frontend():
    assert FRONTEND_CSRF_EXEMPT_PATHS <= CSRF_EXEMPT_PATHS


def test_health_is_csrf_exempt():
    assert is_csrf_exempt_path("/health")


def test_requires_strict_security_from_app_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("APP_ENV", "production")
    clear_settings_cache()
    assert requires_strict_security(get_settings()) is True

    monkeypatch.setenv("APP_ENV", "development")
    clear_settings_cache()
    assert requires_strict_security(get_settings()) is False


def test_requires_strict_security_infers_from_url_when_env_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("APP_BASE_URL", "https://app.avstecnologia.cloud")
    clear_settings_cache()
    assert requires_strict_security(get_settings()) is True

    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8000")
    clear_settings_cache()
    assert requires_strict_security(get_settings()) is False


def test_csp_only_in_strict_context(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8000")
    clear_settings_cache()
    assert build_content_security_policy(get_settings()) is None

    monkeypatch.setenv("APP_ENV", "production")
    clear_settings_cache()
    csp = build_content_security_policy(get_settings())
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_security_headers_csp_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com")
    clear_settings_cache()

    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from src.security import SecurityHeadersMiddleware

    async def health(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/health", health)])
    app.add_middleware(SecurityHeadersMiddleware)

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert "content-security-policy" in {k.lower() for k in response.headers}


def test_security_headers_no_csp_in_development(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:8000")
    clear_settings_cache()

    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from src.security import SecurityHeadersMiddleware

    async def health(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/health", health)])
    app.add_middleware(SecurityHeadersMiddleware)

    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert "content-security-policy" not in {k.lower() for k in response.headers}


def test_validate_security_rejects_weak_secret_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.com")
    monkeypatch.setenv("SESSION_SECRET", "change-me-in-production")
    clear_settings_cache()

    from src.security import validate_security_settings

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_security_settings(get_settings())
