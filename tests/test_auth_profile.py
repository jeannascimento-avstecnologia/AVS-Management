from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password, verify_password
from src.config import get_settings

from tests.auth_helpers import login_and_csrf


def test_get_and_update_profile(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário Teste", hash_password(password))
    headers = login_and_csrf(auth_client, "user@avs.com.br", password)

    profile = auth_client.get("/auth/profile")
    assert profile.status_code == 200
    assert profile.json()["email"] == "user@avs.com.br"
    assert profile.json()["backup_email"] == ""

    updated = auth_client.patch(
        "/auth/profile",
        json={
            "name": "Nome Atualizado",
            "backup_email": "backup@avs.com.br",
            "phone": "(11) 99999-0000",
        },
        headers=headers,
    )
    assert updated.status_code == 200
    data = updated.json()
    assert data["name"] == "Nome Atualizado"
    assert data["backup_email"] == "backup@avs.com.br"
    assert data["phone"] == "(11) 99999-0000"

    me = auth_client.get("/auth/me")
    assert me.json()["user"]["name"] == "Nome Atualizado"


def test_change_password_success(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    old_password = "Test1Pass"
    new_password = "Nova2Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(old_password))
    headers = login_and_csrf(auth_client, "user@avs.com.br", old_password)

    res = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": old_password,
            "new_password": new_password,
            "confirm_password": new_password,
        },
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    user = db.get_user_by_email("user@avs.com.br")
    assert user is not None
    assert verify_password(user.password_hash, new_password)


def test_change_password_wrong_current(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(password))
    headers = login_and_csrf(auth_client, "user@avs.com.br", password)

    res = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": "Wrong2Pass",
            "new_password": "Nova2Pass",
            "confirm_password": "Nova2Pass",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "atual" in res.json()["detail"].lower()


def test_change_password_mismatch(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(password))
    headers = login_and_csrf(auth_client, "user@avs.com.br", password)

    res = auth_client.post(
        "/auth/change-password",
        json={
            "current_password": password,
            "new_password": "Nova2Pass",
            "confirm_password": "Outra2Pass",
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "coincidem" in res.json()["detail"].lower()
