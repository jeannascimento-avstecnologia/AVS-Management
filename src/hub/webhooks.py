"""Callback n8n — HMAC obrigatório, sem sessão (ADR-0003)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from src.auth.audit import log_action
from src.config import get_settings
from src.hub.callback_schemas import CallbackPayload
from src.hub.hmac import SIGNATURE_HEADER, verify_signature
from src.hub.models import HubDatabase
from src.hub.outbox import mark_status
from src.hub.store import get_hub_db

_MAX_BODY_BYTES = 1_048_576
_SYSTEM_USER = {"email": "system:n8n-callback", "id": None}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _apply_quote_external(db: HubDatabase, payload: CallbackPayload) -> None:
    if payload.resource_type != "quote":
        return
    external = payload.external
    if external is None:
        return
    now = _utcnow_iso()
    sets: list[str] = ["updated_at = ?"]
    values: list[Any] = [now]
    if external.tiflux_ticket_number:
        sets.append("tiflux_ticket_number = ?")
        values.append(external.tiflux_ticket_number)
    if external.vhsys_os_id:
        sets.append("vhsys_os_id = ?")
        values.append(external.vhsys_os_id)
    if len(sets) == 1:
        return
    values.append(payload.resource_id)
    with db.connect() as conn:
        conn.execute(
            f"UPDATE quotes SET {', '.join(sets)} WHERE id = ?",
            values,
        )


def _apply_billing_external(db: HubDatabase, payload: CallbackPayload) -> None:
    if payload.resource_type != "billing_run":
        return
    external = payload.external
    now = _utcnow_iso()
    sets: list[str] = ["updated_at = ?"]
    values: list[Any] = [now]
    if payload.status == "ok":
        sets.append("status = ?")
        values.append("sent")
        sets.append("sent_at = COALESCE(sent_at, ?)")
        values.append(now)
        if external is not None:
            if external.tiflux_ticket_number:
                sets.append("tiflux_ticket_number = ?")
                values.append(external.tiflux_ticket_number)
            if external.vhsys_nf_id:
                sets.append("vhsys_nf_id = ?")
                values.append(external.vhsys_nf_id)
            if external.vhsys_cr_id:
                sets.append("vhsys_cr_id = ?")
                values.append(external.vhsys_cr_id)
    else:
        sets.append("status = ?")
        values.append("error")
        if payload.error_message:
            sets.append("error_message = ?")
            values.append(payload.error_message[:500])
    values.append(payload.resource_id)
    with db.connect() as conn:
        conn.execute(
            f"UPDATE billing_runs SET {', '.join(sets)} WHERE id = ?",
            values,
        )


def build_webhooks_router() -> APIRouter:
    router = APIRouter(prefix="/webhooks/n8n", tags=["webhooks"])

    @router.post("/callback")
    async def n8n_callback(request: Request) -> dict[str, Any]:
        raw = await request.body()
        if len(raw) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Body excede 1 MiB.")

        settings = get_settings()
        secret = settings.n8n_webhook_secret
        signature = request.headers.get(SIGNATURE_HEADER) or request.headers.get(
            SIGNATURE_HEADER.lower()
        )
        if not verify_signature(secret, raw, signature):
            raise HTTPException(status_code=401, detail="Assinatura HMAC inválida.")

        try:
            payload = CallbackPayload.model_validate_json(raw)
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=exc.errors()) from exc

        db = get_hub_db()
        with db.connect() as conn:
            row = conn.execute(
                "SELECT id, status, event FROM webhook_outbox WHERE id = ?",
                (payload.outbox_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Outbox não encontrado.")

            if payload.status == "ok":
                mark_status(conn, payload.outbox_id, "acked", acked=True)
            else:
                mark_status(
                    conn,
                    payload.outbox_id,
                    "error",
                    last_error=(payload.error_message or "callback error")[:500],
                )

        if payload.resource_type == "quote" and payload.status == "ok":
            _apply_quote_external(db, payload)
        elif payload.resource_type == "billing_run":
            _apply_billing_external(db, payload)

        log_action(
            request,
            action="webhook.callback",
            resource=f"outbox:{payload.outbox_id}",
            detail={
                "event": payload.event,
                "status": payload.status,
                "resource_type": payload.resource_type,
                "resource_id": payload.resource_id,
                "dry_run": payload.dry_run,
            },
            user=_SYSTEM_USER,
        )
        return {"ok": True, "outbox_id": payload.outbox_id, "status": payload.status}

    return router
