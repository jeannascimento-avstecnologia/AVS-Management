"""Saudação quote.sent (America/Sao_Paulo)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from src.quotes.sent_message import greeting_text

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def test_greeting_morning_and_afternoon() -> None:
    morning = datetime(2026, 9, 25, 9, 30, tzinfo=SAO_PAULO)
    afternoon = datetime(2026, 9, 25, 15, 0, tzinfo=SAO_PAULO)
    assert greeting_text("Ana", now=morning) == "Bom dia, Ana.\nSegue orçamento solicitado."
    assert greeting_text("Ana", now=afternoon) == "Boa tarde, Ana.\nSegue orçamento solicitado."
    assert greeting_text("  ", now=morning).startswith("Bom dia, cliente.")
