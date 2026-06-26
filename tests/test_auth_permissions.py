from __future__ import annotations

from src.auth.cli import SEED_USERS
from src.auth.models import AuthDatabase
from src.auth.permissions import PERMISSION_CADASTRAR, PERMISSION_MANAGE_USERS
from src.auth.passwords import hash_password
from src.config import get_settings
from tests.auth_helpers import create_test_user, login_and_csrf


def test_integrar_requires_cadastrar_permission(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("limited@avs.com.br", "Limitado", hash_password(password))

    headers = login_and_csrf(auth_client, "limited@avs.com.br", password)
    blocked = auth_client.post("/preview", json={"cnpj": "11222333000181"}, headers=headers)
    assert blocked.status_code == 403


def test_integrar_allowed_with_cadastrar(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "user@avs.com.br", "Usuário", password)

    headers = login_and_csrf(auth_client, "user@avs.com.br", password)
    res = auth_client.post("/preview", json={"cnpj": "11222333000181"}, headers=headers)
    assert res.status_code != 403


def test_me_includes_permissions(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "user@avs.com.br", "Usuário", password)

    login_and_csrf(auth_client, "user@avs.com.br", password)
    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    perms = me.json()["user"]["permissions"]
    assert perms[PERMISSION_CADASTRAR] is True
    assert perms[PERMISSION_MANAGE_USERS] is True


def test_seed_migration_grants_seed_users(auth_env):
    settings = get_settings()
    email, name = SEED_USERS[0]
    db = AuthDatabase(settings.auth_db_path)
    if not db.get_user_by_email(email):
        db.create_user(email, name, hash_password("Test1Pass"))
    with db._connect() as conn:
        db._seed_initial_admin_permissions(conn)
    user = db.get_user_by_email(email)
    assert user is not None
    perms = db.get_permissions_map(user.id)
    assert perms[PERMISSION_MANAGE_USERS] is True
