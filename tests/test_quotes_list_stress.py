"""Stress local: QuotesService.list com N quotes em hub.db temp (sem rede)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.hub.models import HubDatabase
from src.quotes import service as quote_service_mod
from src.quotes.schemas import QuoteItemWrite, QuoteWrite
from src.quotes.service import QuoteService

CNPJ = "11222333000181"


def _seed_quotes(svc: QuoteService, *, n: int, items_per: int) -> None:
    temps = ["quente", "morno", "frio", None]
    statuses_cycle = ["draft", "submitted", "sent", "approved"]
    items = [
        QuoteItemWrite(
            section="implantacao" if i % 2 == 0 else "mensalidade",
            name=f"Item {i}",
            qty=1.0,
            unit_value=100.0 + i,
            sort_order=i,
        )
        for i in range(items_per)
    ]
    for i in range(n):
        q = svc.create(
            QuoteWrite(
                cnpj=CNPJ,
                client_name=f"Cliente stress {i}",
                lead_temperature=temps[i % len(temps)],
                items=items,
            ),
            created_by=1,
        )
        # Ajusta status via SQL direto (evita transitions) — só leitura no stress.
        status = statuses_cycle[i % len(statuses_cycle)]
        if status != "draft":
            with svc._db.connect() as conn:
                conn.execute(
                    "UPDATE quotes SET status = ?, updated_at = updated_at WHERE id = ?",
                    (status, q.id),
                )


@pytest.fixture()
def stress_svc(tmp_path: Path) -> QuoteService:
    db = HubDatabase(tmp_path / "hub_stress.db")
    return QuoteService(db)


def test_list_n_plus_one_items_queries(stress_svc: QuoteService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cada quote dispara 1 SELECT em quote_items (N+1)."""
    n = 40
    _seed_quotes(stress_svc, n=n, items_per=5)

    calls = {"n": 0}
    original = quote_service_mod._fetch_items

    def counted(conn, quote_id: int):
        calls["n"] += 1
        return original(conn, quote_id)

    monkeypatch.setattr(quote_service_mod, "_fetch_items", counted)

    listed = stress_svc.list(limit=100, offset=0)
    assert len(listed) == n
    assert calls["n"] == n, f"esperado N+1 com {n} fetches de items, got {calls['n']}"


def test_list_timing_100_and_200_with_items(stress_svc: QuoteService) -> None:
    """Mede list(100) e list(200) com 8 items/quote — números no dossiê."""
    _seed_quotes(stress_svc, n=200, items_per=8)

    t0 = time.perf_counter()
    a = stress_svc.list(limit=100, offset=0)
    ms_100 = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    b = stress_svc.list(limit=200, offset=0)
    ms_200 = (time.perf_counter() - t1) * 1000

    assert len(a) == 100
    assert len(b) == 200
    assert all(len(q.items) == 8 for q in a[:5])

    # Soft ceilings: máquina CI/local; falha só se regressão absurda.
    assert ms_100 < 2000, f"list(100) lento demais: {ms_100:.1f}ms"
    assert ms_200 < 4000, f"list(200) lento demais: {ms_200:.1f}ms"

    # Exporta para stdout (pytest -s captura no dossiê).
    print(f"\n[STRESS] list(100)={ms_100:.2f}ms list(200)={ms_200:.2f}ms items=8")
    # Heurística: ~2x quotes → ~2x tempo (N+1 linear).
    ratio = ms_200 / ms_100 if ms_100 > 0 else 0
    print(f"[STRESS] ratio_200_vs_100={ratio:.2f} (esperado ~2.0 se N+1 domina)")


def test_pipeline_cap_silently_truncates(stress_svc: QuoteService) -> None:
    """UI pipeline-summary usa limit=100 — sob >100 abertos, contagens ficam incompletas."""
    _seed_quotes(stress_svc, n=120, items_per=2)
    capped = stress_svc.list(limit=100, offset=0)
    all_openish = stress_svc.list(limit=500, offset=0)
    assert len(capped) == 100
    assert len(all_openish) == 120
