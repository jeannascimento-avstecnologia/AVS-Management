from __future__ import annotations

from src.auth.models import AuthDatabase
from src.config import get_settings
from tests.auth_helpers import create_test_user, login_and_csrf


def test_audit_log_after_login(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "admin@avs.com.br", "Admin", password)

    login_and_csrf(auth_client, "admin@avs.com.br", password)
    entries = db.list_audit_logs(limit=10)
    assert any(e.action == "auth.login" for e in entries)


def test_admin_can_read_audit(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    create_test_user(db, "admin@avs.com.br", "Admin", password)
    headers = login_and_csrf(auth_client, "admin@avs.com.br", password)

    res = auth_client.get("/auth/admin/audit", headers=headers)
    assert res.status_code == 200
    assert "entries" in res.json()
