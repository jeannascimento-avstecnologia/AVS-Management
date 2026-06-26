from __future__ import annotations

import json
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from src.auth.audit import log_action
from src.auth.deps import require_manage_users
from src.auth.email import send_password_reset_email
from src.auth.store import get_auth_db
from src.auth.passwords import hash_password, validate_password_policy
from src.auth.permissions import ALL_PERMISSIONS, PERMISSION_MANAGE_USERS, PERMISSION_LABELS
from src.config import get_settings


class CreateUserBody(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str | None = None


class SetPermissionsBody(BaseModel):
    permissions: dict[str, bool]


class AdminPasswordBody(BaseModel):
    password: str


def _temp_password() -> str:
    n = secrets.randbelow(900) + 100
    return f"Avs{n}x"


def _user_admin_dict(user, permissions: dict[str, bool]) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
        "permissions": permissions,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _ensure_can_modify_permissions(
    db,
    *,
    actor: dict[str, Any],
    target_user_id: int,
    new_permissions: dict[str, bool],
) -> None:
    actor_id = int(actor["id"])
    if target_user_id == actor_id:
        current = db.get_permissions_map(actor_id)
        if current.get(PERMISSION_MANAGE_USERS) and not new_permissions.get(PERMISSION_MANAGE_USERS):
            raise HTTPException(
                status_code=400,
                detail="Você não pode remover sua própria permissão de gerenciar usuários.",
            )

    target_current = db.get_permissions_map(target_user_id)
    removing_manage = target_current.get(PERMISSION_MANAGE_USERS) and not new_permissions.get(
        PERMISSION_MANAGE_USERS
    )
    if removing_manage:
        others = db.count_active_users_with_permission(
            PERMISSION_MANAGE_USERS,
            exclude_user_id=target_user_id,
        )
        if others < 1:
            raise HTTPException(
                status_code=400,
                detail="Deve existir pelo menos um usuário ativo com permissão de gerenciar usuários.",
            )


def build_admin_router() -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["auth-admin"])

    @router.get("/users")
    async def list_users(_actor: dict = Depends(require_manage_users)):
        db = get_auth_db()
        users = db.list_users()
        return {
            "users": [
                _user_admin_dict(user, db.get_permissions_map(user.id))
                for user in users
            ],
            "permission_labels": PERMISSION_LABELS,
        }

    @router.post("/users")
    async def create_user(request: Request, body: CreateUserBody, actor: dict = Depends(require_manage_users)):
        settings = get_settings()
        db = get_auth_db()
        email = body.email.strip().lower()

        allowed = set(settings.allowed_user_email_list)
        if allowed and email not in allowed:
            raise HTTPException(status_code=400, detail="E-mail não autorizado para cadastro.")

        if db.get_user_by_email(email):
            raise HTTPException(status_code=409, detail="Usuário já existe.")

        password = body.password or _temp_password()
        policy_errors = validate_password_policy(password)
        if policy_errors:
            raise HTTPException(status_code=400, detail=policy_errors[0])

        user = db.create_user(email, body.name, hash_password(password))
        db.set_permissions(user.id, {key: False for key in ALL_PERMISSIONS})

        log_action(
            request,
            action="admin.user.create",
            resource=f"user:{user.id}",
            detail={"email": user.email, "name": user.name},
            user=actor,
        )

        payload = _user_admin_dict(user, db.get_permissions_map(user.id))
        if not body.password:
            payload["temporary_password"] = password
        return payload

    @router.delete("/users/{user_id}")
    async def deactivate_user(request: Request, user_id: int, actor: dict = Depends(require_manage_users)):
        actor_id = int(actor["id"])
        if user_id == actor_id:
            raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta.")

        db = get_auth_db()
        target = db.get_user_by_id(user_id)
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        perms = db.get_permissions_map(user_id)
        if perms.get(PERMISSION_MANAGE_USERS):
            others = db.count_active_users_with_permission(
                PERMISSION_MANAGE_USERS,
                exclude_user_id=user_id,
            )
            if others < 1:
                raise HTTPException(
                    status_code=400,
                    detail="Não é possível excluir o último administrador ativo.",
                )

        if not db.deactivate_user(user_id):
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        db.revoke_remember_tokens(user_id)
        log_action(
            request,
            action="admin.user.deactivate",
            resource=f"user:{user_id}",
            detail={"email": target.email},
            user=actor,
        )
        return {"ok": True}

    @router.patch("/users/{user_id}/permissions")
    async def update_permissions(
        request: Request,
        user_id: int,
        body: SetPermissionsBody,
        actor: dict = Depends(require_manage_users),
    ):
        db = get_auth_db()
        target = db.get_user_by_id(user_id)
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        normalized = {key: bool(body.permissions.get(key)) for key in ALL_PERMISSIONS}
        _ensure_can_modify_permissions(
            db,
            actor=actor,
            target_user_id=user_id,
            new_permissions=normalized,
        )
        updated = db.set_permissions(user_id, normalized)

        log_action(
            request,
            action="admin.permissions.update",
            resource=f"user:{user_id}",
            detail={"permissions": updated},
            user=actor,
        )
        return {"permissions": updated}

    @router.post("/users/{user_id}/password")
    async def set_password(
        request: Request,
        user_id: int,
        body: AdminPasswordBody,
        actor: dict = Depends(require_manage_users),
    ):
        db = get_auth_db()
        target = db.get_user_by_id(user_id)
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        policy_errors = validate_password_policy(body.password)
        if policy_errors:
            raise HTTPException(status_code=400, detail=policy_errors[0])

        db.update_password(user_id, hash_password(body.password))
        db.revoke_remember_tokens(user_id)

        log_action(
            request,
            action="admin.user.password",
            resource=f"user:{user_id}",
            detail={"email": target.email},
            user=actor,
        )
        return {"ok": True, "message": "Senha atualizada."}

    @router.post("/users/{user_id}/reset-email")
    async def send_reset_email(
        request: Request,
        user_id: int,
        actor: dict = Depends(require_manage_users),
    ):
        settings = get_settings()
        db = get_auth_db()
        target = db.get_user_by_id(user_id)
        if not target or not target.is_active:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        raw_token = db.create_password_reset_token(
            user_id,
            hours=settings.password_reset_token_hours,
        )
        reset_url = f"{settings.app_base_url.rstrip('/')}/login/reset#token={raw_token}"
        try:
            send_password_reset_email(
                settings,
                to_email=target.email,
                reset_url=reset_url,
                user_name=target.name,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Falha ao enviar e-mail de redefinição.") from exc

        log_action(
            request,
            action="admin.user.reset_email",
            resource=f"user:{user_id}",
            detail={"email": target.email},
            user=actor,
        )
        return {"ok": True, "message": "E-mail de redefinição enviado."}

    @router.get("/audit")
    async def list_audit(
        _actor: dict = Depends(require_manage_users),
        limit: int = 50,
        offset: int = 0,
    ):
        db = get_auth_db()
        entries = db.list_audit_logs(limit=limit, offset=offset)
        return {"entries": [_format_audit_entry(entry) for entry in entries]}

    @router.get("/audit/users/{user_id}")
    async def list_user_audit(
        user_id: int,
        _actor: dict = Depends(require_manage_users),
        limit: int = 50,
        offset: int = 0,
    ):
        db = get_auth_db()
        target = db.get_user_by_id(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        entries = db.list_audit_logs(user_id=user_id, limit=limit, offset=offset)
        return {"entries": [_format_audit_entry(entry) for entry in entries]}

    return router


def _format_audit_entry(entry) -> dict[str, Any]:
    data = entry.to_dict()
    try:
        data["detail"] = json.loads(entry.detail) if entry.detail else {}
    except json.JSONDecodeError:
        data["detail"] = {"raw": entry.detail}
    return data
