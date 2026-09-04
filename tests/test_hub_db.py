from __future__ import annotations

from pathlib import Path

import pytest

from src.config import clear_settings_cache, get_settings
from src.hub.models import HUB_TABLES, HubDatabase
from src.hub.store import get_hub_db, reset_hub_db_cache


@pytest.fixture()
def hub_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "hub.db"
    monkeypatch.setenv("HUB_DB_PATH", str(db_path))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    clear_settings_cache()
    reset_hub_db_cache()
    yield db_path
    reset_hub_db_cache()
    clear_settings_cache()


def test_hub_database_applies_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "hub.db"
    db = HubDatabase(db_path)
    assert db_path.is_file()
    assert db.foreign_keys_enabled() is True
    tables = set(db.list_tables())
    assert tables == set(HUB_TABLES)


def test_hub_database_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "hub.db"
    HubDatabase(db_path)
    HubDatabase(db_path)  # re-open must not raise
    assert set(HubDatabase(db_path).list_tables()) == set(HUB_TABLES)


def test_repair_stale_quote_items_fk(tmp_path: Path) -> None:
    """Filho com REFERENCES quotes__old_status (ALTER SQLite) volta a apontar para quotes."""
    import sqlite3

    db_path = tmp_path / "hub_stale_fk.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        INSERT INTO quotes (cnpj, status, created_at, updated_at)
        VALUES ('12345678000199', 'draft', '2026-01-01', '2026-01-01');
        CREATE TABLE quote_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER NOT NULL REFERENCES "quotes__old_status" (id) ON DELETE CASCADE,
            section TEXT NOT NULL,
            name TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 1,
            unit_value REAL NOT NULL DEFAULT 0,
            total_value REAL NOT NULL,
            template_key TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.close()
    db = HubDatabase(db_path)
    with db.connect() as opened:
        opened.execute("PRAGMA foreign_keys = ON")
        parents = {str(row[2]) for row in opened.execute("PRAGMA foreign_key_list(quote_items)")}
        assert "quotes" in parents
        assert "quotes__old_status" not in parents
        opened.execute(
            """
            INSERT INTO quote_items (
                quote_id, section, name, qty, unit_value, total_value, sort_order
            ) VALUES (1, 'mensalidade', 'Licenca', 1, 10, 10, 0)
            """
        )
        row = opened.execute("SELECT COUNT(*) FROM quote_items").fetchone()
        assert int(row[0]) == 1


def test_migrate_quote_module_templates_on_existing_db(tmp_path: Path) -> None:
    """DB bootstrapado sem a tabela → migração cria quote_module_templates."""
    db_path = tmp_path / "hub_legacy.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE quote_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            section TEXT NOT NULL,
            lines_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.close()
    db = HubDatabase(db_path)
    assert "quote_module_templates" in db.list_tables()


def test_migrate_quote_module_template_notes_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "hub_legacy_mod.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE quote_module_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            show_labor INTEGER NOT NULL DEFAULT 0,
            lines_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.close()
    db = HubDatabase(db_path)
    with db.connect() as opened:
        cols = {str(row[1]) for row in opened.execute("PRAGMA table_info(quote_module_templates)")}
    assert "notes" in cols
    assert "billed_by_name" in cols


def test_migrate_quotes_internal_notes_column(tmp_path: Path) -> None:
    db_path = tmp_path / "hub_legacy_internal.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cnpj TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.close()
    db = HubDatabase(db_path)
    with db.connect() as opened:
        cols = {str(row[1]) for row in opened.execute("PRAGMA table_info(quotes)")}
    assert "internal_notes" in cols


def test_get_hub_db_uses_settings(hub_env: Path) -> None:
    settings = get_settings()
    assert settings.hub_db_path == str(hub_env)
    assert settings.hub_dry_run is True
    db = get_hub_db(settings)
    assert Path(db.db_path) == hub_env
    assert hub_env.is_file()
    assert set(db.list_tables()) == set(HUB_TABLES)


def test_hub_settings_defaults() -> None:
    clear_settings_cache()
    settings = get_settings()
    assert settings.hub_db_path == "data/hub.db"
    assert settings.hub_dry_run is True
    assert settings.hub_dry_run_notify_n8n is False
    assert settings.hub_outbox_max_attempts == 5
    assert settings.hub_pdf_dir == "data/hub_pdfs"
    assert settings.tiflux_desk_comercial_id == 36089
