"""Classificação pura do vínculo ticket TiFlux ↔ orçamento.

Contrato oficial (OpenAPI v2):
- GET /tickets/{ticket_number}
- fechado: is_closed
- catálogo: services_catalog.item_name (fallback name)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

TicketLinkStatus = Literal["novo", "aprovado", "rejeitado"]
APPROVED_CATALOG_LABEL = "3 - Aprovado"
TICKET_LINK_STATUSES: frozenset[str] = frozenset({"novo", "aprovado", "rejeitado"})
FOLLOWUP_STALE_DAYS = 5
_ACTIVITY_TS_KEYS = ("updated_at", "last_update", "created_at")


def extract_ticket_closed(ticket: dict[str, Any]) -> bool:
    """Fonte de verdade: `is_closed`. SLA `solved_in_time` não conta como fechamento."""
    flag = ticket.get("is_closed")
    if isinstance(flag, bool):
        return flag
    if flag in (1, "1", "true", "True"):
        return True
    return False


def extract_ticket_catalog(ticket: dict[str, Any]) -> str | None:
    """Nome do item de catálogo para comparar com APPROVED_CATALOG_LABEL."""
    cat = (
        ticket.get("services_catalog")
        or ticket.get("services_catalogs_item")
        or ticket.get("catalog_item")
    )
    if isinstance(cat, dict):
        raw = cat.get("item_name") or cat.get("name")
        text = str(raw).strip() if raw is not None else ""
        return text or None
    if cat is None:
        return None
    text = str(cat).strip()
    return text or None


def is_approved_catalog_label(catalog: str | None) -> bool:
    """Fecha como aprovado: `3 - Aprovado` ou item_name `Aprovado` (não Reprovado)."""
    name = (catalog or "").casefold().strip()
    if not name:
        return False
    if name == APPROVED_CATALOG_LABEL.casefold() or name == "aprovado":
        return True
    if "reprovado" in name:
        return False
    return name.endswith("aprovado")


def classify_ticket_link(ticket: dict[str, Any]) -> TicketLinkStatus:
    if not extract_ticket_closed(ticket):
        return "novo"
    catalog = extract_ticket_catalog(ticket)
    return "aprovado" if is_approved_catalog_label(catalog) else "rejeitado"


def extract_ticket_number(ticket: dict[str, Any]) -> str | None:
    raw = ticket.get("ticket_number")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def extract_ticket_subject(ticket: dict[str, Any]) -> str | None:
    raw = ticket.get("title") or ticket.get("subject")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def extract_ticket_client_name(ticket: dict[str, Any]) -> str | None:
    client = ticket.get("client")
    if isinstance(client, dict):
        raw = client.get("name") or client.get("social")
        text = str(raw).strip() if raw is not None else ""
        return text or None
    return None


def extract_ticket_status_name(ticket: dict[str, Any]) -> str | None:
    status = ticket.get("status")
    if isinstance(status, dict):
        raw = status.get("name")
        text = str(raw).strip() if raw is not None else ""
        return text or None
    if status is None:
        return None
    text = str(status).strip()
    return text or None


def build_ticket_preview(ticket: dict[str, Any]) -> dict[str, Any]:
    catalog = extract_ticket_catalog(ticket)
    closed = extract_ticket_closed(ticket)
    link_status = classify_ticket_link(ticket)
    return {
        "ticket_number": extract_ticket_number(ticket) or "",
        "subject": extract_ticket_subject(ticket),
        "client_name": extract_ticket_client_name(ticket),
        "status": extract_ticket_status_name(ticket),
        "catalog": catalog,
        "closed": closed,
        "suggested_link_status": link_status,
    }


def unwrap_ticket_payload(data: object) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    nested = data.get("ticket")
    if isinstance(nested, dict):
        return nested
    return data


def option_id(row: dict[str, Any]) -> int | None:
    raw = row.get("id")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 1 else None


def option_name(row: dict[str, Any]) -> str:
    raw = row.get("item_name") or row.get("name") or row.get("display_name")
    return str(raw).strip() if raw is not None else ""


def pick_default_catalog_item_id(items: list[dict[str, Any]]) -> int | None:
    ranked: list[tuple[int, int]] = []
    for item in items:
        oid = option_id(item)
        if oid is None:
            continue
        name = option_name(item)
        folded = name.casefold()
        if is_approved_catalog_label(name) or folded.startswith("3 -"):
            score = 2
        elif "triagem" in folded or folded.startswith("1 -") or folded.startswith("1 "):
            score = 0
        else:
            score = 1
        ranked.append((score, oid))
    ranked.sort()
    return ranked[0][1] if ranked else None


def pick_default_priority_id(items: list[dict[str, Any]]) -> int | None:
    ranked: list[tuple[int, int, int]] = []
    for item in items:
        oid = option_id(item)
        if oid is None:
            continue
        name = option_name(item).casefold()
        try:
            order = int(item["order"]) if item.get("order") is not None else 999
        except (TypeError, ValueError):
            order = 999
        score = 0 if ("baixa" in name or name in {"low", "baixa"}) else 1
        ranked.append((score, order, oid))
    ranked.sort()
    return ranked[0][2] if ranked else None


def default_ticket_title(*, quote_id: int, title: str | None, client_name: str | None) -> str:
    text = (title or "").strip()
    if text:
        return text[:200]
    client = (client_name or "").strip() or "cliente"
    return f"Orçamento M{quote_id} — {client}"[:200]


def default_ticket_description(
    *,
    quote_id: int,
    client_name: str | None,
    cnpj: str | None,
    item_count: int,
    total: float,
) -> str:
    client = (client_name or "").strip() or "—"
    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    lines = [
        f"Orçamento M{quote_id}",
        f"Cliente: {client}",
        f"CNPJ: {digits or '—'}",
        f"Itens: {item_count}",
        f"Total: {total:.2f}",
        "",
        "Aberto pelo AVS Management (wizard Revisão).",
    ]
    return "\n".join(lines)[:8000]


def build_create_ticket_payload(
    *,
    title: str,
    description: str,
    client_id: int,
    desk_id: int,
    services_catalogs_item_id: int | None,
    priority_id: int | None,
    requestor_id: int | None,
    requestor_name: str | None,
    requestor_email: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title.strip(),
        "description": description.strip(),
        "client_id": int(client_id),
        "desk_id": int(desk_id),
    }
    if services_catalogs_item_id:
        payload["services_catalogs_item_id"] = int(services_catalogs_item_id)
    if priority_id:
        payload["priority_id"] = int(priority_id)
    if requestor_id:
        payload["requestor_id"] = int(requestor_id)
    else:
        name = (requestor_name or "").strip()
        email = (requestor_email or "").strip()
        if email:
            payload["requestor_email"] = email
        if name:
            payload["requestor_name"] = name
    return payload


def _parse_utc(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _nested_id(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    raw = value.get("id")
    if raw is None:
        return ""
    text = str(raw).strip()
    if text in {"", "0"}:
        return ""
    return text


def _nested_name(value: object) -> str:
    if isinstance(value, dict):
        raw = value.get("name") or value.get("stage_name") or value.get("item_name")
        return str(raw).strip() if raw is not None else ""
    if value is None:
        return ""
    return str(value).strip()


def extract_ticket_activity_at(ticket: dict[str, Any]) -> str | None:
    """Primeiro timestamp preenchido: updated_at, last_update, created_at."""
    for key in _ACTIVITY_TS_KEYS:
        parsed = _parse_utc(ticket.get(key))
        if parsed is not None:
            return _iso_utc(parsed)
    return None


def extract_ticket_responsible_token(ticket: dict[str, Any]) -> str:
    for key in ("responsible_id", "user_id"):
        raw = ticket.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text and text not in {"0", "None"}:
            return text
    for key in ("responsible", "responsible_user", "user", "attendant"):
        token = _nested_id(ticket.get(key))
        if token:
            return token
        name = _nested_name(ticket.get(key))
        if name:
            return name.casefold()
    return ""


def extract_ticket_stage_token(ticket: dict[str, Any]) -> str:
    stage = ticket.get("stage")
    name = _nested_name(stage) or str(ticket.get("stage_name") or "").strip()
    if name:
        return name.casefold()
    return _nested_id(stage)


def ticket_activity_fingerprint(ticket: dict[str, Any]) -> str:
    """Catálogo, responsável, estágio e status. Separador não aparece nos valores."""
    catalog = (extract_ticket_catalog(ticket) or "").casefold()
    responsible = extract_ticket_responsible_token(ticket)
    stage = extract_ticket_stage_token(ticket)
    status = (extract_ticket_status_name(ticket) or "").casefold()
    return "\x1f".join((catalog, responsible, stage, status))


def fingerprint_after_sent(
    ticket: dict[str, Any],
    *,
    stage_name: str,
    status_name: str,
    status_id: int | None,
    responsible_id: int | None,
) -> str:
    """Fingerprint como o GET deve voltar depois do PUT de quote.sent."""
    overlay = dict(ticket)
    overlay["stage"] = {"name": stage_name}
    overlay["stage_name"] = stage_name
    status = ticket.get("status")
    status_obj = dict(status) if isinstance(status, dict) else {}
    status_obj["name"] = status_name
    if status_id is not None:
        status_obj["id"] = status_id
    overlay["status"] = status_obj
    if responsible_id is not None:
        overlay["responsible_id"] = responsible_id
        overlay["responsible"] = {"id": responsible_id}
    return ticket_activity_fingerprint(overlay)


def resolve_ticket_activity_at(
    *,
    stored_at: str | None,
    stored_fingerprint: str | None,
    payload_at: str | None,
    payload_fingerprint: str,
    now: str,
) -> str:
    """Envio abre o relógio. Movimentação (fingerprint) atualiza para agora."""
    stored = _parse_utc(stored_at)
    payload = _parse_utc(payload_at)
    now_dt = _parse_utc(now) or datetime.now(timezone.utc)
    fingerprint_changed = bool(stored_fingerprint) and stored_fingerprint != payload_fingerprint
    if stored is None and not stored_fingerprint:
        chosen = payload or now_dt
    elif fingerprint_changed:
        chosen = now_dt
    elif payload is not None and (stored is None or payload > stored):
        chosen = payload
    else:
        chosen = stored or now_dt
    return _iso_utc(chosen)


def followup_state(
    *,
    status: str,
    ticket_link_status: str | None,
    ticket_number: str | None,
    sent_at: str | None,
    activity_at: str | None,
    now: datetime,
) -> tuple[bool, int | None]:
    number = (ticket_number or "").strip()
    if status != "sent" or ticket_link_status != "novo" or not number:
        return False, None
    anchor = _parse_utc(activity_at) or _parse_utc(sent_at)
    if anchor is None:
        return False, None
    current = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    seconds = (current.astimezone(timezone.utc) - anchor).total_seconds()
    if seconds < 0:
        seconds = 0
    days = int(seconds // 86400)
    return days >= FOLLOWUP_STALE_DAYS, days
