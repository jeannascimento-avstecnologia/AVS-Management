from __future__ import annotations

from fastapi import APIRouter

from src.auth.local import build_local_auth_router
from src.auth.m365 import build_auth_router as build_m365_auth_router
from src.config import get_settings


def build_auth_router() -> APIRouter:
    settings = get_settings()
    if settings.auth_provider == "m365":
        return build_m365_auth_router()
    return build_local_auth_router()
