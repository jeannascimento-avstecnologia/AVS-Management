"""CRUD billing_runs/items/artifacts + approve/prefeitura outbox (ADR-0002/0003)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.config import Settings, get_settings
from src.hub.models import HubDatabase
from src.hub.outbox import OutboxConflictError, insert_pending
from src.billing.schemas import (
    BillingArtifactRead,
    BillingArtifactWrite,
    BillingItemRead,
    BillingItemWrite,
    BillingPrefeituraInput,
    BillingRunRead,
    BillingRunUpdate,
    BillingRunWrite,
)
from src.quotes.totals import apply_stacked_discount

_RUN_COLUMNS = (
    "id",
    "cnpj",
    "client_name",
    "tiflux_client_id",
    "vhsys_client_id",
    "competence",
    "due_date",
    "status",
    "has_retencao",
    "payment_method",
    "gross_total",
    "discount_pct",
    "discount_value",
    "net_total",
    "nf_prefeitura_number",
    "tiflux_ticket_number",
    "vhsys_nf_id",
    "vhsys_cr_id",
    "error_message",
    "approved_by",
    "created_by",
    "created_at",
    "updated_at",
    "approved_at",
    "sent_at",
)

_EDITABLE_STATUSES = frozenset({"draft"})
_APPROVABLE_STATUSES = frozenset({"draft"})
_PREFEITURA_STATUSES = frozenset({"awaiting_prefeitura"})


class BillingNotFoundError(Exception):
    pass


class BillingConflictError(Exception):
    pass


class BillingActionResult:
    """Run + outbox após approve/prefeitura."""

    __slots__ = ("run", "outbox_id", "outbox_status", "dry_run")

    def __init__(
        self,
        run: BillingRunRead,
        *,
        outbox_id: int | None,
        outbox_status: str | None,
        dry_run: bool,
    ) -> None:
        self.run = run
        self.outbox_id = outbox_id
        self.outbox_status = outbox_status
        self.dry_run = dry_run

    def to_dict(self) -> dict[str, Any]:
        payload = self.run.model_dump()
        payload["outbox_id"] = self.outbox_id
        payload["outbox_status"] = self.outbox_status
        payload["dry_run"] = self.dry_run
        return payload


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_bool(value: Any) -> bool:
    return bool(int(value or 0))


def _compute_gross(items: list[BillingItemWrite], gross_total: float | None) -> float | None:
    if gross_total is not None:
        return float(gross_total)
    if not items:
        return None
    return round(sum(item.amount for item in items), 2)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _compute_net(
    gross: float | None,
    *,
    discount_pct: float | None,
    discount_value: float | None,
    has_retencao: bool,
) -> float | None:
    """Líquido após desconto. Com retenção, net fica NULL até input prefeitura."""
    if has_retencao or gross is None:
        return None
    _, net = apply_stacked_discount(gross, discount_pct, discount_value)
    return net


def _row_to_item(row: sqlite3.Row) -> BillingItemRead:
    return BillingItemRead(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        source=row["source"],
        external_ref=row["external_ref"],
        description=str(row["description"]),
        amount=float(row["amount"]),
        sort_order=int(row["sort_order"]),
    )


def _row_to_artifact(row: sqlite3.Row) -> BillingArtifactRead:
    return BillingArtifactRead(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        kind=row["kind"],
        path_or_url=str(row["path_or_url"]),
        created_at=str(row["created_at"]),
    )


def _row_to_run(
    row: sqlite3.Row,
    items: list[BillingItemRead],
    artifacts: list[BillingArtifactRead],
) -> BillingRunRead:
    return BillingRunRead(
        id=int(row["id"]),
        cnpj=str(row["cnpj"]),
        client_name=row["client_name"],
        tiflux_client_id=row["tiflux_client_id"],
        vhsys_client_id=row["vhsys_client_id"],
        competence=str(row["competence"]),
        due_date=row["due_date"],
        status=row["status"],
        has_retencao=_as_bool(row["has_retencao"]),
        payment_method=row["payment_method"],
        gross_total=row["gross_total"],
        discount_pct=_optional_float(row["discount_pct"]) if "discount_pct" in row.keys() else None,
        discount_value=(
            _optional_float(row["discount_value"]) if "discount_value" in row.keys() else None
        ),
        net_total=row["net_total"],
        nf_prefeitura_number=row["nf_prefeitura_number"],
        tiflux_ticket_number=row["tiflux_ticket_number"],
        vhsys_nf_id=row["vhsys_nf_id"],
        vhsys_cr_id=row["vhsys_cr_id"],
        error_message=row["error_message"],
        approved_by=row["approved_by"],
        created_by=row["created_by"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        approved_at=row["approved_at"],
        sent_at=row["sent_at"],
        items=items,
        artifacts=artifacts,
    )


def _fetch_items(conn: sqlite3.Connection, run_id: int) -> list[BillingItemRead]:
    rows = conn.execute(
        """
        SELECT id, run_id, source, external_ref, description, amount, sort_order
        FROM billing_items
        WHERE run_id = ?
        ORDER BY sort_order, id
        """,
        (run_id,),
    ).fetchall()
    return [_row_to_item(row) for row in rows]


def _fetch_artifacts(conn: sqlite3.Connection, run_id: int) -> list[BillingArtifactRead]:
    rows = conn.execute(
        """
        SELECT id, run_id, kind, path_or_url, created_at
        FROM billing_artifacts
        WHERE run_id = ?
        ORDER BY id
        """,
        (run_id,),
    ).fetchall()
    return [_row_to_artifact(row) for row in rows]


def _insert_items(conn: sqlite3.Connection, run_id: int, items: list[BillingItemWrite]) -> None:
    for item in items:
        conn.execute(
            """
            INSERT INTO billing_items (
                run_id, source, external_ref, description, amount, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                item.source,
                item.external_ref,
                item.description,
                item.amount,
                item.sort_order,
            ),
        )


