from __future__ import annotations

from unittest.mock import patch

from src.auth.models import AuthDatabase
from src.auth.passwords import hash_password, verify_password
from src.config import get_settings

FORGOT_MSG = "Se o e-mail estiver cadastrado, enviaremos instruções para redefinir a senha."


def test_forgot_password_generic_response(auth_client):
    known = auth_client.post("/auth/forgot-password", json={"email": "user@avs.com.br"})
    unknown = auth_client.post("/auth/forgot-password", json={"email": "ghost@avs.com.br"})
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == FORGOT_MSG
    assert unknown.json()["message"] == FORGOT_MSG


@patch("src.auth.local.send_password_reset_email")
def test_reset_password_flow(mock_send, auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Init1Pass"
    db.create_user("user@avs.com.br", "Usuário", hash_password(password))

    auth_client.post("/auth/forgot-password", json={"email": "user@avs.com.br"})
    assert mock_send.called
    reset_url = mock_send.call_args.kwargs["reset_url"]
    assert "#token=" in reset_url
    token = reset_url.split("#token=")[-1]

    new_password = "Nova2Pass"
    reset = auth_client.post(
        "/auth/reset-password",
        json={"token": token, "password": new_password},
    )
    assert reset.status_code == 200

    user = db.get_user_by_email("user@avs.com.br")
    assert user is not None
    assert verify_password(user.password_hash, new_password)
    assert not verify_password(user.password_hash, password)

    reuse = auth_client.post(
        "/auth/reset-password",
        json={"token": token, "password": "Other3Pass"},
    )
    assert reuse.status_code == 400
