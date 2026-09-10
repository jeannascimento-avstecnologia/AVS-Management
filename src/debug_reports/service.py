from __future__ import annotations

import base64
import html
import json
import re
import time
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request

from src.auth.audit import log_action
from src.auth.email import send_debug_report_email
from src.config import Settings
from src.debug_reports.schemas import (
    DEBUG_REPORT_MAX_SCREENSHOT_BASE64,
    DebugReportClientMeta,
    SessionLogEvent,
    SubmitDebugReportInput,
)

RATE_LIMIT_WINDOW_S = 60 * 60
RATE_LIMIT_MAX = 5

_rate_limit_buckets: dict[str, list[float]] = {}

SECRET_REDACT_PATTERN = re.compile(
    r"(authorization|bearer|access[_-]?token|refresh[_-]?token|api[_-]?key|password|senha|secret)\s*[:=]\s*[\"']?[^\s\"',}]+",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)

_LOG_BADGE_COLORS: dict[str, str] = {
    "error": "#ef4444",
    "console.error": "#ef4444",
    "unhandledrejection": "#ef4444",
    "api.error": "#ef4444",
    "console.warn": "#f59e0b",
    "click": "#3b82f6",
    "navigation": "#10b981",
}


def reset_debug_report_rate_limit() -> None:
    _rate_limit_buckets.clear()


def redact_secrets(value: str) -> str:
    return BEARER_PATTERN.sub("Bearer [REDACTED]", SECRET_REDACT_PATTERN.sub(r"\1=[REDACTED]", value))


def sanitize_session_log(session_log: list[SessionLogEvent]) -> list[SessionLogEvent]:
    cleaned: list[SessionLogEvent] = []
    for event in session_log:
        meta = event.meta
        if meta:
            meta = {
                key: redact_secrets(value) if isinstance(value, str) else value
                for key, value in meta.items()
            }
        cleaned.append(
            event.model_copy(update={"message": redact_secrets(event.message), "meta": meta})
        )
    return cleaned


def _assert_rate_limit(user_key: str) -> None:
    now = time.time()
    recent = [ts for ts in _rate_limit_buckets.get(user_key, []) if now - ts < RATE_LIMIT_WINDOW_S]
    if len(recent) >= RATE_LIMIT_MAX:
        raise HTTPException(
            status_code=400,
            detail="Limite de relatórios excedido. Tente novamente mais tarde.",
        )
    recent.append(now)
    _rate_limit_buckets[user_key] = recent


def strip_data_url_prefix(base64_value: str) -> str:
    comma_index = base64_value.find(",")
    return base64_value[comma_index + 1 :] if comma_index >= 0 else base64_value


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _nl(value: str) -> str:
    return _escape(value).replace("\n", "<br>")