def _replace_items(conn: sqlite3.Connection, run_id: int, items: list[BillingItemWrite]) -> None:
    conn.execute("DELETE FROM billing_items WHERE run_id = ?", (run_id,))
    _insert_items(conn, run_id, items)


def _get_run_row(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    cols = ", ".join(_RUN_COLUMNS)
    return conn.execute(
        f"SELECT {cols} FROM billing_runs WHERE id = ?",
        (run_id,),
    ).fetchone()


def _load_run(conn: sqlite3.Connection, run_id: int) -> BillingRunRead:
    row = _get_run_row(conn, run_id)
    if row is None:
        raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
    return _row_to_run(row, _fetch_items(conn, run_id), _fetch_artifacts(conn, run_id))


def _outbox_payload(run: BillingRunRead) -> dict[str, Any]:
    return {
        "billing_run": run.model_dump(),
        "has_retencao": run.has_retencao,
        "payment_method": run.payment_method,
    }


class BillingService:
    def __init__(self, db: HubDatabase) -> None:
        self._db = db

    def create(self, data: BillingRunWrite, *, created_by: int | None) -> BillingRunRead:
        now = _utcnow_iso()
        gross = _compute_gross(data.items, data.gross_total)
        net = _compute_net(
            gross,
            discount_pct=data.discount_pct,
            discount_value=data.discount_value,
            has_retencao=data.has_retencao,
        )
        with self._db.connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO billing_runs (
                        cnpj, client_name, tiflux_client_id, vhsys_client_id,
                        competence, due_date, status, has_retencao, payment_method,
                        gross_total, discount_pct, discount_value, net_total,
                        created_by, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, 'draft', ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        data.cnpj,
                        data.client_name,
                        data.tiflux_client_id,
                        data.vhsys_client_id,
                        data.competence,
                        data.due_date,
                        1 if data.has_retencao else 0,
                        data.payment_method,
                        gross,
                        data.discount_pct,
                        data.discount_value,
                        net,
                        created_by,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise BillingConflictError(
                    "Já existe faturamento para este cliente/competência."
                ) from exc
            run_id = int(cur.lastrowid)
            _insert_items(conn, run_id, data.items)
            return _load_run(conn, run_id)

    def list(
        self,
        *,
        status: str | None = None,
        competence: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[BillingRunRead]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        cols = ", ".join(f"r.{c}" for c in _RUN_COLUMNS)
        sql = f"SELECT {cols} FROM billing_runs r"
        params: list[Any] = []
        clauses: list[str] = []
        if status:
            clauses.append("r.status = ?")
            params.append(status)
        if competence:
            clauses.append("r.competence = ?")
            params.append(competence)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY r.competence DESC, r.updated_at DESC, r.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._db.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [
                _row_to_run(
                    row,
                    _fetch_items(conn, int(row["id"])),
                    _fetch_artifacts(conn, int(row["id"])),
                )
                for row in rows
            ]

    def get(self, run_id: int) -> BillingRunRead:
        with self._db.connect() as conn:
            return _load_run(conn, run_id)

    def update(self, run_id: int, data: BillingRunUpdate) -> BillingRunRead:
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            if str(row["status"]) not in _EDITABLE_STATUSES:
                raise BillingConflictError(
                    f"Faturamento {run_id} com status '{row['status']}' não pode ser editado."
                )

            patch = data.model_dump(exclude_unset=True)
            items = patch.pop("items", None)
            if "has_retencao" in patch:
                patch["has_retencao"] = 1 if patch["has_retencao"] else 0

            now = _utcnow_iso()
            if patch:
                sets = ", ".join(f"{key} = ?" for key in patch)
                values = list(patch.values())
                values.extend([now, run_id])
                try:
                    conn.execute(
                        f"UPDATE billing_runs SET {sets}, updated_at = ? WHERE id = ?",
                        values,
                    )
                except sqlite3.IntegrityError as exc:
                    raise BillingConflictError(
                        "Já existe faturamento para este cliente/competência."
                    ) from exc
            else:
                conn.execute(
                    "UPDATE billing_runs SET updated_at = ? WHERE id = ?",
                    (now, run_id),
                )

            if items is not None:
                typed = [BillingItemWrite.model_validate(item) for item in items]
                _replace_items(conn, run_id, typed)

            updated_row = _get_run_row(conn, run_id)
            assert updated_row is not None
            current_items = _fetch_items(conn, run_id)
            write_items = [
                BillingItemWrite(
                    source=i.source,
                    external_ref=i.external_ref,
                    description=i.description,
                    amount=i.amount,
                    sort_order=i.sort_order,
                )
                for i in current_items
            ]
            if "gross_total" in patch:
                gross = patch["gross_total"]
            elif items is not None:
                gross = _compute_gross(write_items, None)
            else:
                gross = (
                    float(updated_row["gross_total"])
                    if updated_row["gross_total"] is not None
                    else None
                )
            has_ret = _as_bool(updated_row["has_retencao"])
            discount_pct = _optional_float(updated_row["discount_pct"])
            discount_value = _optional_float(updated_row["discount_value"])
            net = _compute_net(
                gross if gross is None else float(gross),
                discount_pct=discount_pct,
                discount_value=discount_value,
                has_retencao=has_ret,
            )
            conn.execute(
                """
                UPDATE billing_runs
                SET gross_total = ?, net_total = ?, updated_at = ?
                WHERE id = ?
                """,
                (gross, net, now, run_id),
            )
            return _load_run(conn, run_id)

    def delete(self, run_id: int) -> None:
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            if str(row["status"]) != "draft":
                raise BillingConflictError("Só é permitido excluir faturamento em draft.")
            conn.execute("DELETE FROM billing_runs WHERE id = ?", (run_id,))

    def add_artifact(
        self,
        run_id: int,
        data: BillingArtifactWrite,
    ) -> BillingArtifactRead:
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            now = _utcnow_iso()
            cur = conn.execute(
                """
                INSERT INTO billing_artifacts (run_id, kind, path_or_url, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, data.kind, data.path_or_url, now),
            )
            artifact_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE billing_runs SET updated_at = ? WHERE id = ?",
                (now, run_id),
            )
            art_row = conn.execute(
                """
                SELECT id, run_id, kind, path_or_url, created_at
                FROM billing_artifacts WHERE id = ?
                """,
                (artifact_id,),
            ).fetchone()
            assert art_row is not None
            return _row_to_artifact(art_row)

    def delete_artifact(self, run_id: int, artifact_id: int) -> None:
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            art = conn.execute(
                "SELECT id FROM billing_artifacts WHERE id = ? AND run_id = ?",
                (artifact_id, run_id),
            ).fetchone()
            if art is None:
                raise BillingNotFoundError(
                    f"Artefato {artifact_id} não encontrado no faturamento {run_id}."
                )
            conn.execute("DELETE FROM billing_artifacts WHERE id = ?", (artifact_id,))
            conn.execute(
                "UPDATE billing_runs SET updated_at = ? WHERE id = ?",
                (_utcnow_iso(), run_id),
            )

    def approve(
        self,
        run_id: int,
        *,
        approved_by: int | None,
        settings: Settings | None = None,
    ) -> tuple[BillingActionResult, int | None]:
        """
        draft → approved (+ outbox billing.approved) se sem retenção;
        draft → awaiting_prefeitura se has_retencao (sem outbox).
        """
        cfg = settings or get_settings()
        dry_run = bool(cfg.hub_dry_run)
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            current = str(row["status"])
            if current not in _APPROVABLE_STATUSES:
                raise BillingConflictError(
                    f"Só é possível aprovar faturamento em draft (atual: '{current}')."
                )
            now = _utcnow_iso()
            has_ret = _as_bool(row["has_retencao"])

            if has_ret:
                conn.execute(
                    """
                    UPDATE billing_runs
                    SET status = 'awaiting_prefeitura',
                        approved_by = ?, approved_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (approved_by, now, now, run_id),
                )
                run = _load_run(conn, run_id)
                result = BillingActionResult(
                    run,
                    outbox_id=None,
                    outbox_status=None,
                    dry_run=dry_run,
                )
                return result, None

            conn.execute(
                """
                UPDATE billing_runs
                SET status = 'approved',
                    approved_by = ?, approved_at = ?, updated_at = ?,
                    net_total = COALESCE(net_total, gross_total)
                WHERE id = ?
                """,
                (approved_by, now, now, run_id),
            )
            run = _load_run(conn, run_id)
            try:
                outbox_id, _envelope = insert_pending(
                    conn,
                    event="billing.approved",
                    resource_type="billing_run",
                    resource_id=run_id,
                    payload=_outbox_payload(run),
                    dry_run=dry_run,
                    settings=cfg,
                )
            except OutboxConflictError as exc:
                raise BillingConflictError(str(exc)) from exc

            result = BillingActionResult(
                run,
                outbox_id=outbox_id,
                outbox_status="pending",
                dry_run=dry_run,
            )
            return result, outbox_id

    def submit_prefeitura(
        self,
        run_id: int,
        data: BillingPrefeituraInput,
        *,
        approved_by: int | None,
        settings: Settings | None = None,
    ) -> tuple[BillingActionResult, int]:
        """
        awaiting_prefeitura → approved + outbox billing.nf_prefeitura.
        """
        cfg = settings or get_settings()
        dry_run = bool(cfg.hub_dry_run)
        with self._db.connect() as conn:
            row = _get_run_row(conn, run_id)
            if row is None:
                raise BillingNotFoundError(f"Faturamento {run_id} não encontrado.")
            current = str(row["status"])
            if current not in _PREFEITURA_STATUSES:
                raise BillingConflictError(
                    "Só é possível informar NF prefeitura com status "
                    f"awaiting_prefeitura (atual: '{current}')."
                )
            if not _as_bool(row["has_retencao"]):
                raise BillingConflictError(
                    "Branch prefeitura só se aplica a faturamento com retenção."
                )
            now = _utcnow_iso()
            conn.execute(
                """
                UPDATE billing_runs
                SET status = 'approved',
                    nf_prefeitura_number = ?,
                    net_total = ?,
                    approved_by = COALESCE(approved_by, ?),
                    approved_at = COALESCE(approved_at, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    data.nf_prefeitura_number,
                    data.net_total,
                    approved_by,
                    now,
                    now,
                    run_id,
                ),
            )
            run = _load_run(conn, run_id)
            try:
                outbox_id, _envelope = insert_pending(
                    conn,
                    event="billing.nf_prefeitura",
                    resource_type="billing_run",
                    resource_id=run_id,
                    payload=_outbox_payload(run),
                    dry_run=dry_run,
                    settings=cfg,
                )
            except OutboxConflictError as exc:
                raise BillingConflictError(str(exc)) from exc

            result = BillingActionResult(
                run,
                outbox_id=outbox_id,
                outbox_status="pending",
                dry_run=dry_run,
            )
            return result, outbox_id
