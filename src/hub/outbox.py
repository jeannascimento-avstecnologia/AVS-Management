"""Outbox confiável + dispatch n8n (ADR-0003)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

import httpx

from src.config import Settings, get_settings
from src.hub.hmac import HmacSecretMissingError, SIGNATURE_HEADER, sign_body
from src.hub.models import HubDatabase

logger = logging.getLogger(__name__)

OutboxEvent = Literal[
    "quote.submit",
    "quote.sent",
    "quote.approved",
    "billing.approved",
    "billing.nf_prefeitura",
]
OutboxStatus = Literal["pending", "sent", "acked", "error"]
ResourceType = Literal["quote", "billing_run"]

_MAX_PAYLOAD_BYTES = 1_048_576  # 1 MiB — path/body safety básica


class OutboxError(Exception):
    pass


class OutboxConflictError(OutboxError):
    pass


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def idempotency_key(event: OutboxEvent, resource_type: ResourceType, resource_id: int) -> str:
    return f"{event}:{resource_type}:{resource_id}"


def _callback_url(settings: Settings) -> str:
    base = settings.app_base_url.rstrip("/")
    return f"{base}/webhooks/n8n/callback"


def _webhook_url_for_event(settings: Settings, event: str) -> str:
    if event.startswith("billing."):
        return (settings.n8n_billing_webhook_url or "").strip()
    return (settings.n8n_commercial_webhook_url or "").strip()


def _is_safe_webhook_url(url: str) -> bool:
    """Bloqueia file:// / javascript: e exige http(s)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def build_envelope(
    *,
    event: OutboxEvent,
    resource_type: ResourceType,
    resource_id: int,
    outbox_id: int,
    key: str,
    dry_run: bool,
    callback_url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event": event,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "outbox_id": outbox_id,
        "idempotency_key": key,
        "dry_run": dry_run,
        "callback_url": callback_url,
        "payload": payload,
    }


