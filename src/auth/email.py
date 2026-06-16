from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import Settings


def send_password_reset_email(
    settings: Settings,
    *,
    to_email: str,
    reset_url: str,
    user_name: str,
) -> None:
    if not settings.smtp_host or not settings.smtp_user:
        raise RuntimeError("SMTP não configurado (SMTP_HOST / SMTP_USER).")

    subject = "AVS Management — redefinição de senha"
    text_body = (
        f"Olá, {user_name}.\n\n"
        "Recebemos uma solicitação para redefinir sua senha no AVS Management.\n"
        f"Acesse o link abaixo (válido por {settings.password_reset_token_hours} hora(s)):\n\n"
        f"{reset_url}\n\n"
        "Se você não solicitou esta alteração, ignore este e-mail.\n\n"
        "— AVS Management"
    )
    html_body = f"""
    <p>Olá, <strong>{user_name}</strong>.</p>
    <p>Recebemos uma solicitação para redefinir sua senha no <strong>AVS Management</strong>.</p>
    <p><a href="{reset_url}">Clique aqui para definir uma nova senha</a></p>
    <p>O link expira em {settings.password_reset_token_hours} hora(s).</p>
    <p>Se você não solicitou esta alteração, ignore este e-mail.</p>
  """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], [to_email], msg.as_string())
