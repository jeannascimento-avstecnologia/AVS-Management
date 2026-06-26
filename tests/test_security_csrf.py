from __future__ import annotations

from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password
from src.config import get_settings

from tests.auth_helpers import create_test_user, login_and_csrf


def test_csrf_required_for_protected_post(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "user@avs.com.br", "Usuário", password)
    headers = login_and_csrf(auth_client, "user@avs.com.br", password)

    blocked = auth_client.post("/preview", json={"cnpj": "11222333000181"})
    assert blocked.status_code == 403

    allowed = auth_client.post("/preview", json={"cnpj": "11222333000181"}, headers=headers)
    assert allowed.status_code != 403


def test_login_returns_csrf_token(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(password))

    login = auth_client.post(
        "/auth/login",
        json={"email": "user@avs.com.br", "password": password, "remember_me": False},
    )
    assert login.status_code == 200
    assert login.json().get("csrf_token")
