from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = _REPO_ROOT / "docs" / "hub" / "schema" / "hub_v1.sql"

# Tabelas canônicas ADR-0002 / hub_v1.sql — usadas no smoke de bootstrap.
HUB_TABLES: tuple[str, ...] = (
    "quotes",
    "quote_items",
    "quote_templates",
    "quote_module_templates",
    "quote_proposal_templates",
    "quote_versions",
    "billing_runs",
    "billing_items",
    "billing_artifacts",
    "webhook_outbox",
)


class HubDatabase:
    """SQLite SoT do hub (quotes/billing/outbox). Sem CRUD de negócio neste módulo."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        schema_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.schema_path = Path(schema_path) if schema_path else DEFAULT_SCHEMA_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Conexão com FK ON + commit/rollback. CRUD de negócio fica em módulos (ex. quotes)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as conn:
            yield conn

    def _schema_applied(self, conn: sqlite3.Connection) -> bool:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quotes' LIMIT 1"
        ).fetchone()
        return row is not None

    def _init_schema(self) -> None:
        if not self.schema_path.is_file():
            raise FileNotFoundError(f"Schema hub não encontrado: {self.schema_path}")

        with self._connect() as conn:
            if not self._schema_applied(conn):
                sql = self.schema_path.read_text(encoding="utf-8")
                conn.executescript(sql)
            self._migrate_quotes_columns(conn)
            self._migrate_relax_section_checks(conn)
            self._migrate_quote_items_columns(conn)
            self._migrate_quote_module_templates(conn)
            self._migrate_quote_module_template_columns(conn)
            self._migrate_quote_proposal_templates(conn)
            self._migrate_quote_versions(conn)
            self._migrate_billing_columns(conn)

    def _migrate_quotes_columns(self, conn: sqlite3.Connection) -> None:
        """ALTER TABLE idempotente para colunas novas em DBs já bootstrapados."""
        existing = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(quotes)").fetchall()
        }
        additions = (
            ("implant_labor_hours", "REAL"),
            ("implant_labor_hourly_rate", "REAL"),
            ("monthly_labor_hours", "REAL"),
            ("monthly_labor_hourly_rate", "REAL"),
            ("modules_json", "TEXT"),
            ("active_quote_version_id", "INTEGER"),
            ("current_version_number", "INTEGER"),
            ("monthly_draft_json", "TEXT"),
            ("client_email", "TEXT"),
            ("extra_recipients", "TEXT"),
            ("notes", "TEXT"),
            ("title", "TEXT"),
        )
        for name, col_type in additions:
            if name not in existing:
                conn.execute(f"ALTER TABLE quotes ADD COLUMN {name} {col_type}")

    def _migrate_quote_items_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(quote_items)").fetchall()
        }
        if "vhsys_product_id" not in existing:
            conn.execute("ALTER TABLE quote_items ADD COLUMN vhsys_product_id INTEGER")

    def _migrate_quote_versions(self, conn: sqlite3.Connection) -> None:
        """Cria quote_versions em DBs já bootstrapados (idempotente)."""
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quote_versions'"
        ).fetchone()
        if row is not None:
            return
        conn.executescript(
            """
            CREATE TABLE quote_versions (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                quote_id                INTEGER NOT NULL
                                        REFERENCES quotes (id) ON DELETE CASCADE,
                version_number         INTEGER NOT NULL,
                snapshot_modules_json  TEXT NOT NULL,
                snapshot_items_json    TEXT NOT NULL,
                snapshot_notes         TEXT,
                snapshot_monthly_json TEXT,
                pdf_path                TEXT,
                created_at              TEXT NOT NULL,
                updated_at              TEXT NOT NULL,
                UNIQUE (quote_id, version_number)
            );
            CREATE INDEX idx_quote_versions_quote_id ON quote_versions (quote_id);
            """
        )

    def _migrate_relax_section_checks(self, conn: sqlite3.Connection) -> None:
        """Recria quote_items / quote_templates sem CHECK binário de section."""
        for table in ("quote_items", "quote_templates"):
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if row is None:
                continue
            ddl = str(row[0] or "")
            if "CHECK (section IN ('implantacao', 'mensalidade'))" not in ddl:
                continue
            if table == "quote_items":
                conn.executescript(
                    """
                    CREATE TABLE quote_items__new (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        quote_id        INTEGER NOT NULL
                                        REFERENCES quotes (id) ON DELETE CASCADE,
                        section         TEXT    NOT NULL,
                        name            TEXT    NOT NULL,
                        qty             REAL    NOT NULL DEFAULT 1,
                        unit_value      REAL    NOT NULL DEFAULT 0,
                        total_value     REAL    NOT NULL,
                        template_key    TEXT,
                        sort_order      INTEGER NOT NULL DEFAULT 0
                    );
                    INSERT INTO quote_items__new
                        SELECT id, quote_id, section, name, qty, unit_value,
                               total_value, template_key, sort_order
                        FROM quote_items;
                    DROP TABLE quote_items;
                    ALTER TABLE quote_items__new RENAME TO quote_items;
                    CREATE INDEX IF NOT EXISTS idx_quote_items_quote_section_sort
                        ON quote_items (quote_id, section, sort_order);
                    """
                )
            else:
                conn.executescript(
                    """
                    CREATE TABLE quote_templates__new (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        key         TEXT    NOT NULL UNIQUE,
                        name        TEXT    NOT NULL,
                        section     TEXT    NOT NULL,
                        lines_json  TEXT    NOT NULL,
                        created_at  TEXT    NOT NULL
                    );
                    INSERT INTO quote_templates__new
                        SELECT id, key, name, section, lines_json, created_at
                        FROM quote_templates;
                    DROP TABLE quote_templates;
                    ALTER TABLE quote_templates__new RENAME TO quote_templates;
                    """
                )

    def _migrate_quote_module_templates(self, conn: sqlite3.Connection) -> None:
        """Cria quote_module_templates em DBs já bootstrapados (idempotente)."""
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quote_module_templates'"
        ).fetchone()
        if row is not None:
            return
        conn.executescript(
            """
            CREATE TABLE quote_module_templates (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                show_labor  INTEGER NOT NULL DEFAULT 0
                            CHECK (show_labor IN (0, 1)),
                notes           TEXT,
                billed_by_name  TEXT,
                lines_json  TEXT    NOT NULL,
                created_at  TEXT    NOT NULL
            );
            """
        )

    def _migrate_quote_module_template_columns(self, conn: sqlite3.Connection) -> None:
        """ALTER TABLE idempotente — defaults de observação / faturado por na biblioteca."""
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quote_module_templates'"
        ).fetchone()
        if exists is None:
            return
        existing = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(quote_module_templates)").fetchall()
        }
        for name, col_type in (
            ("notes", "TEXT"),
            ("billed_by_name", "TEXT"),
            ("billed_by_cnpj", "TEXT"),
            ("simplified", "INTEGER NOT NULL DEFAULT 0"),
            ("display_name", "TEXT"),
        ):
            if name not in existing:
                conn.execute(f"ALTER TABLE quote_module_templates ADD COLUMN {name} {col_type}")

    def _migrate_quote_proposal_templates(self, conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'quote_proposal_templates'"
        ).fetchone()
        if row is not None:
            return
        conn.executescript(
            """
            CREATE TABLE quote_proposal_templates (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                modules_json  TEXT    NOT NULL,
                items_json    TEXT    NOT NULL,
                created_at    TEXT    NOT NULL,
                updated_at    TEXT    NOT NULL
            );
            """
        )

    def _migrate_billing_columns(self, conn: sqlite3.Connection) -> None:
        """ALTER TABLE idempotente — desconto em billing_runs."""
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'billing_runs'"
        ).fetchone()
        if exists is None:
            return
        existing = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(billing_runs)").fetchall()
        }
        for name, col_type in (
            ("discount_pct", "REAL"),
            ("discount_value", "REAL"),
        ):
            if name not in existing:
                conn.execute(f"ALTER TABLE billing_runs ADD COLUMN {name} {col_type}")

    def list_tables(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [str(row["name"]) for row in rows]

    def foreign_keys_enabled(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
        return bool(row[0]) if row is not None else False
