"""Aplica quote.sent no TiFlux. Sem outbox e sem POST ao n8n."""

from __future__ import annotations

import base64
import html
import logging
import re
from pathlib import Path
from typing import Any

from src.config import Settings
from src.integrations.tiflux_client import TifluxClient
from src.quotes.schemas import QuoteMarkSentBody, QuoteRead
from src.quotes.sent_message import (
    RESPONSIBLE_NAME,
    STAGE_TARGET,
    STATUS_TARGET,
    message_text_for,
)

logger = logging.getLogger(__name__)

_UUID_PDF_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.pdf$",
    re.IGNORECASE,
)
_MAX_PDF_BYTES = 25 * 1024 * 1024
_STAGE_KEYS = ("stages", "stage")
_STATUS_KEYS = ("statuses", "status", "ticket_statuses")
_FOLLOWERS_PENDING = "Seguidores pendentes: TifluxClient sem método de seguidores."

_name_id_cache: dict[tuple[str, int, str], int] = {}


def clear_quote_sent_caches() -> None:
    _name_id_cache.clear()


def message_to_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>\n")


def find_id_by_name(payloads: list[object], keys: tuple[str, ...], target: str) -> int | None:
    wanted = target.casefold()
    for record in _named_records(payloads, keys):
        raw_name = record.get("name") or record.get("stage_name") or record.get("status_name")
        if str(raw_name or "").strip().casefold() != wanted:
            continue
        found = _positive_int(record.get("id"))
        if found is not None:
            return found
    return None


def read_quote_pdf_base64(
    pdf_name: str | None,
    settings: Settings,
) -> tuple[dict[str, str] | None, str | None]:
    if not pdf_name:
        return None, "PDF ausente; mensagem segue sem anexo."
    name = Path(pdf_name).name
    if name != pdf_name or not _UUID_PDF_RE.match(name):
        return None, "PDF inválido; mensagem segue sem anexo."
    root = Path(settings.hub_pdf_dir).expanduser().resolve()
    target = (root / name).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None, "PDF não encontrado em disco; mensagem segue sem anexo."
    data = target.read_bytes()
    if len(data) > _MAX_PDF_BYTES:
        return None, "PDF acima de 25 MB; mensagem segue sem anexo."
    return {
        "filename": name,
        "base64": base64.b64encode(data).decode("ascii"),
    }, None


def simulate_quote_sent_tiflux(
    quote: QuoteRead,
    body: QuoteMarkSentBody | None,
    settings: Settings,
) -> dict[str, Any]:
    """Dry-run: não chama o TiFlux. Valida ticket e PDF locais."""
    sent = body or QuoteMarkSentBody()
    result = _blank(dry_run=True)
    number = str(quote.tiflux_ticket_number or "").strip()
    if not number:
        result["errors"].append("Chamado TiFlux não vinculado ao orçamento.")
        _mark_followers(result, sent)
        return result
    result["stage_ok"] = True
    result["status_ok"] = True
    result["responsible_ok"] = True
    result["answer_ok"] = True
    _file, warning = read_quote_pdf_base64(quote.pdf_path, settings)
    if warning:
        logger.warning("quote.sent dry-run: %s", warning)
        result["errors"].append(warning)
    else:
        result["attachment_ok"] = True
    _mark_followers(result, sent)
    return result


async def apply_quote_sent_to_tiflux(
    quote: QuoteRead,
    body: QuoteMarkSentBody | None,
    settings: Settings,
    *,
    client: TifluxClient,
) -> dict[str, Any]:
    sent = body or QuoteMarkSentBody()
    result = _blank(dry_run=False)
    number = str(quote.tiflux_ticket_number or "").strip()
    if not number:
        result["errors"].append("Chamado TiFlux não vinculado ao orçamento.")
        _mark_followers(result, sent)
        return result

    try:
        ticket = await client.get_ticket_by_number(number)
    except Exception as exc:
        logger.warning("quote.sent: falha ao consultar chamado %s: %s", number, exc)
        result["errors"].append(f"Falha ao consultar chamado: {_short(exc)}")
        _mark_followers(result, sent)
        return result
    if not ticket:
        result["errors"].append(f"Chamado {number} não encontrado no TiFlux.")
        _mark_followers(result, sent)
        return result

    desk_id = _desk_id(ticket) or _positive_int(settings.tiflux_desk_comercial_id)
    stage_id = _cached("stage", desk_id, STAGE_TARGET) or find_id_by_name(
        [ticket], _STAGE_KEYS, STAGE_TARGET
    )
    status_id = _cached("status", desk_id, STATUS_TARGET) or find_id_by_name(
        [ticket], _STATUS_KEYS, STATUS_TARGET
    )
    if desk_id and (stage_id is None or status_id is None):
        desk = await _load_desk(client, desk_id, result)
        if desk is not None:
            if stage_id is None:
                stage_id = find_id_by_name([desk], _STAGE_KEYS, STAGE_TARGET)
            if status_id is None:
                status_id = find_id_by_name([desk], _STATUS_KEYS, STATUS_TARGET)
    if desk_id and stage_id:
        _remember("stage", desk_id, STAGE_TARGET, stage_id)
    if desk_id and status_id:
        _remember("status", desk_id, STATUS_TARGET, status_id)

    responsible_id = await _resolve_responsible(client, settings, result)
    await _update_ticket(
        client,
        ticket,
        stage_id=stage_id,
        status_id=status_id,
        responsible_id=responsible_id,
        result=result,
    )
    await _post_answer(client, quote, sent, number, settings, result)
    _mark_followers(result, sent)
    return result


