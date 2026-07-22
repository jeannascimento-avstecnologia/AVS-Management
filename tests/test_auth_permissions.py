from __future__ import annotations

from src.auth.cli import SEED_USERS
from src.auth.models import AuthDatabase
from src.auth.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_APROVAR_FATURA,
    PERMISSION_APROVAR_ORCAMENTO,
    PERMISSION_CADASTRAR,
    PERMISSION_FATURAR,
    PERMISSION_GERAR_CONTRATO,
    PERMISSION_LABELS,
    PERMISSION_MANAGE_USERS,
    PERMISSION_ORCAMENTOS,
    all_permissions_enabled,
    empty_permissions,
)
from src.auth.passwords import hash_password
from src.config import get_settings
from tests.auth_helpers import create_test_user, login_and_csrf

HUB_PERMISSIONS = (
    PERMISSION_ORCAMENTOS,
    PERMISSION_APROVAR_ORCAMENTO,
    PERMISSION_GERAR_CONTRATO,
    PERMISSION_FATURAR,
    PERMISSION_APROVAR_FATURA,
)


def test_catalog_includes_hub_permissions():
    for key in HUB_PERMISSIONS:
        assert key in ALL_PERMISSIONS
        assert key in PERMISSION_LABELS
        assert PERMISSION_LABELS[key]


def test_empty_and_all_helpers_cover_catalog():
    empty = empty_permissions()
    enabled = all_permissions_enabled()
    assert set(empty) == set(ALL_PERMISSIONS)
    assert set(enabled) == set(ALL_PERMISSIONS)
    assert all(v is False for v in empty.values())
    assert all(v is True for v in enabled.values())
    for key in HUB_PERMISSIONS:
        assert empty[key] is False
        assert enabled[key] is True


def test_user_without_rows_defaults_hub_false(auth_env):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    user = db.create_user("noperm@avs.com.br", "Sem Perm", hash_password("Test1Pass"))
    perms = db.get_permissions_map(user.id)
    assert set(perms) == set(ALL_PERMISSIONS)
    for key in HUB_PERMISSIONS:
        assert perms[key] is False


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
    assert set(perms) == set(ALL_PERMISSIONS)
    assert perms[PERMISSION_CADASTRAR] is True
    assert perms[PERMISSION_MANAGE_USERS] is True
    for key in HUB_PERMISSIONS:
        assert perms[key] is True


def test_me_hub_permissions_false_without_grant(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "limited@avs.com.br", "Limitado", password, all_permissions=False)

    login_and_csrf(auth_client, "limited@avs.com.br", password)
    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    perms = me.json()["user"]["permissions"]
    assert set(perms) == set(ALL_PERMISSIONS)
    for key in HUB_PERMISSIONS:
        assert perms[key] is False


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
    for key in HUB_PERMISSIONS:
        assert perms[key] is True


def test_admin_accepts_hub_permission_keys(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "admin@avs.com.br", "Admin", password)
    target = db.create_user("target@avs.com.br", "Target", hash_password(password))

    headers = login_and_csrf(auth_client, "admin@avs.com.br", password)
    labels = auth_client.get("/auth/admin/users", headers=headers)
    assert labels.status_code == 200
    for key in HUB_PERMISSIONS:
        assert key in labels.json()["permission_labels"]

    res = auth_client.patch(
        f"/auth/admin/users/{target.id}/permissions",
        json={"permissions": {PERMISSION_ORCAMENTOS: True, PERMISSION_FATURAR: True}},
        headers=headers,
    )
    assert res.status_code == 200
    updated = res.json()["permissions"]
    assert set(updated) == set(ALL_PERMISSIONS)
    assert updated[PERMISSION_ORCAMENTOS] is True
    assert updated[PERMISSION_FATURAR] is True
    assert updated[PERMISSION_APROVAR_ORCAMENTO] is False
    assert updated[PERMISSION_GERAR_CONTRATO] is False
    assert updated[PERMISSION_APROVAR_FATURA] is False
