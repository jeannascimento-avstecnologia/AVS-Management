from __future__ import annotations

from src.auth.models import AuthDatabase
from src.config import Settings, get_settings

_db: AuthDatabase | None = None


def get_auth_db(settings: Settings | None = None) -> AuthDatabase:
    global _db
    cfg = settings or get_settings()
    if _db is None:
        _db = AuthDatabase(cfg.auth_db_path)
    return _db


def reset_auth_db_cache() -> None:
    global _db
    _db = None
