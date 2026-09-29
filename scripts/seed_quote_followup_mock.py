"""Grava orçamentos 9001–9004 no hub.db local.

Uso:
    QUOTE_FOLLOWUP_MOCK=1 python scripts/seed_quote_followup_mock.py

Reinicie a API depois de ligar o flag. Abra /orcamentos.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config import get_settings
from src.hub.models import HubDatabase
from src.quotes.followup_mock import seed_followup_mock_quotes


def main() -> None:
    settings = get_settings()
    db = HubDatabase(settings.hub_db_path)
    ids = seed_followup_mock_quotes(db)
    print(f"hub.db: {settings.hub_db_path}")
    print(f"orçamentos: {ids}")
    print("9001 destaca · 9002 não (resposta ontem) · 9003 não · 9004 não (aprovado)")
    if settings.quote_followup_mock:
        print("QUOTE_FOLLOWUP_MOCK está ligado. Abra /orcamentos.")
    else:
        print("QUOTE_FOLLOWUP_MOCK está desligado. Ligue (=1) e reinicie a API antes de abrir /orcamentos.")


if __name__ == "__main__":
    main()
