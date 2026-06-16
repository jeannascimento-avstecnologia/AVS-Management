from __future__ import annotations

from src.auth.models import AuthDatabase
from src.auth.passwords import (
    MIN_PASSWORD_LENGTH,
    hash_password,
    validate_password_policy,
    verify_password,
)
from src.config import get_settings


def test_password_policy_minimum_length():
    errors = validate_password_policy("Ab1")
    assert any(str(MIN_PASSWORD_LENGTH) in e for e in errors)


def test_password_policy_requires_mixed_case_and_digit():
    assert any("minúscula" in e for e in validate_password_policy("ABCD1"))
    assert any("maiúscula" in e for e in validate_password_policy("abcd1"))
    assert any("número" in e for e in validate_password_policy("Abcde"))


def test_password_policy_rejects_blocklist():
    errors = validate_password_policy("Senha1")
    assert errors


def test_hash_and_verify_password():
    raw = "Test1Pass"
    hashed = hash_password(raw)
    assert verify_password(hashed, raw)
    assert not verify_password(hashed, "Other2Pass")


def test_login_success_and_me(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário Teste", hash_password(password))

    login = auth_client.post(
        "/auth/login",
        json={"email": "user@avs.com.br", "password": password, "remember_me": False},
    )
    assert login.status_code == 200
    assert login.json()["ok"] is True

    me = auth_client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@avs.com.br"


def test_login_generic_error(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    db.create_user("user@avs.com.br", "Usuário", hash_password("Good1Pass"))

    bad = auth_client.post(
        "/auth/login",
        json={"email": "user@avs.com.br", "password": "Wrong2Pass"},
    )
    assert bad.status_code == 401
    assert bad.json()["detail"] == "E-mail ou senha inválidos."

    missing = auth_client.post(
        "/auth/login",
        json={"email": "naoexiste@avs.com.br", "password": "Wrong2Pass"},
    )
    assert missing.status_code == 401
    assert missing.json()["detail"] == "E-mail ou senha inválidos."


def test_remember_me_cookie(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(password))

    login = auth_client.post(
        "/auth/login",
        json={"email": "user@avs.com.br", "password": password, "remember_me": True},
    )
    assert login.status_code == 200
    assert "avs_remember" in login.cookies
