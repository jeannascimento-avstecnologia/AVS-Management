from __future__ import annotations

from fastapi.testclient import TestClient

from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password


def login_and_csrf(client: TestClient, email: str, password: str, *, remember_me: bool = False) -> dict[str, str]:
    login = client.post(
        "/auth/login",
        json={"email": email, "password": password, "remember_me": remember_me},
    )
    assert login.status_code == 200, login.text
    token = login.json().get("csrf_token") or client.get("/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": token}


def create_test_user(
    db: AuthDatabase,
    email: str,
    name: str,
    password: str,
    *,
    all_permissions: bool = True,
):
    user = db.create_user(email, name, hash_password(password))
    if all_permissions:
        db.grant_all_permissions(user.id)
    return user