def _render_session_logs_html(session_log: list[SessionLogEvent]) -> str:
    if not session_log:
        return '<div style="color: #94a3b8; font-style: italic;">Nenhum evento registrado nesta sessão.</div>'

    parts: list[str] = []
    for event in session_log:
        badge_bg = _LOG_BADGE_COLORS.get(event.type, "#475569")
        time_label = ""
        if event.ts:
            try:
                time_label = datetime.fromisoformat(event.ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
            except ValueError:
                time_label = event.ts[11:19] if len(event.ts) >= 19 else event.ts
        meta_html = ""
        if event.meta:
            meta_html = (
                ' <span style="color:#94a3b8;font-size:11px;">'
                f"({_escape(json.dumps(event.meta, ensure_ascii=False))})"
                "</span>"
            )
        parts.append(
            '<div style="border-bottom:1px solid #1e293b;padding:6px 0;word-break:break-all;">'
            f'<span style="color:#64748b;font-size:11px;">[{_escape(time_label)}]</span>'
            f'<span style="background-color:{badge_bg};color:#ffffff;font-size:10px;font-weight:700;'
            f'padding:2px 6px;border-radius:4px;text-transform:uppercase;margin:0 4px;display:inline-block;">'
            f"{_escape(event.type)}</span>"
            f'<span style="color:#f8fafc;font-weight:500;">{_escape(event.message)}</span>{meta_html}'
            "</div>"
        )
    return "".join(parts)


def build_email_html(
    *,
    title: str,
    description: str,
    notes: str | None,
    reporter_name: str,
    reporter_email: str,
    client_meta: DebugReportClientMeta,
    session_log: list[SessionLogEvent],
    screenshot_base64: str,
) -> str:
    clean_base64 = strip_data_url_prefix(screenshot_base64)
    screenshot_data_url = f"data:image/png;base64,{clean_base64}"
    notes_html = ""
    if notes:
        notes_html = f"""
              <div style="margin-bottom: 20px;">
                <h2 style="margin: 0 0 8px 0; font-size: 13px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">Observações Adicionais</h2>
                <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 0 8px 8px 0; font-size: 14px; line-height: 1.6; color: #92400e;">
                  {_nl(notes)}
                </div>
              </div>"""
    logs_html = _render_session_logs_html(session_log)
    return f"""<!-- NO-BRANDING -->
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Debug Report] {_escape(title)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f1f5f9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:680px;background-color:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #cbd5e1;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
          <tr>
            <td style="background-color:#0f172a;padding:24px;color:#ffffff;">
              <table width="100%" role="presentation" cellspacing="0" cellpadding="0">
                <tr>
                  <td>
                    <span style="background-color:#ef4444;color:#ffffff;font-size:11px;font-weight:700;padding:4px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:0.5px;display:inline-block;margin-bottom:8px;">
                      Relatório de Bug / Debug
                    </span>
                    <h1 style="margin:0;font-size:20px;font-weight:700;color:#ffffff;line-height:1.3;">
                      {_escape(title)}
                    </h1>
                  </td>
                  <td align="right" style="vertical-align:top;">
                    <span style="background-color:#1e293b;color:#94a3b8;font-size:11px;font-weight:600;padding:4px 10px;border-radius:6px;border:1px solid #334155;white-space:nowrap;">
                      {_escape(client_meta.app)}
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f8fafc;padding:12px 24px;border-bottom:1px solid #e2e8f0;font-size:13px;color:#475569;">
              <strong>Reportado por:</strong> {_escape(reporter_name)}
              (&lt;<a href="mailto:{_escape(reporter_email)}" style="color:#2563eb;text-decoration:none;">{_escape(reporter_email)}</a>&gt;)
            </td>
          </tr>
          <tr>
            <td style="padding:24px;">
              <div style="margin-bottom:20px;">
                <h2 style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.5px;">Descrição do Problema</h2>
                <div style="background-color:#f8fafc;border-left:4px solid #3b82f6;padding:14px 16px;border-radius:0 8px 8px 0;font-size:14px;line-height:1.6;color:#0f172a;border-top:1px solid #f1f5f9;border-right:1px solid #f1f5f9;border-bottom:1px solid #f1f5f9;">
                  {_nl(description)}
                </div>
              </div>
              {notes_html}
              <div style="margin-bottom:24px;">
                <h2 style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.5px;">Contexto Técnico do Cliente</h2>
                <table width="100%" role="presentation" style="border-collapse:collapse;font-size:13px;">
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:8px 0;color:#64748b;width:120px;font-weight:600;">Página / URL:</td>
                    <td style="padding:8px 0;color:#0f172a;word-break:break-all;">
                      <a href="{_escape(client_meta.url)}" style="color:#2563eb;text-decoration:underline;" target="_blank">
                        {_escape(client_meta.url)}
                      </a>
                    </td>
                  </tr>
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:8px 0;color:#64748b;font-weight:600;">Viewport:</td>
                    <td style="padding:8px 0;color:#0f172a;">{client_meta.viewport.width} x {client_meta.viewport.height} px</td>
                  </tr>
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:8px 0;color:#64748b;font-weight:600;">Navegador:</td>
                    <td style="padding:8px 0;color:#0f172a;font-size:12px;font-family:monospace;">{_escape(client_meta.userAgent)}</td>
                  </tr>
                </table>
              </div>
              <div style="margin-bottom:24px;">
                <h2 style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.5px;">Captura de Tela do Viewport</h2>
                <div style="border:1px solid #cbd5e1;border-radius:8px;overflow:hidden;background-color:#0f172a;text-align:center;padding:12px;">
                  <img src="{screenshot_data_url}" alt="Captura de Tela" style="max-width:100%;height:auto;display:block;margin:0 auto;border:0;border-radius:4px;" />
                </div>
              </div>
              <div style="margin-bottom:12px;">
                <h2 style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:0.5px;">
                  Logs de Acesso e Sessão ({len(session_log)} eventos)
                </h2>
                <div style="background-color:#0f172a;border-radius:8px;padding:16px;font-family:Consolas,Monaco,'Andale Mono',monospace;font-size:12px;line-height:1.5;color:#e2e8f0;max-height:400px;overflow-y:auto;overflow-x:auto;">
                  {logs_html}
                </div>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f8fafc;padding:16px 24px;border-top:1px solid #e2e8f0;text-align:center;font-size:12px;color:#94a3b8;">
              AVS Management — Ferramenta de Relatório de Debug. Os arquivos brutos <code>screenshot.png</code> e <code>session-log.json</code> também continuam anexados a esta mensagem.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_debug_report(
    request: Request,
    settings: Settings,
    payload: SubmitDebugReportInput,
    user: dict[str, Any],
) -> dict[str, bool]:
    user_key = str(user.get("id") or user.get("email") or "anonymous")
    _assert_rate_limit(user_key)

    if len(payload.screenshotBase64) > DEBUG_REPORT_MAX_SCREENSHOT_BASE64:
        raise HTTPException(status_code=400, detail="Captura muito grande.")

    recipients = settings.debug_report_recipient_list
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="Destinatários de debug report não configurados (DEBUG_REPORT_RECIPIENTS).",
        )

    reporter_name = str(user.get("name") or user.get("email") or "Usuário")
    reporter_email = str(user.get("email") or "")
    session_log = sanitize_session_log(payload.sessionLog)
    subject = f"[Debug Report] {payload.title}"
    html_body = build_email_html(
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
        reporter_name=reporter_name,
        reporter_email=reporter_email,
        client_meta=payload.clientMeta,
        session_log=session_log,
        screenshot_base64=payload.screenshotBase64,
    )

    screenshot_bytes = base64.b64decode(strip_data_url_prefix(payload.screenshotBase64), validate=False)
    session_log_bytes = json.dumps(
        [event.model_dump() for event in session_log],
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    try:
        send_debug_report_email(
            settings,
            to=recipients,
            subject=subject,
            html_body=html_body,
            reply_to=reporter_email or None,
            screenshot_png=screenshot_bytes,
            session_log_json=session_log_bytes,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    log_action(
        request,
        action="debug_report",
        resource="debug-report",
        detail={"title": payload.title, "recipients": recipients},
        user=user,
    )
    return {"success": True}
