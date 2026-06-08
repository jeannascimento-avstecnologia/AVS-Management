from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from src.config import Settings, get_settings


def get_current_user(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return {"email": "dev@local", "name": "Desenvolvimento", "dev_mode": True}
    return request.session.get("user")


def require_user(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    return user