def insert_pending(
    conn: sqlite3.Connection,
    *,
    event: OutboxEvent,
    resource_type: ResourceType,
    resource_id: int,
    payload: dict[str, Any],
    dry_run: bool,
    settings: Settings | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Insert outbox pending no mesmo commit do caller.
    Rejeita se já existir sent/acked para a mesma idempotency_key.
    Se pending/error existir, reutiliza (atualiza payload) — idempotency.
    """
    cfg = settings or get_settings()
    key = idempotency_key(event, resource_type, resource_id)
    now = _utcnow_iso()

    existing = conn.execute(
        """
        SELECT id, status FROM webhook_outbox
        WHERE idempotency_key = ?
        """,
        (key,),
    ).fetchone()

    if existing is not None:
        status = str(existing["status"])
        if status in ("sent", "acked"):
            raise OutboxConflictError(
                f"Evento {key} já foi enviado (status={status})."
            )
        outbox_id = int(existing["id"])
        envelope = build_envelope(
            event=event,
            resource_type=resource_type,
            resource_id=resource_id,
            outbox_id=outbox_id,
            key=key,
            dry_run=dry_run,
            callback_url=_callback_url(cfg),
            payload=payload,
        )
        raw = json.dumps(envelope, ensure_ascii=False)
        if len(raw.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
            raise OutboxError("payload_json excede limite de 1 MiB.")
        conn.execute(
            """
            UPDATE webhook_outbox
            SET payload_json = ?, status = 'pending', last_error = NULL, updated_at = ?
            WHERE id = ?
            """,
            (raw, now, outbox_id),
        )
        return outbox_id, envelope

    # Placeholder envelope (outbox_id preenchido após insert)
    placeholder = build_envelope(
        event=event,
        resource_type=resource_type,
        resource_id=resource_id,
        outbox_id=0,
        key=key,
        dry_run=dry_run,
        callback_url=_callback_url(cfg),
        payload=payload,
    )
    raw_ph = json.dumps(placeholder, ensure_ascii=False)
    cur = conn.execute(
        """
        INSERT INTO webhook_outbox (
            event, payload_json, status, attempts, last_error,
            idempotency_key, created_at, updated_at
        ) VALUES (?, ?, 'pending', 0, NULL, ?, ?, ?)
        """,
        (event, raw_ph, key, now, now),
    )
    outbox_id = int(cur.lastrowid)
    envelope = build_envelope(
        event=event,
        resource_type=resource_type,
        resource_id=resource_id,
        outbox_id=outbox_id,
        key=key,
        dry_run=dry_run,
        callback_url=_callback_url(cfg),
        payload=payload,
    )
    raw = json.dumps(envelope, ensure_ascii=False)
    if len(raw.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise OutboxError("payload_json excede limite de 1 MiB.")
    conn.execute(
        "UPDATE webhook_outbox SET payload_json = ?, updated_at = ? WHERE id = ?",
        (raw, now, outbox_id),
    )
    return outbox_id, envelope


def mark_status(
    conn: sqlite3.Connection,
    outbox_id: int,
    status: OutboxStatus,
    *,
    last_error: str | None = None,
    bump_attempts: bool = False,
    acked: bool = False,
) -> None:
    now = _utcnow_iso()
    if bump_attempts:
        conn.execute(
            """
            UPDATE webhook_outbox
            SET status = ?, last_error = ?, attempts = attempts + 1,
                updated_at = ?, acked_at = CASE WHEN ? THEN ? ELSE acked_at END
            WHERE id = ?
            """,
            (status, last_error, now, 1 if acked else 0, now if acked else None, outbox_id),
        )
    else:
        conn.execute(
            """
            UPDATE webhook_outbox
            SET status = ?, last_error = ?, updated_at = ?,
                acked_at = CASE WHEN ? THEN ? ELSE acked_at END
            WHERE id = ?
            """,
            (status, last_error, now, 1 if acked else 0, now if acked else None, outbox_id),
        )


async def dispatch_outbox(
    db: HubDatabase,
    outbox_id: int,
    *,
    settings: Settings | None = None,
) -> str:
    """
    Após commit: envia HTTP ao n8n ou simula em dry-run.
    Retorna status final: sent | pending | error.
    """
    cfg = settings or get_settings()

    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, event, payload_json, status, attempts FROM webhook_outbox WHERE id = ?",
            (outbox_id,),
        ).fetchone()
        if row is None:
            raise OutboxError(f"Outbox {outbox_id} não encontrado.")
        if str(row["status"]) not in ("pending", "error"):
            return str(row["status"])

        envelope: dict[str, Any] = json.loads(str(row["payload_json"]))
        event = str(row["event"])
        attempts = int(row["attempts"])
        max_attempts = max(1, cfg.hub_outbox_max_attempts)
        if attempts >= max_attempts:
            mark_status(conn, outbox_id, "error", last_error="max attempts exceeded")
            return "error"

        dry_run = bool(cfg.hub_dry_run) or bool(envelope.get("dry_run"))
        notify = bool(cfg.hub_dry_run_notify_n8n)

        # ADR-0003: dry-run MVP → skip HTTP (simula sent) salvo HUB_DRY_RUN_NOTIFY_N8N
        if dry_run and not notify:
            mark_status(conn, outbox_id, "sent", last_error=None)
            logger.info("outbox %s dry-run simulated sent (no HTTP)", outbox_id)
            return "sent"

        url = _webhook_url_for_event(cfg, event)  # event from DB CHECK constraint
        if not url:
            mark_status(
                conn,
                outbox_id,
                "error",
                last_error="webhook URL vazia",
                bump_attempts=True,
            )
            return "error"
        if not _is_safe_webhook_url(url):
            mark_status(
                conn,
                outbox_id,
                "error",
                last_error="webhook URL inválida",
                bump_attempts=True,
            )
            return "error"

        body_bytes = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        try:
            signature = sign_body(cfg.n8n_webhook_secret, body_bytes)
        except HmacSecretMissingError:
            mark_status(
                conn,
                outbox_id,
                "error",
                last_error="N8N_WEBHOOK_SECRET ausente (fail closed)",
                bump_attempts=True,
            )
            return "error"

    # HTTP fora da transação de leitura acima — nova conexão para update
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    SIGNATURE_HEADER: signature,
                },
            )
        if 200 <= response.status_code < 300:
            with db.connect() as conn:
                mark_status(conn, outbox_id, "sent", bump_attempts=True)
            return "sent"
        err = f"HTTP {response.status_code}"
        with db.connect() as conn:
            mark_status(conn, outbox_id, "error", last_error=err, bump_attempts=True)
        return "error"
    except Exception as exc:  # noqa: BLE001 — persist last_error
        with db.connect() as conn:
            mark_status(
                conn,
                outbox_id,
                "error",
                last_error=str(exc)[:500],
                bump_attempts=True,
            )
        return "error"


def get_outbox_row(db: HubDatabase, outbox_id: int) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT id, event, payload_json, status, attempts, last_error,
                   idempotency_key, created_at, updated_at, acked_at
            FROM webhook_outbox WHERE id = ?
            """,
            (outbox_id,),
        ).fetchone()
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}
