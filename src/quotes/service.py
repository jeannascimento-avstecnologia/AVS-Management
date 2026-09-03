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
from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer
from src.quotes.schemas import (
    QuoteItemRead,
    QuoteItemWrite,
    QuoteModule,
    QuoteModuleTemplateRead,
    QuoteModuleTemplateUpdate,
    QuoteModuleTemplateWrite,
    QuoteProposalTemplateRead,
    QuoteProposalTemplateUpdate,
    QuoteProposalTemplateWrite,
    QuoteRead,
    QuoteMonthlyDraftWrite,
    QuoteVersionRead,
    QuoteTemplateLine,
    QuoteTemplateRead,
    QuoteTemplateUpdate,
    QuoteTemplateWrite,
    QuoteUpdate,
    QuoteWrite,
    seed_default_modules,
    seed_quote_notes,
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
    "active_quote_version_id",
    "current_version_number",
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
    "monthly_draft_json",
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

_QUOTE_VERSION_COLUMNS = (
    "id",
    "quote_id",
    "version_number",
    "snapshot_modules_json",
    "snapshot_items_json",
    "snapshot_notes",
    "snapshot_monthly_json",
    "pdf_path",
    "created_at",
    "updated_at",
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


def _dump_items(items: list[QuoteItemRead]) -> str:
    """Serializa quote_items para snapshot de versão (PDF)."""
    return json.dumps([i.model_dump() for i in items], ensure_ascii=False)


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
        active_quote_version_id=(
            int(row["active_quote_version_id"])
            if "active_quote_version_id" in row.keys() and row["active_quote_version_id"] is not None
            else None
        ),
        current_version_number=(
            int(row["current_version_number"])
            if "current_version_number" in row.keys() and row["current_version_number"] is not None
            else None
        ),
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
        monthly_draft_json=(str(row["monthly_draft_json"]) if "monthly_draft_json" in row.keys() else None),
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
    """Upsert por id (mantém ids p/ mensalidades); remove linhas omitidas."""
    existing = {
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM quote_items WHERE quote_id = ?",
            (quote_id,),
        ).fetchall()
    }
    keep: set[int] = set()
    for item in items:
        total = item.computed_total()
        if item.id is not None and item.id in existing:
            conn.execute(
                """
                UPDATE quote_items
                SET section = ?, name = ?, qty = ?, unit_value = ?, total_value = ?,
                    template_key = ?, sort_order = ?
                WHERE id = ? AND quote_id = ?
                """,
                (
                    item.section,
                    item.name,
                    item.qty,
                    item.unit_value,
                    total,
                    item.template_key,
                    item.sort_order,
                    item.id,
                    quote_id,
                ),
            )
            keep.add(item.id)
        else:
            cur = conn.execute(
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
                    total,
                    item.template_key,
                    item.sort_order,
                ),
            )
            keep.add(int(cur.lastrowid))
    for leftover in existing - keep:
        conn.execute(
            "DELETE FROM quote_items WHERE id = ? AND quote_id = ?",
            (leftover, quote_id),
        )


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
        modules = list(data.modules if data.modules is not None else seed_default_modules())
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
                    seed_quote_notes(data.notes, ticket=None),
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
                SELECT id, key, name, title, show_labor, notes, billed_by_name,
                       billed_by_cnpj, simplified, display_name,
                       lines_json, created_at
                FROM quote_module_templates
                ORDER BY name, id
                """
            ).fetchall()
        return [self._row_to_module_template(row) for row in rows]

    def get_module_template(self, template_id: int) -> QuoteModuleTemplateRead:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, key, name, title, show_labor, notes, billed_by_name,
                       billed_by_cnpj, simplified, display_name,
                       lines_json, created_at
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
                    (key, name, title, show_labor, notes, billed_by_name,
                     billed_by_cnpj, simplified, display_name,
                     lines_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    data.name,
                    data.title,
                    1 if data.show_labor else 0,
                    data.notes,
                    data.billed_by_name,
                    data.billed_by_cnpj,
                    1 if data.simplified else 0,
                    data.display_name,
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
        notes = data.notes if "notes" in data.model_fields_set else current.notes
        billed_by_name = (
            data.billed_by_name
            if "billed_by_name" in data.model_fields_set
            else current.billed_by_name
        )
        billed_by_cnpj = (
            data.billed_by_cnpj
            if "billed_by_cnpj" in data.model_fields_set
            else current.billed_by_cnpj
        )
        simplified = (
            data.simplified if data.simplified is not None else current.simplified
        )
        display_name = (
            data.display_name
            if "display_name" in data.model_fields_set
            else current.display_name
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
                SET name = ?, title = ?, show_labor = ?, notes = ?, billed_by_name = ?,
                    billed_by_cnpj = ?, simplified = ?, display_name = ?,
                    lines_json = ?
                WHERE id = ?
                """,
                (
                    name,
                    title,
                    1 if show_labor else 0,
                    notes,
                    billed_by_name,
                    billed_by_cnpj,
                    1 if simplified else 0,
                    display_name,
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
            notes=row["notes"],
            billed_by_name=row["billed_by_name"],
            billed_by_cnpj=row["billed_by_cnpj"] if "billed_by_cnpj" in row.keys() else None,
            simplified=bool(row["simplified"]) if "simplified" in row.keys() else False,
            display_name=row["display_name"] if "display_name" in row.keys() else None,
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

    def list_proposal_templates(self) -> list[QuoteProposalTemplateRead]:
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, modules_json, items_json, created_at, updated_at
                FROM quote_proposal_templates
                ORDER BY name, id
                """
            ).fetchall()
        return [self._row_to_proposal_template(row) for row in rows]

    def get_proposal_template(self, template_id: int) -> QuoteProposalTemplateRead:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, modules_json, items_json, created_at, updated_at
                FROM quote_proposal_templates
                WHERE id = ?
                """,
                (template_id,),
            ).fetchone()
        if row is None:
            raise QuoteNotFoundError(f"Modelo de orçamento {template_id} não encontrado.")
        return self._row_to_proposal_template(row)

    def create_proposal_template(
        self, data: QuoteProposalTemplateWrite
    ) -> QuoteProposalTemplateRead:
        now = _utcnow_iso()
        modules_json = json.dumps(
            [m.model_dump() for m in data.modules], ensure_ascii=False
        )
        items_json = json.dumps(
            [i.model_dump() for i in data.items], ensure_ascii=False
        )
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO quote_proposal_templates
                    (name, modules_json, items_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (data.name, modules_json, items_json, now, now),
            )
            template_id = int(cur.lastrowid)
        return self.get_proposal_template(template_id)

    def update_proposal_template(
        self, template_id: int, data: QuoteProposalTemplateUpdate
    ) -> QuoteProposalTemplateRead:
        current = self.get_proposal_template(template_id)
        name = data.name if data.name is not None else current.name
        modules = data.modules if data.modules is not None else current.modules
        items = data.items if data.items is not None else current.items
        if data.modules is not None:
            items = data.items if data.items is not None else []
            modules = validate_modules_and_items(modules, items)
        now = _utcnow_iso()
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE quote_proposal_templates
                SET name = ?, modules_json = ?, items_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    json.dumps([m.model_dump() for m in modules], ensure_ascii=False),
                    json.dumps([i.model_dump() for i in items], ensure_ascii=False),
                    now,
                    template_id,
                ),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(
                    f"Modelo de orçamento {template_id} não encontrado."
                )
        return self.get_proposal_template(template_id)

    def delete_proposal_template(self, template_id: int) -> None:
        with self._db.connect() as conn:
            cur = conn.execute(
                "DELETE FROM quote_proposal_templates WHERE id = ?",
                (template_id,),
            )
            if cur.rowcount == 0:
                raise QuoteNotFoundError(
                    f"Modelo de orçamento {template_id} não encontrado."
                )

    @staticmethod
    def _row_to_proposal_template(row: sqlite3.Row) -> QuoteProposalTemplateRead:
        modules_raw = json.loads(str(row["modules_json"]))
        items_raw = json.loads(str(row["items_json"]))
        modules = [QuoteModule.model_validate(m) for m in modules_raw]
        items = [QuoteItemWrite.model_validate(i) for i in items_raw]
        return QuoteProposalTemplateRead(
            id=int(row["id"]),
            name=str(row["name"]),
            modules=modules,
            items=items,
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

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

    def update_monthly_draft(
        self,
        quote_id: int,
        draft: QuoteMonthlyDraftWrite,
    ) -> QuoteRead:
        # valida e persiste rascunho; o snapshot da versão só é criado no clique em "Salvar orçamento"
        allocs = draft.allocations
        with self._db.connect() as conn:
            if allocs:
                license_ids = [a.item_id for a in allocs]
                placeholders = ",".join("?" for _ in license_ids)
                rows = conn.execute(
                    f"""
                    SELECT id, total_value
                    FROM quote_items
                    WHERE quote_id = ? AND id IN ({placeholders})
                    """,
                    (quote_id, *license_ids),
                ).fetchall()
                by_id = {int(r["id"]): float(r["total_value"]) for r in rows}
                if len(by_id) != len(license_ids):
                    raise QuoteNotFoundError(
                        "Mensalidades: alguns quote_items selecionados não pertencem ao orçamento."
                    )
                per_item: list[dict[str, Any]] = []
                for a in allocs:
                    line_total = round(by_id[a.item_id], 2)
                    split = round(float(a.fornecedor_amount) + float(a.intermediador_amount), 2)
                    per_item.append(
                        {
                            "item_id": a.item_id,
                            "line_total": line_total,
                            "split": split,
                            "ok": abs(line_total - split) <= 0.01,
                        }
                    )
                    if abs(line_total - split) > 0.01:
                        raise QuoteConflictError(
                            f"Mensalidades inválidas: fornecedor+intermediador ({split}) "
                            f"deve bater com a linha {a.item_id} ({line_total})."
                        )
                # #region agent log
                try:
                    import time as _t

                    _p = Path("/Users/jean.nascimento/Projetos/avs-management/.cursor/debug-ae8776.log")
                    _p.parent.mkdir(parents=True, exist_ok=True)
                    with _p.open("a", encoding="utf-8") as _fh:
                        _fh.write(
                            json.dumps(
                                {
                                    "sessionId": "ae8776",
                                    "runId": "post-fix",
                                    "hypothesisId": "C",
                                    "location": "service.py:update_monthly_draft",
                                    "message": "backend validates per-line split",
                                    "data": {"per_item": per_item, "per_item_mode": True},
                                    "timestamp": int(_t.time() * 1000),
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                except Exception:
                    pass
                # #endregion
                monthly_json = json.dumps(draft.model_dump(), ensure_ascii=False)
            else:
                monthly_json = None
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE quotes
                SET monthly_draft_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (monthly_json, now, quote_id),
            )
            updated_row = _get_quote_row(conn, quote_id)
            assert updated_row is not None
            return _row_to_quote(updated_row, _fetch_items(conn, quote_id))

    def list_versions(self, quote_id: int, *, limit: int = 100) -> list[QuoteVersionRead]:
        limit = max(1, min(limit, 200))
        with self._db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, quote_id, version_number, snapshot_notes, snapshot_monthly_json,
                       pdf_path, created_at
                FROM quote_versions
                WHERE quote_id = ?
                ORDER BY version_number DESC, id DESC
                LIMIT ?
                """,
                (quote_id, limit),
            ).fetchall()
        return [
            QuoteVersionRead(
                id=int(r["id"]),
                quote_id=int(r["quote_id"]),
                version_number=int(r["version_number"]),
                snapshot_notes=r["snapshot_notes"],
                snapshot_monthly_json=r["snapshot_monthly_json"],
                pdf_path=r["pdf_path"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]

    def _row_to_version(self, row: sqlite3.Row) -> QuoteVersionRead:
        return QuoteVersionRead(
            id=int(row["id"]),
            quote_id=int(row["quote_id"]),
            version_number=int(row["version_number"]),
            snapshot_notes=row["snapshot_notes"],
            snapshot_monthly_json=row["snapshot_monthly_json"],
            pdf_path=row["pdf_path"],
            created_at=str(row["created_at"]),
        )

    def get_version(self, quote_id: int, version_id: int) -> QuoteVersionRead:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, quote_id, version_number, snapshot_notes, snapshot_monthly_json,
                       pdf_path, created_at
                FROM quote_versions
                WHERE id = ? AND quote_id = ?
                """,
                (version_id, quote_id),
            ).fetchone()
        if row is None:
            raise QuoteNotFoundError(
                f"Versão {version_id} não encontrada no orçamento {quote_id}."
            )
        return self._row_to_version(row)

    def create_version(
        self,
        quote_id: int,
        *,
        created_by: int | None,
        settings: Settings | None = None,
    ) -> QuoteVersionRead:
        # settings reservado para futuras validações/flags
        _ = settings
        _ = created_by
        quote = self.get(quote_id)
        snapshot_modules_json = _dump_modules(quote.modules)
        snapshot_items_json = _dump_items(quote.items)
        now = _utcnow_iso()
        with self._db.connect() as conn:
            cur = conn.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1 AS next_v
                FROM quote_versions
                WHERE quote_id = ?
                """,
                (quote_id,),
            )
            next_v = int(cur.fetchone()["next_v"])
            cur2 = conn.execute(
                """
                INSERT INTO quote_versions (
                    quote_id, version_number,
                    snapshot_modules_json, snapshot_items_json,
                    snapshot_notes, snapshot_monthly_json,
                    pdf_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    quote_id,
                    next_v,
                    snapshot_modules_json,
                    snapshot_items_json,
                    quote.notes,
                    quote.monthly_draft_json,
                    now,
                    now,
                ),
            )
            version_id = int(cur2.lastrowid)
            conn.execute(
                """
                UPDATE quotes
                SET active_quote_version_id = ?, current_version_number = ?, updated_at = ?
                WHERE id = ?
                """,
                (version_id, next_v, now, quote_id),
            )

        self.generate_pdf(quote_id, version_id=version_id)
        return self.get_version(quote_id, version_id)

    def generate_pdf(
        self,
        quote_id: int,
        *,
        issuer: QuotePdfIssuer | None = None,
        client: QuotePdfClient | None = None,
        version_id: int | None = None,
        from_live: bool = False,
    ) -> tuple[QuoteRead, Path]:
        """Gera PDF da versão pedida (default: ativa) e salva UUID sob HUB_PDF_DIR."""
        quote = self.get(quote_id)
        live_item_n = len(quote.items)
        live_mod_ids = [m.id for m in quote.modules]
        live_item_sections = [i.section for i in quote.items]
        if from_live:
            target_version_id = None
            version_number = quote.current_version_number
            snapshot_monthly_json = quote.monthly_draft_json
            old_version_pdf = None
            overlay_item_n = live_item_n
            used = "live"
        else:
            target_version_id = version_id if version_id is not None else quote.active_quote_version_id
            version_number = None
            snapshot_monthly_json = quote.monthly_draft_json
            old_version_pdf = None
            overlay_item_n = -1
            used = "snapshot"
            if target_version_id is not None:
                with self._db.connect() as conn:
                    v = conn.execute(
                        """
                        SELECT version_number, snapshot_modules_json, snapshot_items_json,
                               snapshot_notes, snapshot_monthly_json, id, pdf_path
                        FROM quote_versions
                        WHERE id = ? AND quote_id = ?
                        """,
                        (target_version_id, quote_id),
                    ).fetchone()
                    if v is None:
                        target_version_id = None
                    else:
                        version_number = int(v["version_number"])
                        snapshot_monthly_json = v["snapshot_monthly_json"]
                        snapshot_notes = v["snapshot_notes"]
                        old_version_pdf = v["pdf_path"]
                        modules_raw = json.loads(str(v["snapshot_modules_json"] or "[]"))
                        items_raw = json.loads(str(v["snapshot_items_json"] or "[]"))
                        modules = [QuoteModule.model_validate(m) for m in modules_raw]
                        items = [QuoteItemRead.model_validate(i) for i in items_raw]
                        overlay_item_n = len(items)
                        quote = quote.model_copy(
                            update={
                                "modules": modules,
                                "items": items,
                                "notes": snapshot_notes,
                            }
                        )
            else:
                overlay_item_n = live_item_n
                used = "live-fallback"
        root = self._pdf_root()
        filename = f"{uuid.uuid4()}.pdf"
        dest = (root / filename).resolve()
        if not dest.is_relative_to(root):
            raise QuoteConflictError("Falha ao resolver path do PDF.")

        from src.quotes.pdf import _agent_dbg, render_quote_pdf

        # #region agent log
        _agent_dbg(
            "F",
            "service.py:generate_pdf",
            "pdf source live vs snapshot",
            {
                "from_live": from_live,
                "used": used,
                "live_item_n": live_item_n,
                "overlay_item_n": overlay_item_n,
                "render_item_n": len(quote.items),
                "live_mod_ids": live_mod_ids,
                "render_mod_ids": [m.id for m in quote.modules],
                "live_item_sections": live_item_sections,
                "render_item_sections": [i.section for i in quote.items],
            },
        )
        # #endregion

        render_quote_pdf(
            quote,
            dest,
            issuer=issuer,
            client=client,
            version_number=version_number,
            monthly_draft_json=snapshot_monthly_json,
        )

        now = _utcnow_iso()
        with self._db.connect() as conn:
            if target_version_id is not None:
                if old_version_pdf and old_version_pdf != filename:
                    try:
                        old_path = self._resolve_stored_pdf(str(old_version_pdf))
                        if old_path.is_file():
                            old_path.unlink()
                    except QuoteNotFoundError:
                        pass
                conn.execute(
                    """
                    UPDATE quote_versions
                    SET pdf_path = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (filename, now, target_version_id),
                )
                live = _get_quote_row(conn, quote_id)
                active = (
                    int(live["active_quote_version_id"])
                    if live is not None and live["active_quote_version_id"] is not None
                    else None
                )
                if active == target_version_id:
                    conn.execute(
                        """
                        UPDATE quotes
                        SET pdf_path = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (filename, now, quote_id),
                    )
            else:
                old_name = quote.pdf_path
                if old_name and old_name != filename:
                    try:
                        old_path = self._resolve_stored_pdf(old_name)
                        if old_path.is_file():
                            old_path.unlink()
                    except QuoteNotFoundError:
                        pass
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

    def get_version_pdf_file(self, quote_id: int, version_id: int) -> Path:
        with self._db.connect() as conn:
            row = conn.execute(
                """
                SELECT pdf_path
                FROM quote_versions
                WHERE id = ? AND quote_id = ?
                """,
                (version_id, quote_id),
            ).fetchone()
        if row is None:
            raise QuoteNotFoundError(f"Versão {version_id} não encontrada no orçamento {quote_id}.")
        pdf_path = row["pdf_path"]
        if not pdf_path:
            _, dest = self.generate_pdf(quote_id, version_id=version_id)
            return dest
        path = self._resolve_stored_pdf(str(pdf_path))
        if not path.is_file():
            raise QuoteNotFoundError(
                f"PDF da versão {version_id} não encontrado no disco."
            )
        return path
