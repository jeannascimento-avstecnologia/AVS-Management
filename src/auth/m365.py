from __future__ import annotations

import msal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.config import Settings, get_settings

SCOPES = ["User.Read"]


def _build_msal_app(settings: Settings) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        settings.azure_client_id,
        authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        client_credential=settings.azure_client_secret,
    )


def build_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/login")
    async def login(request: Request):
        settings = get_settings()
        if not settings.auth_enabled:
            request.session["user"] = {
                "email": "dev@local",
                "name": "Desenvolvimento",
                "dev_mode": True,
            }
            return RedirectResponse(url="/", status_code=302)

        if not settings.azure_tenant_id or not settings.azure_client_id:
            raise HTTPException(
                status_code=500,
                detail="Azure AD não configurado (AZURE_TENANT_ID / AZURE_CLIENT_ID).",
            )

        app_msal = _build_msal_app(settings)
        flow = app_msal.initiate_auth_code_flow(
            scopes=SCOPES,
            redirect_uri=settings.azure_redirect_uri,
        )
        request.session["auth_flow"] = flow
        return RedirectResponse(flow["auth_uri"], status_code=302)

    @router.get("/callback")
    async def callback(request: Request):
        settings = get_settings()
        if not settings.auth_enabled:
            return RedirectResponse(url="/", status_code=302)

        flow = request.session.pop("auth_flow", None)
        if not flow:
            raise HTTPException(status_code=400, detail="Fluxo de login expirado. Tente novamente.")

        app_msal = _build_msal_app(settings)
        result = app_msal.acquire_token_by_auth_code_flow(flow, dict(request.query_params))
        if "error" in result:
            raise HTTPException(
                status_code=401,
                detail=result.get("error_description") or result.get("error"),
            )

        claims = result.get("id_token_claims") or {}
        email = (
            claims.get("preferred_username")
            or claims.get("email")
            or claims.get("upn")
            or ""
        ).lower().strip()
        name = claims.get("name") or email

        allowed = set(settings.allowed_user_email_list)
        if allowed and email not in allowed:
            raise HTTPException(
                status_code=403,
                detail="Usuário não autorizado a acessar o AVS Management.",
            )

        request.session["user"] = {"email": email, "name": name}
        return RedirectResponse(url="/", status_code=302)

    @router.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(url="/auth/login", status_code=302)

    @router.get("/me")
    async def me(request: Request):
        settings = get_settings()
        user = request.session.get("user")
        if not user and settings.auth_enabled:
            raise HTTPException(status_code=401, detail="Não autenticado.")
        if not user:
            user = {"email": "dev@local", "name": "Desenvolvimento", "dev_mode": True}
        return {"authenticated": True, "user": user}

    return router
