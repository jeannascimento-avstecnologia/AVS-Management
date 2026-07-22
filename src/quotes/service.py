from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import Settings, get_settings
from src.hub.models import HubDatabase
from src.hub.outbox import OutboxConflictError, insert_pending
from src.quotes.pdf import render_quote_pdf
from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer
from src.quotes.schemas import (
    QuoteItemRead,
    QuoteItemWrite,
    QuoteModule,
    QuoteModuleTemplateRead,
    QuoteModuleTemplateUpdate,
    QuoteModuleTemplateWrite,
    QuoteRead,
    QuoteTemplateLine,
    QuoteTemplateRead,
    QuoteTemplateUpdate,
    QuoteTemplateWrite,
    QuoteUpdate,
    QuoteWrite,
    seed_default_modules,
    validate_modules_and_items,
)

_UUID_PDF_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$",
    re.IGNORECASE,
)

_QUOTE_COLUMNS = (
    "id",
    "cnpj",
    "client_name",
    "tiflux_client_id",
    "vhsys_client_id",
    "status",
    "lead_temperature",
    "billed_by_type",
    "billed_by_name",
    "implant_payment_plan",
    "implant_discount_pct",
    "implant_discount_value",
    "implant_labor_hours",
    "implant_labor_hourly_rate",
    "monthly_payment_plan",
    "monthly_discount_pct",
    "monthly_discount_value",
    "monthly_labor_hours",
    "monthly_labor_hourly_rate",
    "modules_json",
    "client_email",
    "extra_recipients",
    "notes",
    "tiflux_ticket_number",
    "vhsys_os_id",
    "pdf_path",
    "created_by",
    "created_at",
    "updated_at",
    "submitted_at",
    "sent_at",
    "approved_at",
)

_EDITABLE_STATUSES = frozenset({"draft"})
_APPROVABLE_STATUSES = frozenset({"draft", "submitted", "sent"})
_SUBMITTABLE_STATUSES = frozenset({"draft"})
_MARK_SENT_STATUSES = frozenset({"submitted"})


class QuoteNotFoundError(Exception):
    pass


class QuoteConflictError(Exception):
    pass


class QuoteSubmitResult:
    """Quote + outbox após submit/mark-sent."""

    __slots__ = ("quote", "outbox_id", "outbox_status", "dry_run")

    def __init__(
        self,
        quote: QuoteRead,
        *,
        outbox_id: int,
        outbox_status: str,
        dry_run: bool,
    ) -> None:
        self.quote = quote
        self.outbox_id = outbox_id
        self.outbox_status = outbox_status
        self.dry_run = dry_run

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.quote.model_dump(),
            "outbox_id": self.outbox_id,
            "outbox_status": self.outbox_status,
            "dry_run": self.dry_run,
        }


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _optional_float(row: sqlite3.Row, key: str) -> float | None:
    try:
        raw = row[key]
    except (KeyError, IndexError):
        return None
    if raw is None:
        return None
    return float(raw)


def _parse_extra_recipients(raw: object) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x).strip().lower() for x in raw if str(x).strip()]
    try:
        data = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip().lower() for x in data if str(x).strip()]


def _dump_extra_recipients(emails: list[str] | None) -> str | None:
    if not emails:
        return None
    return json.dumps(list(emails), ensure_ascii=False)


def _optional_notes(row: sqlite3.Row) -> str | None:
    if "notes" not in row.keys():
        return None
    raw = row["notes"]
    if raw is None:
        return None
    cleaned = str(raw).strip()
    return cleaned or None


def _dump_modules(modules: list[QuoteModule]) -> str:
    return json.dumps([m.model_dump() for m in modules], ensure_ascii=False)


