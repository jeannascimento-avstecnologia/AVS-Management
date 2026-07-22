from __future__ import annotations

from src.config import Settings, get_settings
from src.hub.models import HubDatabase

_db: HubDatabase | None = None


def get_hub_db(settings: Settings | None = None) -> HubDatabase:
    global _db
    cfg = settings or get_settings()
    if _db is None:
        _db = HubDatabase(cfg.hub_db_path)
    return _db


def reset_hub_db_cache() -> None:
    global _db
    _db = None
