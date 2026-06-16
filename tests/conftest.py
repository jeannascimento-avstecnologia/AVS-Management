from __future__ import annotations

from pathlib import Path

import pytest

from src.auth.local import reset_auth_db_cache
from src.config import clear_settings_cache


@pytest.fixture(autouse=True)
def disable_auth_for_non_auth_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    if "auth_env" in request.fixturenames or "auth_client" in request.fixturenames:
        return
    monkeypatch.setenv("AUTH_ENABLED", "false")
    clear_settings_cache()


@pytest.fixture()
def auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "auth.db"
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("AUTH_DB_PATH", str(db_path))
    monkeypatch.setenv("SESSION_SECRET", "test-secret-key-for-pytest-only")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "user@avs.com.br,autorizado@avstecnologia.cloud")
    monkeypatch.setenv("SMTP_HOST", "")
    clear_settings_cache()
    reset_auth_db_cache()
    yield db_path
    reset_auth_db_cache()
    clear_settings_cache()


@pytest.fixture()
def auth_client(auth_env: Path):
    from fastapi.testclient import TestClient

    from src.main import app

    with TestClient(app) as client:
        yield client
