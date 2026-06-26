from __future__ import annotations

from src.auth.models import AuthDatabase
from src.auth.permissions import PERMISSION_CADASTRAR, PERMISSION_MANAGE_USERS
from src.auth.passwords import hash_password
from src.config import get_settings
from tests.auth_helpers import create_test_user, login_and_csrf


def test_admin_list_users(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "admin@avs.com.br", "Admin", password)

    headers = login_and_csrf(auth_client, "admin@avs.com.br", password)
    res = auth_client.get("/auth/admin/users", headers=headers)
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()["users"]}
    assert "admin@avs.com.br" in emails


def test_admin_denied_without_manage_users(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = db.create_user("limited@avs.com.br", "Limitado", hash_password(password))
    db.set_permissions(
        user.id,
        {PERMISSION_CADASTRAR: True, PERMISSION_MANAGE_USERS: False, "inativar": False, "consultar": False, "empresas_inativas": False},
    )

    headers = login_and_csrf(auth_client, "limited@avs.com.br", password)
    res = auth_client.get("/auth/admin/users", headers=headers)
    assert res.status_code == 403


def test_admin_cannot_remove_own_manage_users(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    admin = create_test_user(db, "admin@avs.com.br", "Admin", password)

    headers = login_and_csrf(auth_client, "admin@avs.com.br", password)
    res = auth_client.patch(
        f"/auth/admin/users/{admin.id}/permissions",
        json={"permissions": {PERMISSION_MANAGE_USERS: False}},
        headers=headers,
    )
    assert res.status_code == 400


def test_admin_update_permissions(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "admin@avs.com.br", "Admin", password)
    target = db.create_user("target@avs.com.br", "Target", hash_password(password))

    headers = login_and_csrf(auth_client, "admin@avs.com.br", password)
    res = auth_client.patch(
        f"/auth/admin/users/{target.id}/permissions",
        json={"permissions": {PERMISSION_CADASTRAR: True}},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["permissions"][PERMISSION_CADASTRAR] is True