def _legacy_flat_from_modules(modules: list[QuoteModule]) -> dict[str, Any]:
    """Espelha módulos legacy_kind → colunas implant_*/monthly_*; ausentes → None."""
    flat: dict[str, Any] = {
        "implant_payment_plan": None,
        "implant_discount_pct": None,
        "implant_discount_value": None,
        "implant_labor_hours": None,
        "implant_labor_hourly_rate": None,
        "monthly_payment_plan": None,
        "monthly_discount_pct": None,
        "monthly_discount_value": None,
        "monthly_labor_hours": None,
        "monthly_labor_hourly_rate": None,
    }
    for mod in modules:
        if mod.legacy_kind == "implantacao":
            flat["implant_payment_plan"] = mod.payment_plan
            flat["implant_discount_pct"] = mod.discount_pct
            flat["implant_discount_value"] = mod.discount_value
            flat["implant_labor_hours"] = None
            flat["implant_labor_hourly_rate"] = None
        elif mod.legacy_kind == "mensalidade":
            flat["monthly_payment_plan"] = mod.payment_plan
            flat["monthly_discount_pct"] = mod.discount_pct
            flat["monthly_discount_value"] = mod.discount_value
            flat["monthly_labor_hours"] = mod.labor_hours if mod.show_labor else None
            flat["monthly_labor_hourly_rate"] = (
                mod.labor_hourly_rate if mod.show_labor else None
            )
    return flat


def _modules_from_flat_row(row: sqlite3.Row) -> list[QuoteModule]:
    """Legado sem modules_json → sintetiza seed a partir das colunas flat."""
    return [
        QuoteModule(
            id="implantacao",
            title="Implantação",
            legacy_kind="implantacao",
            show_labor=False,
            payment_plan=row["implant_payment_plan"],
            discount_pct=row["implant_discount_pct"],
            discount_value=row["implant_discount_value"],
            labor_hours=None,
            labor_hourly_rate=None,
            sort_order=0,
        ),
        QuoteModule(
            id="mensalidade",
            title="Mensalidade",
            legacy_kind="mensalidade",
            show_labor=True,
            payment_plan=row["monthly_payment_plan"],
            discount_pct=row["monthly_discount_pct"],
            discount_value=row["monthly_discount_value"],
            labor_hours=_optional_float(row, "monthly_labor_hours"),
            labor_hourly_rate=_optional_float(row, "monthly_labor_hourly_rate"),
            sort_order=1,
        ),
    ]


def _parse_modules(row: sqlite3.Row) -> list[QuoteModule]:
    if "modules_json" not in row.keys():
        return _modules_from_flat_row(row)
    raw = row["modules_json"]
    if raw is None or str(raw).strip() == "":
        return _modules_from_flat_row(row)
    try:
        data = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return _modules_from_flat_row(row)
    if not isinstance(data, list):
        return _modules_from_flat_row(row)
    if len(data) == 0:
        return []
    try:
        return [QuoteModule.model_validate(item) for item in data]
    except Exception:
        return _modules_from_flat_row(row)


def _row_to_item(row: sqlite3.Row) -> QuoteItemRead:
    return QuoteItemRead(
        id=int(row["id"]),
        quote_id=int(row["quote_id"]),
        section=row["section"],
        name=str(row["name"]),
        qty=float(row["qty"]),
        unit_value=float(row["unit_value"]),
        total_value=float(row["total_value"]),
        template_key=row["template_key"],
        sort_order=int(row["sort_order"]),
    )


