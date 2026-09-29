"""Texto do quote.sent. A aplicação no TiFlux fica em sent_tiflux.py."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.config import Settings
from src.quotes.schemas import QuoteMarkSentBody, QuoteRead

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
STATUS_TARGET = "Aguardando o cliente"
STAGE_TARGET = "Orçamento enviado"
RESPONSIBLE_NAME = "André"
STANDARD_LINE = "Segue orçamento solicitado."


def greeting_text(recipient_name: str, *, now: datetime | None = None) -> str:
    """Bom dia antes das 12:00 em America/Sao_Paulo; depois, Boa tarde."""
    moment = datetime.now(SAO_PAULO) if now is None else now
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=SAO_PAULO)
    else:
        moment = moment.astimezone(SAO_PAULO)
    salute = "Bom dia" if moment.hour < 12 else "Boa tarde"
    name = " ".join((recipient_name or "").split()) or "cliente"
    return f"{salute}, {name}.\n{STANDARD_LINE}"


def message_text_for(quote: QuoteRead, body: QuoteMarkSentBody) -> str:
    recipient = (quote.contact_name or quote.client_name or "").strip()
    greeting = greeting_text(recipient)
    free = body.free_message
    return f"{greeting}\n\n{free}" if free else greeting


def build_quote_sent_payload(
    quote: QuoteRead,
    body: QuoteMarkSentBody,
    settings: Settings,
) -> dict[str, Any]:
    message = message_text_for(quote, body)
    free = body.free_message
    greeting = message[: -len(free) - 2] if free else message
    responsible_id = settings.tiflux_quote_sent_responsible_id
    pdf_path = quote.pdf_path
    filename = Path(pdf_path).name if pdf_path else None
    return {
        "quote": quote.model_dump(),
        "pdf_path": pdf_path,
        "tiflux_ticket_number": quote.tiflux_ticket_number,
        "status_target": STATUS_TARGET,
        "stage_target": STAGE_TARGET,
        "responsible": {
            "name": RESPONSIBLE_NAME,
            "id": responsible_id if responsible_id > 0 else None,
        },
        "greeting_text": greeting,
        "free_message": free,
        "message_text": message,
        "followers": [item.model_dump() for item in body.followers],
        "attachment": {
            "kind": "pdf",
            "pdf_path": pdf_path,
            "filename": filename,
        },
    }
