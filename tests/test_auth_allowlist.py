from __future__ import annotations

from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password


def test_login_rejects_email_not_in_allowlist(auth_client, monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_USER_EMAILS",
        "autorizado@avstecnologia.cloud",
    )
    from src.config import clear_settings_cache

    clear_settings_cache()

    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    db.create_user("bloqueado@avstecnologia.cloud", "Bloqueado", hash_password("Test1Pass"))

    res = auth_client.post(
        "/auth/login",
        json={
            "email": "bloqueado@avstecnologia.cloud",
            "password": "Test1Pass",
            "remember_me": False,
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "E-mail ou senha inválidos."