def _row_to_quote(row: sqlite3.Row, items: list[QuoteItemRead]) -> QuoteRead:
    modules = _parse_modules(row)
    return QuoteRead(
        id=int(row["id"]),
        cnpj=str(row["cnpj"]),
        client_name=row["client_name"],
        tiflux_client_id=row["tiflux_client_id"],
        vhsys_client_id=row["vhsys_client_id"],
        status=row["status"],
        lead_temperature=row["lead_temperature"],
        billed_by_type=row["billed_by_type"],
        billed_by_name=row["billed_by_name"],
        implant_payment_plan=row["implant_payment_plan"],
        implant_discount_pct=row["implant_discount_pct"],
        implant_discount_value=row["implant_discount_value"],
        implant_labor_hours=_optional_float(row, "implant_labor_hours"),
        implant_labor_hourly_rate=_optional_float(row, "implant_labor_hourly_rate"),
        monthly_payment_plan=row["monthly_payment_plan"],
        monthly_discount_pct=row["monthly_discount_pct"],
        monthly_discount_value=row["monthly_discount_value"],
        monthly_labor_hours=_optional_float(row, "monthly_labor_hours"),
        monthly_labor_hourly_rate=_optional_float(row, "monthly_labor_hourly_rate"),
        modules=modules,
        client_email=(str(row["client_email"]).strip() if row["client_email"] else None),
        extra_recipients=_parse_extra_recipients(
            row["extra_recipients"] if "extra_recipients" in row.keys() else None
        ),
        notes=_optional_notes(row),
        tiflux_ticket_number=row["tiflux_ticket_number"],
        vhsys_os_id=row["vhsys_os_id"],
        pdf_path=row["pdf_path"],
        created_by=row["created_by"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        submitted_at=row["submitted_at"],
        sent_at=row["sent_at"],
        approved_at=row["approved_at"],
        items=items,
    )


def _fetch_items(conn: sqlite3.Connection, quote_id: int) -> list[QuoteItemRead]:
    rows = conn.execute(
        """
        SELECT id, quote_id, section, name, qty, unit_value, total_value,
               template_key, sort_order
        FROM quote_items
        WHERE quote_id = ?
        ORDER BY section, sort_order, id
        """,
        (quote_id,),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def _insert_items(conn: sqlite3.Connection, quote_id: int, items: list[QuoteItemWrite]) -> None:
    for item in items:
        conn.execute(
            """
            INSERT INTO quote_items (
                quote_id, section, name, qty, unit_value, total_value,
                template_key, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote_id,
                item.section,
                item.name,
                item.qty,
                item.unit_value,
                item.computed_total(),
                item.template_key,
                item.sort_order,
            ),
        )


def _replace_items(conn: sqlite3.Connection, quote_id: int, items: list[QuoteItemWrite]) -> None:
    conn.execute("DELETE FROM quote_items WHERE quote_id = ?", (quote_id,))
    _insert_items(conn, quote_id, items)


def _get_quote_row(conn: sqlite3.Connection, quote_id: int) -> sqlite3.Row | None:
    cols = ", ".join(_QUOTE_COLUMNS)
    return conn.execute(
        f"SELECT {cols} FROM quotes WHERE id = ?",
        (quote_id,),
    ).fetchone()


class QuoteService:
    def __init__(self, db: HubDatabase) -> None:
        self._db = db

    def create(self, data: QuoteWrite, *, created_by: int | None) -> QuoteRead:
        now = _utcnow_iso()
        modules = list(data.modules or seed_default_modules())
        modules = validate_modules_and_items(modules, data.items)
        flat = _legacy_flat_from_modules(modules)
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quotes (
                    cnpj, client_name, tiflux_client_id, vhsys_client_id,
                    status, lead_temperature, billed_by_type, billed_by_name,
                    implant_payment_plan, implant_discount_pct, implant_discount_value,
                    implant_labor_hours, implant_labor_hourly_rate,
                    monthly_payment_plan, monthly_discount_pct, monthly_discount_value,
                    monthly_labor_hours, monthly_labor_hourly_rate,
                    modules_json,
                    client_email, extra_recipients, notes,
                    created_by, created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?,
                    'draft', ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?, ?,
                    ?, ?, ?
                )
                """,
                (
                    data.cnpj,
                    data.client_name,
                    data.tiflux_client_id,
                    data.vhsys_client_id,
                    data.lead_temperature,
                    data.billed_by_type,
                    data.billed_by_name,
                    flat["implant_payment_plan"],
                    flat["implant_discount_pct"],
                    flat["implant_discount_value"],
                    None,  # implant labor always null
                    None,
                    flat["monthly_payment_plan"],
                    flat["monthly_discount_pct"],
                    flat["monthly_discount_value"],
                    flat["monthly_labor_hours"],
                    flat["monthly_labor_hourly_rate"],
                    _dump_modules(modules),
                    data.client_email,
                    _dump_extra_recipients(data.extra_recipients),
                    (data.notes or "").strip() or None,
                    created_by,
                    now,
                    now,
                ),
            )
            quote_id = int(cur.lastrowid)
            _insert_items(conn, quote_id, data.items)
            row = _get_quote_row(conn, quote_id)
            assert row is not None
            return _row_to_quote(row, _fetch_items(conn, quote_id))

    def list(
        self,
        *,
        status: str | None = None,
        lead_temperature: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[QuoteRead]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        cols = ", ".join(f"q.{c}" for c in _QUOTE_COLUMNS)
        sql = f"SELECT {cols} FROM quotes q"
        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("q.status = ?")
            params.append(status)
        if lead_temperature:
            where.append("q.lead_temperature = ?")
            params.append(lead_temperature)
            # Filtro de lead = pipeline aberto (ainda não aprovados / contratados).
            where.append("q.status NOT IN ('approved', 'contracted')")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY q.updated_at DESC, q.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                _row_to_quote(row, _fetch_items(conn, int(row["id"])))
                for row in rows
            ]

    def get(self, quote_id: int) -> QuoteRead:
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            return _row_to_quote(row, _fetch_items(conn, quote_id))

    def update(self, quote_id: int, data: QuoteUpdate) -> QuoteRead:
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            if str(row["status"]) not in _EDITABLE_STATUSES:
                raise QuoteConflictError(
                    f"Orçamento {quote_id} com status '{row['status']}' não pode ser editado."
                )

            patch = data.model_dump(exclude_unset=True)
            items_raw = patch.pop("items", None)
            modules_raw = patch.pop("modules", None)
            # Implantação: mão de obra sempre null (schema mantém colunas)
            if "implant_labor_hours" in patch:
                patch["implant_labor_hours"] = None
            if "implant_labor_hourly_rate" in patch:
                patch["implant_labor_hourly_rate"] = None
            if "extra_recipients" in patch:
                patch["extra_recipients"] = _dump_extra_recipients(patch["extra_recipients"])
            if "notes" in patch:
                raw_notes = patch["notes"]
                patch["notes"] = (str(raw_notes).strip() if raw_notes else None) or None

            typed_items: list[QuoteItemWrite] | None = None
            if items_raw is not None:
                typed_items = [QuoteItemWrite.model_validate(item) for item in items_raw]

            current_modules = _parse_modules(row)
            if modules_raw is not None:
                mods = [QuoteModule.model_validate(m) for m in modules_raw]
                item_check = typed_items if typed_items is not None else [
                    QuoteItemWrite(
                        section=i.section,
                        name=i.name,
                        qty=i.qty,
                        unit_value=i.unit_value,
                        template_key=i.template_key,
                        sort_order=i.sort_order,
                    )
                    for i in _fetch_items(conn, quote_id)
                ]
                mods = validate_modules_and_items(mods, item_check)
                flat = _legacy_flat_from_modules(mods)
                patch.update(flat)
                patch["modules_json"] = _dump_modules(mods)
            elif typed_items is not None:
                # Itens mudaram sem modules — revalidar contra módulos atuais
                validate_modules_and_items(current_modules, typed_items)
            elif any(
                k.startswith("implant_") or k.startswith("monthly_") for k in patch
            ):
                # Patch flat legado → espelhar nos modules
                mods = list(current_modules)
                updated: list[QuoteModule] = []
                for mod in mods:
                    if mod.legacy_kind == "implantacao":
                        updated.append(
                            mod.model_copy(
                                update={
                                    "payment_plan": patch.get(
                                        "implant_payment_plan", mod.payment_plan
                                    ),
                                    "discount_pct": patch.get(
                                        "implant_discount_pct", mod.discount_pct
                                    ),
                                    "discount_value": patch.get(
                                        "implant_discount_value", mod.discount_value
                                    ),
                                    "labor_hours": None,
                                    "labor_hourly_rate": None,
                                    "show_labor": False,
                                }
                            )
                        )
                    elif mod.legacy_kind == "mensalidade":
                        updated.append(
                            mod.model_copy(
                                update={
                                    "payment_plan": patch.get(
                                        "monthly_payment_plan", mod.payment_plan
                                    ),
                                    "discount_pct": patch.get(
                                        "monthly_discount_pct", mod.discount_pct
                                    ),
                                    "discount_value": patch.get(
                                        "monthly_discount_value", mod.discount_value
                                    ),
                                    "labor_hours": patch.get(
                                        "monthly_labor_hours", mod.labor_hours
                                    ),
                                    "labor_hourly_rate": patch.get(
                                        "monthly_labor_hourly_rate",
                                        mod.labor_hourly_rate,
                                    ),
                                }
                            )
                        )
                    else:
                        updated.append(mod)
                patch["modules_json"] = _dump_modules(updated)

            now = _utcnow_iso()
            if patch:
                sets = ", ".join(f"{key} = ?" for key in patch)
                values = list(patch.values())
                values.extend([now, quote_id])
                conn.execute(
                    f"UPDATE quotes SET {sets}, updated_at = ? WHERE id = ?",
                    values,
                )
            else:
                conn.execute(
                    "UPDATE quotes SET updated_at = ? WHERE id = ?",
                    (now, quote_id),
                )

            if typed_items is not None:
                _replace_items(conn, quote_id, typed_items)

            updated = _get_quote_row(conn, quote_id)
            assert updated is not None
            return _row_to_quote(updated, _fetch_items(conn, quote_id))

    def delete(self, quote_id: int) -> None:
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            if str(row["status"]) != "draft":
                raise QuoteConflictError("Só é permitido excluir orçamento em draft.")
            conn.execute("DELETE FROM quotes WHERE id = ?", (quote_id,))

    def approve(self, quote_id: int) -> QuoteRead:
        """Transição local → approved. Outbox quote.approved = O3/fast-follow (não dispara)."""
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            current = str(row["status"])
            if current == "approved":
                return _row_to_quote(row, _fetch_items(conn, quote_id))
            if current not in _APPROVABLE_STATUSES:
                raise QuoteConflictError(
                    f"Não é possível aprovar orçamento com status '{current}'."
                )
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE quotes
                SET status = 'approved', approved_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, quote_id),
            )
            updated = _get_quote_row(conn, quote_id)
            assert updated is not None
            return _row_to_quote(updated, _fetch_items(conn, quote_id))

    def submit(
        self,
        quote_id: int,
        *,
        settings: Settings | None = None,
    ) -> tuple[QuoteSubmitResult, int]:
        """
        draft → submitted + outbox quote.submit (mesmo commit).
        Retorna (result, outbox_id) para dispatch pós-commit.
        """
        cfg = settings or get_settings()
        dry_run = bool(cfg.hub_dry_run)
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            current = str(row["status"])
            if current not in _SUBMITTABLE_STATUSES:
                raise QuoteConflictError(
                    f"Só é possível submeter orçamento em draft (atual: '{current}')."
                )
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE quotes
                SET status = 'submitted', submitted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, quote_id),
            )
            updated = _get_quote_row(conn, quote_id)
            assert updated is not None
            quote = _row_to_quote(updated, _fetch_items(conn, quote_id))
            try:
                outbox_id, _envelope = insert_pending(
                    conn,
                    event="quote.submit",
                    resource_type="quote",
                    resource_id=quote_id,
                    payload={
                        "quote": quote.model_dump(),
                        "pdf_path": quote.pdf_path,
                        "recipients": {
                            "to": quote.client_email,
                            "cc": list(quote.extra_recipients),
                        },
                    },
                    dry_run=dry_run,
                    settings=cfg,
                )
            except OutboxConflictError as exc:
                raise QuoteConflictError(str(exc)) from exc

            result = QuoteSubmitResult(
                quote,
                outbox_id=outbox_id,
                outbox_status="pending",
                dry_run=dry_run,
            )
            return result, outbox_id

    def mark_sent(
        self,
        quote_id: int,
        *,
        settings: Settings | None = None,
    ) -> tuple[QuoteSubmitResult, int]:
        """submitted → sent + outbox quote.sent."""
        cfg = settings or get_settings()
        dry_run = bool(cfg.hub_dry_run)
        with self._db.connect() as conn:
            row = _get_quote_row(conn, quote_id)
            if row is None:
                raise QuoteNotFoundError(f"Orçamento {quote_id} não encontrado.")
            current = str(row["status"])
            if current not in _MARK_SENT_STATUSES:
                raise QuoteConflictError(
                    f"Só é possível mark-sent com status submitted (atual: '{current}')."
                )
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE quotes
                SET status = 'sent', sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, quote_id),
            )
            updated = _get_quote_row(conn, quote_id)
            assert updated is not None
            quote = _row_to_quote(updated, _fetch_items(conn, quote_id))
            try:
                outbox_id, _envelope = insert_pending(
                    conn,
                    event="quote.sent",
                    resource_type="quote",
                    resource_id=quote_id,
                    payload={
                        "quote": quote.model_dump(),
                        "pdf_path": quote.pdf_path,
                    },
                    dry_run=dry_run,
                    settings=cfg,
                )
            except OutboxConflictError as exc:
                raise QuoteConflictError(str(exc)) from exc

            result = QuoteSubmitResult(
                quote,
                outbox_id=outbox_id,
                outbox_status="pending",
                dry_run=dry_run,
            )
            return result, outbox_id

    def list_templates(self) -> list[QuoteTemplateRead]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, key, name, section, lines_json, created_at
                FROM quote_templates
                ORDER BY section, name, id
                """
            ).fetchall()
        return [self._row_to_template(row) for row in rows]

    def get_template(self, template_id: int) -> QuoteTemplateRead:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, key, name, section, lines_json, created_at
                FROM quote_templates
                WHERE id = ?
                """,
                (template_id,),
            ).fetchone()
        if row is None:
            raise QuoteNotFoundError(f"Modelo {template_id} não encontrado.")
        return self._row_to_template(row)

    def create_template(self, data: QuoteTemplateWrite) -> QuoteTemplateRead:
        lines = self._normalize_template_lines(data.lines)
        key = data.key or self._allocate_template_key(data.name, data.section)
        now = _utcnow_iso()
        with self._db.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM quote_templates WHERE key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                raise QuoteConflictError(f"Já existe modelo com key '{key}'.")
            cur = conn.execute(
                """
                INSERT INTO quote_templates (key, name, section, lines_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, data.name, data.section, json.dumps(lines, ensure_ascii=False), now),
            )
            template_id = int(cur.lastrowid)
        return self.get_template(template_id)

    def update_template(
        self, template_id: int, data: QuoteTemplateUpdate
    ) -> QuoteTemplateRead:
        current = self.get_template(template_id)
        name = data.name if data.name is not None else current.name
        section = data.section if data.section is not None else current.section
        if data.lines is not None:
            lines = self._normalize_template_lines(data.lines)
        else:
            lines = [
                {
                    "name": line.name,
                    "qty": line.qty,
                    "unit_value": line.unit_value,
                    "sort_order": line.sort_order,
                }
                for line in current.lines
            ]
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE quote_templates
                SET name = ?, section = ?, lines_json = ?
                WHERE id = ?
                """,
                (name, section, json.dumps(lines, ensure_ascii=False), template_id),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(f"Modelo {template_id} não encontrado.")
        return self.get_template(template_id)

    def delete_template(self, template_id: int) -> None:
        with self._db.connect() as conn:
            cur = conn.execute(
                "DELETE FROM quote_templates WHERE id = ?",
                (template_id,),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(f"Modelo {template_id} não encontrado.")

    def list_module_templates(self) -> list[QuoteModuleTemplateRead]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, key, name, title, show_labor, lines_json, created_at
                FROM quote_module_templates
                ORDER BY name, id
                """
            ).fetchall()
        return [self._row_to_module_template(row) for row in rows]

    def get_module_template(self, template_id: int) -> QuoteModuleTemplateRead:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, key, name, title, show_labor, lines_json, created_at
                FROM quote_module_templates
                WHERE id = ?
                """,
                (template_id,),
            ).fetchone()
        if row is None:
            raise QuoteNotFoundError(f"Modelo de módulo {template_id} não encontrado.")
        return self._row_to_module_template(row)

    def create_module_template(
        self, data: QuoteModuleTemplateWrite
    ) -> QuoteModuleTemplateRead:
        lines = self._normalize_template_lines(data.lines)
        key = data.key or self._allocate_module_template_key(data.name)
        now = _utcnow_iso()
        with self._db.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM quote_module_templates WHERE key = ?",
                (key,),
            ).fetchone()
            if existing is not None:
                raise QuoteConflictError(f"Já existe modelo de módulo com key '{key}'.")
            cur = conn.execute(
                """
                INSERT INTO quote_module_templates
                    (key, name, title, show_labor, lines_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    data.name,
                    data.title,
                    1 if data.show_labor else 0,
                    json.dumps(lines, ensure_ascii=False),
                    now,
                ),
            )
            template_id = int(cur.lastrowid)
        return self.get_module_template(template_id)

    def update_module_template(
        self, template_id: int, data: QuoteModuleTemplateUpdate
    ) -> QuoteModuleTemplateRead:
        current = self.get_module_template(template_id)
        name = data.name if data.name is not None else current.name
        title = data.title if data.title is not None else current.title
        show_labor = (
            data.show_labor if data.show_labor is not None else current.show_labor
        )
        if data.lines is not None:
            lines = self._normalize_template_lines(data.lines)
        else:
            lines = [
                {
                    "name": line.name,
                    "qty": line.qty,
                    "unit_value": line.unit_value,
                    "sort_order": line.sort_order,
                }
                for line in current.lines
            ]
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE quote_module_templates
                SET name = ?, title = ?, show_labor = ?, lines_json = ?
                WHERE id = ?
                """,
                (
                    name,
                    title,
                    1 if show_labor else 0,
                    json.dumps(lines, ensure_ascii=False),
                    template_id,
                ),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(
                    f"Modelo de módulo {template_id} não encontrado."
                )
        return self.get_module_template(template_id)

    def delete_module_template(self, template_id: int) -> None:
        with self._db.connect() as conn:
            cur = conn.execute(
                "DELETE FROM quote_module_templates WHERE id = ?",
                (template_id,),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(
                    f"Modelo de módulo {template_id} não encontrado."
                )

    @staticmethod
    def _row_to_template(row: sqlite3.Row) -> QuoteTemplateRead:
        raw = json.loads(str(row["lines_json"]))
        lines = [QuoteTemplateLine.model_validate(line) for line in raw]
        return QuoteTemplateRead(
            id=int(row["id"]),
            key=str(row["key"]),
            name=str(row["name"]),
            section=row["section"],
            lines=lines,
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _row_to_module_template(row: sqlite3.Row) -> QuoteModuleTemplateRead:
        raw = json.loads(str(row["lines_json"]))
        lines = [QuoteTemplateLine.model_validate(line) for line in raw]
        return QuoteModuleTemplateRead(
            id=int(row["id"]),
            key=str(row["key"]),
            name=str(row["name"]),
            title=str(row["title"]),
            show_labor=bool(row["show_labor"]),
            lines=lines,
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _normalize_template_lines(lines: list[QuoteTemplateLine]) -> list[dict[str, Any]]:
        ordered = sorted(enumerate(lines), key=lambda pair: (pair[1].sort_order, pair[0]))
        return [
            {
                "name": line.name,
                "qty": line.qty,
                "unit_value": line.unit_value,
                "sort_order": idx,
            }
            for idx, (_orig_i, line) in enumerate(ordered)
        ]

    def _allocate_template_key(self, name: str, section: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        if not base:
            base = "modelo"
        prefix = f"{section}_{base}"[:72]
        candidate = prefix
        with self._db.connect() as conn:
            n = 2
            while True:
                exists = conn.execute(
                    "SELECT 1 FROM quote_templates WHERE key = ?",
                    (candidate,),
                ).fetchone()
                if exists is None:
                    return candidate
                candidate = f"{prefix}_{n}"[:80]
                n += 1

    def _allocate_module_template_key(self, name: str) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        if not base:
            base = "modulo"
        prefix = f"mod_{base}"[:72]
        candidate = prefix
        with self._db.connect() as conn:
            n = 2
            while True:
                exists = conn.execute(
                    "SELECT 1 FROM quote_module_templates WHERE key = ?",
                    (candidate,),
                ).fetchone()
                if exists is None:
                    return candidate
                candidate = f"{prefix}_{n}"[:80]
                n += 1

    def _pdf_root(self) -> Path:
        root = Path(get_settings().hub_pdf_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_stored_pdf(self, filename: str) -> Path:
        """Resolve filename UUID sob HUB_PDF_DIR — rejeita path traversal."""
        name = Path(filename).name
        if name != filename or not _UUID_PDF_RE.match(name):
            raise QuoteNotFoundError("PDF inválido ou ausente.")
        root = self._pdf_root()
        target = (root / name).resolve()
        if not target.is_relative_to(root):
            raise QuoteNotFoundError("PDF inválido ou ausente.")
        return target

    def generate_pdf(
        self,
        quote_id: int,
        *,
        issuer: QuotePdfIssuer | None = None,
        client: QuotePdfClient | None = None,
    ) -> tuple[QuoteRead, Path]:
        """Gera PDF (draft/approved/qualquer status), grava UUID sob HUB_PDF_DIR."""
        quote = self.get(quote_id)
        root = self._pdf_root()
        filename = f"{uuid.uuid4()}.pdf"
        dest = (root / filename).resolve()
        if not dest.is_relative_to(root):
            raise QuoteConflictError("Falha ao resolver path do PDF.")

        old_name = quote.pdf_path
        render_quote_pdf(quote, dest, issuer=issuer, client=client)

        now = _utcnow_iso()
        with self._db.connect() as conn:
            conn.execute(
                """
                UPDATE quotes
                SET pdf_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (filename, now, quote_id),
            )
            row = _get_quote_row(conn, quote_id)
            assert row is not None
            updated = _row_to_quote(row, _fetch_items(conn, quote_id))

        if old_name and old_name != filename:
            try:
                old_path = self._resolve_stored_pdf(old_name)
                if old_path.is_file():
                    old_path.unlink()
            except QuoteNotFoundError:
                pass

        return updated, dest

    def get_pdf_file(self, quote_id: int) -> Path:
        """Retorna Path do PDF já gerado; 404 se orçamento ou arquivo inexistente."""
        quote = self.get(quote_id)
        if not quote.pdf_path:
            raise QuoteNotFoundError(f"PDF do orçamento {quote_id} ainda não foi gerado.")
        path = self._resolve_stored_pdf(quote.pdf_path)
        if not path.is_file():
            raise QuoteNotFoundError(f"PDF do orçamento {quote_id} não encontrado no disco.")
        return path
