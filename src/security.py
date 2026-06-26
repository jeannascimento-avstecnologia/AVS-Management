from __future__ import annotations

import logging
import re
import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_WEAK_SESSION_SECRETS = frozenset(
    {
        "change-me-in-production",
        "change-me-in-production-use-long-random-string",
        "secret",
        "test-secret-key-for-pytest-only",
    }
)

_SENSITIVE_PATTERNS = re.compile(
    r"(token|secret|password|bearer|api[_-]?key|authorization)",
    re.IGNORECASE,
)

_LOCAL_HOST_MARKERS = ("127.0.0.1", "localhost", "testserver", "0.0.0.0")

CSRF_HEADER = "x-csrf-token"

# POST públicos sem sessão CSRF — manter alinhado com frontend/src/api/csrf.ts
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/auth/login",
        "/auth/forgot-password",
        "/auth/reset-password",
        "/health",
    }
)

# Subconjunto enviado pelo frontend (sem /health: apenas GET)
FRONTEND_CSRF_EXEMPT_PATHS = frozenset(
    {
        "/auth/login",
        "/auth/forgot-password",
        "/auth/reset-password",
    }
)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def is_local_app_url(settings: Settings) -> bool:
    host = settings.app_base_url.lower()
    return any(marker in host for marker in _LOCAL_HOST_MARKERS)


def requires_strict_security(settings: Settings) -> bool:
    """Produção explícita ou deploy não-local quando APP_ENV não restringe dev."""
    env = settings.app_env.strip().lower()
    if env in ("production", "prod"):
        return True
    if env in ("development", "dev", "local", "test"):
        return False
    return not is_local_app_url(settings)


def is_non_local_deployment(settings: Settings) -> bool:
    return requires_strict_security(settings)


def is_csrf_exempt_path(path: str) -> bool:
    return path in CSRF_EXEMPT_PATHS


def build_content_security_policy(settings: Settings) -> str | None:
    """CSP em produção; omitido em dev (Vite HMR / inline theme bootstrap)."""
    if not requires_strict_security(settings):
        return None
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def client_ip(request: Request, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    direct = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    trusted = set(cfg.trusted_proxy_ip_list)
    if forwarded and direct in trusted:
        return forwarded.split(",")[0].strip()
    return direct


def safe_error_message(exc: Exception, *, settings: Settings | None = None) -> str:
    """Evita vazar detalhes internos em respostas HTTP."""
    cfg = settings or get_settings()
    if not cfg.auth_enabled:
        return str(exc)
    message = str(exc).strip()
    if not message:
        return "Erro interno do servidor."
    if _SENSITIVE_PATTERNS.search(message):
        return "Erro interno do servidor."
    if len(message) > 200:
        return "Erro interno do servidor."
    return message


def validate_security_settings(settings: Settings) -> None:
    strict = requires_strict_security(settings)
    if not settings.auth_enabled:
        message = (
            "AUTH_ENABLED=false: todas as rotas da API estão acessíveis sem login. "
            "Não use em produção."
        )
        if strict:
            raise RuntimeError(message)
        logger.warning(message)
        return
    weak_secret = (
        settings.session_secret.strip() in _WEAK_SESSION_SECRETS
        or len(settings.session_secret) < 32
    )
    if weak_secret:
        message = (
            "SESSION_SECRET fraco ou padrão com AUTH_ENABLED=true. "
            "Defina um valor aleatório com pelo menos 32 caracteres no .env."
        )
        if strict:
            raise RuntimeError(message)
        logger.error(message)


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.auth_enabled:
            return await call_next(request)
        if request.method not in _UNSAFE_METHODS:
            return await call_next(request)
        if is_csrf_exempt_path(request.url.path):
            return await call_next(request)

        session_token = request.session.get("csrf_token")
        if not session_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token ausente. Recarregue a página."},
            )
        header_token = request.headers.get(CSRF_HEADER, "")
        if not header_token or not secrets.compare_digest(header_token, session_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token inválido."},
            )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        csp = build_content_security_policy(settings)
        if csp:
            response.headers.setdefault("Content-Security-Policy", csp)
        if settings.app_base_url.startswith("https://"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
