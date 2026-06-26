from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException, Request

from src.auth.permissions import PERMISSION_MANAGE_USERS, all_permissions_enabled
from src.config import get_settings


def get_current_user(request: Request) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return {
            "email": "dev@local",
            "name": "Desenvolvimento",
            "dev_mode": True,
            "permissions": all_permissions_enabled(),
        }
    user = request.session.get("user")
    if user:
        return user
    if settings.auth_provider == "local":
        from src.auth.local import try_remember_login

        if try_remember_login(request):
            return request.session.get("user")
    return None


def require_user(request: Request) -> dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    return user


def _user_has_permission(user: dict[str, Any], permission: str) -> bool:
    settings = get_settings()
    if not settings.auth_enabled or user.get("dev_mode"):
        return True
    user_id = user.get("id")
    if not user_id:
        return False
    from src.auth.store import get_auth_db

    return get_auth_db(settings).is_permission_enabled(int(user_id), permission)


def require_permission(permission: str) -> Callable[..., dict[str, Any]]:
    def _dependency(request: Request) -> dict[str, Any]:
        user = require_user(request)
        if not _user_has_permission(user, permission):
            raise HTTPException(status_code=403, detail="Sem permissão para esta operação.")
        return user

    return _dependency


def require_manage_users(request: Request) -> dict[str, Any]:
    user = require_user(request)
    if not _user_has_permission(user, PERMISSION_MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Sem permissão para gerenciar usuários.")
    return user
