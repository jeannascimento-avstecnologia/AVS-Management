from __future__ import annotations

import base64
from unittest.mock import patch

from src.auth.email import send_debug_report_email
from src.auth.models import AuthDatabase
from src.config import clear_settings_cache, get_settings
from src.debug_reports.schemas import DEBUG_REPORT_MAX_SCREENSHOT_BASE64
from src.debug_reports.service import RATE_LIMIT_MAX, reset_debug_report_rate_limit

from tests.auth_helpers import create_test_user, login_and_csrf

TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII="
)

PASSWORD = "Test1Pass"
RECIPIENTS = "ops@avs.com.br,dev@avs.com.br"


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": "Falha no PDF",
        "description": "O download não inicia.",
        "screenshotBase64": TINY_PNG,
        "sessionLog": [
            {
                "ts": "2026-09-10T12:00:00.000Z",
                "type": "console.error",
                "message": "failed Bearer supersecrettokenvalue",
                "meta": {"info": "password=hunter2"},
            }
        ],
        "clientMeta": {
            "url": "http://127.0.0.1:5173/orcamentos",
            "userAgent": "pytest",
            "viewport": {"width": 1280, "height": 720},
            "app": "avs-management",
        },
    }
    body.update(overrides)
    return body


def _login(auth_client):
    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    create_test_user(db, "user@avs.com.br", "Usuário Teste", PASSWORD)
    return login_and_csrf(auth_client, "user@avs.com.br", PASSWORD)


def _enable_recipients(monkeypatch) -> None:
    monkeypatch.setenv("DEBUG_REPORT_RECIPIENTS", RECIPIENTS)
    clear_settings_cache()


def test_debug_report_requires_auth(auth_client):
    reset_debug_report_rate_limit()
    csrf = auth_client.get("/auth/csrf").json()["csrf_token"]
    res = auth_client.post("/debug-reports", json=_payload(), headers={"X-CSRF-Token": csrf})
    assert res.status_code == 401
    assert res.json()["detail"] == "Autenticação necessária."


def test_debug_report_recipients_missing(auth_client, monkeypatch):
    reset_debug_report_rate_limit()
    monkeypatch.setenv("DEBUG_REPORT_RECIPIENTS", "")
    clear_settings_cache()
    headers = _login(auth_client)
    res = auth_client.post("/debug-reports", json=_payload(), headers=headers)
    assert res.status_code == 400
    assert "DEBUG_REPORT_RECIPIENTS" in res.json()["detail"]


def test_debug_report_screenshot_too_large(auth_client, monkeypatch):
    reset_debug_report_rate_limit()
    _enable_recipients(monkeypatch)
    headers = _login(auth_client)
    huge = "x" * (DEBUG_REPORT_MAX_SCREENSHOT_BASE64 + 1)
    res = auth_client.post("/debug-reports", json=_payload(screenshotBase64=huge), headers=headers)
    assert res.status_code == 400
    assert res.json()["detail"] == "Captura muito grande."


@patch("src.debug_reports.service.log_action")
@patch("src.debug_reports.service.send_debug_report_email")
def test_debug_report_success_sends_email(mock_send, mock_log, auth_client, monkeypatch):
    reset_debug_report_rate_limit()
    _enable_recipients(monkeypatch)
    headers = _login(auth_client)

    res = auth_client.post("/debug-reports", json=_payload(notes="passo extra"), headers=headers)
    assert res.status_code == 201, res.text
    assert res.json() == {"success": True}

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == ["ops@avs.com.br", "dev@avs.com.br"]
    assert kwargs["reply_to"] == "user@avs.com.br"
    assert kwargs["subject"] == "[Debug Report] Falha no PDF"
    assert kwargs["screenshot_png"]
    log_json = kwargs["session_log_json"].decode("utf-8")
    assert "Bearer [REDACTED]" in log_json
    assert "password=[REDACTED]" in log_json
    assert "supersecrettokenvalue" not in log_json
    assert "hunter2" not in log_json
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["action"] == "debug_report"


@patch("src.debug_reports.service.log_action")
@patch("src.debug_reports.service.send_debug_report_email")
def test_debug_report_rate_limit(mock_send, mock_log, auth_client, monkeypatch):
    reset_debug_report_rate_limit()
    _enable_recipients(monkeypatch)
    headers = _login(auth_client)

    for _ in range(RATE_LIMIT_MAX):
        res = auth_client.post("/debug-reports", json=_payload(), headers=headers)
        assert res.status_code == 201, res.text

    blocked = auth_client.post("/debug-reports", json=_payload(), headers=headers)
    assert blocked.status_code == 400
    assert "Limite de relatórios" in blocked.json()["detail"]
    assert mock_send.call_count == RATE_LIMIT_MAX


@patch("src.auth.email.smtplib.SMTP")
def test_send_debug_report_email_attachments(mock_smtp, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "noreply@avs.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM", "noreply@avs.com")
    clear_settings_cache()

    raw_png = base64.b64decode(TINY_PNG.split(",", 1)[1])
    send_debug_report_email(
        get_settings(),
        to=["ops@avs.com.br"],
        subject="[Debug Report] Falha no PDF",
        html_body="<p>ok</p>",
        reply_to="user@avs.com.br",
        screenshot_png=raw_png,
        session_log_json=b'[{"message":"ok"}]',
    )

    server = mock_smtp.return_value.__enter__.return_value
    server.sendmail.assert_called_once()
    _from, recipients, raw = server.sendmail.call_args.args
    assert recipients == ["ops@avs.com.br"]
    assert "screenshot.png" in raw
    assert "session-log.json" in raw
    assert "Reply-To: user@avs.com.br" in raw