def _blank(*, dry_run: bool) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "stage_ok": False,
        "status_ok": False,
        "responsible_ok": False,
        "answer_ok": False,
        "attachment_ok": False,
        "followers_ok": False,
        "errors": [],
    }


def _mark_followers(result: dict[str, Any], body: QuoteMarkSentBody) -> None:
    if not body.followers:
        result["followers_ok"] = True
        return
    logger.warning("quote.sent: %s", _FOLLOWERS_PENDING)
    result["errors"].append(_FOLLOWERS_PENDING)


async def _load_desk(
    client: TifluxClient,
    desk_id: int,
    result: dict[str, Any],
) -> dict | None:
    try:
        return await client.get_desk(desk_id)
    except Exception as exc:
        logger.warning("quote.sent: falha ao consultar mesa %s: %s", desk_id, exc)
        result["errors"].append(f"Falha ao consultar mesa: {_short(exc)}")
        return None


async def _resolve_responsible(
    client: TifluxClient,
    settings: Settings,
    result: dict[str, Any],
) -> int | None:
    configured = _positive_int(settings.tiflux_quote_sent_responsible_id)
    if configured is not None:
        return configured
    try:
        found = await client.find_user_id_by_name(RESPONSIBLE_NAME)
    except Exception as exc:
        logger.warning("quote.sent: falha ao buscar responsável: %s", exc)
        result["errors"].append(f"Responsável {RESPONSIBLE_NAME} não resolvido: {_short(exc)}")
        return None
    if found is None:
        logger.warning("quote.sent: usuário %s não encontrado", RESPONSIBLE_NAME)
        result["errors"].append(
            f"Responsável {RESPONSIBLE_NAME} não encontrado; chamado segue sem responsável."
        )
    return found


async def _update_ticket(
    client: TifluxClient,
    ticket: dict,
    *,
    stage_id: int | None,
    status_id: int | None,
    responsible_id: int | None,
    result: dict[str, Any],
) -> None:
    ticket_id = _positive_int(ticket.get("id"))
    if ticket_id is None:
        result["errors"].append("Ticket sem id interno; estágio e status não atualizados.")
        return
    if status_id is None:
        result["errors"].append(f"Status '{STATUS_TARGET}' não encontrado na mesa.")
    extra: dict[str, int] = {}
    if status_id is not None:
        extra["status_id"] = status_id
    if responsible_id is not None:
        extra["responsible_id"] = responsible_id
    try:
        await client.update_ticket(
            ticket_id,
            stage_id=stage_id,
            stage_name=STAGE_TARGET,
            extra=extra or None,
        )
    except Exception as exc:
        logger.warning("quote.sent: falha ao atualizar ticket %s: %s", ticket_id, exc)
        result["errors"].append(f"Falha ao atualizar chamado: {_short(exc)}")
        return
    result["stage_ok"] = True
    result["status_ok"] = status_id is not None
    result["responsible_ok"] = responsible_id is not None


async def _post_answer(
    client: TifluxClient,
    quote: QuoteRead,
    body: QuoteMarkSentBody,
    number: str,
    settings: Settings,
    result: dict[str, Any],
) -> None:
    file_entry, warning = read_quote_pdf_base64(quote.pdf_path, settings)
    if warning:
        logger.warning("quote.sent: %s", warning)
        result["errors"].append(warning)
    files = [file_entry] if file_entry else None
    answer = message_to_html(message_text_for(quote, body))
    try:
        await client.create_ticket_answer(number, answer=answer, files_base64=files)
    except Exception as exc:
        logger.warning("quote.sent: falha ao publicar mensagem no chamado %s: %s", number, exc)
        result["errors"].append(f"Falha ao publicar mensagem: {_short(exc)}")
        return
    result["answer_ok"] = True
    result["attachment_ok"] = file_entry is not None


def _cached(kind: str, desk_id: int | None, name: str) -> int | None:
    if desk_id is None:
        return None
    return _name_id_cache.get((kind, desk_id, name.casefold()))


def _remember(kind: str, desk_id: int, name: str, value: int) -> None:
    _name_id_cache[(kind, desk_id, name.casefold())] = value


def _desk_id(ticket: dict) -> int | None:
    desk = ticket.get("desk")
    if isinstance(desk, dict):
        found = _positive_int(desk.get("id"))
        if found is not None:
            return found
    return _positive_int(ticket.get("desk_id"))


def _named_records(payloads: list[object], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for payload in payloads:
        _walk(payload, keys, found, depth=0)
    return found


def _walk(node: object, keys: tuple[str, ...], found: list[dict[str, Any]], *, depth: int) -> None:
    if depth > 5:
        return
    if isinstance(node, dict):
        for key in keys:
            value = node.get(key)
            if isinstance(value, dict):
                found.append(value)
            elif isinstance(value, list):
                found.extend(item for item in value if isinstance(item, dict))
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk(value, keys, found, depth=depth + 1)
        return
    if isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                _walk(item, keys, found, depth=depth + 1)


def _positive_int(raw: object) -> int | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _short(exc: BaseException) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:300]
