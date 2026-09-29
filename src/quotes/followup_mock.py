"""Tickets 9001–9004 para o destaque de orçamento sem retorno. Só com QUOTE_FOLLOWUP_MOCK."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from src.hub.models import HubDatabase
from src.quotes.schemas import QuoteWrite
from src.quotes.service import QuoteService
from src.quotes.ticket_link import (
    APPROVED_CATALOG_LABEL,
    extract_ticket_activity_at,
    extract_ticket_catalog,
    ticket_activity_fingerprint,
)

MOCK_TICKET_NUMBERS = frozenset({"9001", "9002", "9003", "9004"})
MOCK_CNPJ = "11222333000181"
_OPEN_CATALOG = "1 - Triagem"


def mock_followup_ticket(number: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Payload estável. None se o número não é mock."""
    ticket_number = str(number).strip()
    if ticket_number not in MOCK_TICKET_NUMBERS:
        return None
    clock = now or datetime.now(timezone.utc)
    idle_days = {"9001": 8, "9002": 1, "9003": 2, "9004": 10}[ticket_number]
    closed = ticket_number == "9004"
    catalog = APPROVED_CATALOG_LABEL if closed else _OPEN_CATALOG
    return {
        "ticket_number": ticket_number,
        "title": f"MOCK follow-up {ticket_number}",
        "is_closed": closed,
        "client": {"name": f"Cliente mock {ticket_number}"},
        "services_catalog": {"item_name": catalog},
        "responsible": {"id": 9, "name": "André"},
        "stage": {"name": "Orçamento enviado"},
        "status": {"name": "Aprovado" if closed else "Aguardando cliente"},
        "updated_at": (clock - timedelta(days=idle_days)).replace(microsecond=0).isoformat(),
    }


def seed_followup_mock_quotes(db: HubDatabase, *, now: datetime | None = None) -> list[int]:
    """Substitui os quatro orçamentos mock. 9002 nasce parado; o refresh é que enxerga a resposta."""
    clock = now or datetime.now(timezone.utc)
    _delete_previous(db)
    svc = QuoteService(db)
    ids: list[int] = []
    specs = (
        ("9001", 8, "novo"),
        ("9002", 8, "novo"),
        ("9003", 2, "novo"),
        ("9004", 10, "aprovado"),
    )
    for number, sent_days, link_status in specs:
        created = svc.create(
            QuoteWrite.model_validate(
                {
                    "cnpj": MOCK_CNPJ,
                    "client_name": f"Cliente mock {number}",
                    "title": f"MOCK follow-up {number}",
                    "items": [
                        {
                            "section": "implantacao",
                            "name": "Item mock",
                            "qty": 1,
                            "unit_value": 100.0,
                            "sort_order": 0,
                        }
                    ],
                }
            ),
            created_by=1,
        )
        ticket = mock_followup_ticket(number, now=clock)
        assert ticket is not None
        sent_at = (clock - timedelta(days=sent_days)).replace(microsecond=0).isoformat()
        activity_at = sent_at if number == "9002" else extract_ticket_activity_at(ticket)
        with db.connect() as conn:
            conn.execute(
                """
                UPDATE quotes
                SET status = 'sent',
                    submitted_at = ?,
                    sent_at = ?,
                    tiflux_ticket_number = ?,
                    ticket_link_status = ?,
                    ticket_link_catalog = ?,
                    ticket_link_checked_at = ?,
                    ticket_activity_at = ?,
                    ticket_activity_fingerprint = ?
                WHERE id = ?
                """,
                (
                    sent_at,
                    sent_at,
                    number,
                    link_status,
                    extract_ticket_catalog(ticket),
                    sent_at,
                    activity_at,
                    ticket_activity_fingerprint(ticket),
                    created.id,
                ),
            )
        ids.append(created.id)
    return ids


def _delete_previous(db: HubDatabase) -> None:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM quotes
            WHERE title LIKE 'MOCK follow-up %'
              AND tiflux_ticket_number IN ('9001', '9002', '9003', '9004')
            """
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM quotes WHERE id = ?", (int(row["id"]),))
