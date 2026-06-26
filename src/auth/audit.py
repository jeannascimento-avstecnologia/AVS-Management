from __future__ import annotations

import json
from typing import Any

from fastapi import Request

from src.auth.store import get_auth_db
from src.security import client_ip


def log_action(
    request: Request,
    *,
    action: str,
    resource: str,
    detail: dict[str, Any] | None = None,
    user: dict[str, Any] | None = None,
) -> None:
    actor = user or request.session.get("user") or {}
    user_id = actor.get("id")
    user_email = str(actor.get("email") or "")
    if not user_id and not user_email:
        return

    safe_detail = _sanitize_detail(detail or {})
    get_auth_db().insert_audit_log(
        user_id=int(user_id) if user_id else None,
        user_email=user_email,
        action=action,
        resource=resource,
        detail=json.dumps(safe_detail, ensure_ascii=False),
        ip_address=client_ip(request),
    )


def _sanitize_detail(detail: dict[str, Any]) -> dict[str, Any]:
    blocked = {"password", "token", "csrf_token", "password_hash", "current_password", "new_password"}
    out: dict[str, Any] = {}
    for key, value in detail.items():
        if key.lower() in blocked:
            continue
        out[key] = value
    return out
