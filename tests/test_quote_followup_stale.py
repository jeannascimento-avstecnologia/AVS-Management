from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, clear_settings_cache
from src.hub.models import HubDatabase
from src.hub.store import reset_hub_db_cache
from src.integrations.tiflux_client import TifluxClient
from src.quotes.followup_mock import mock_followup_ticket, seed_followup_mock_quotes
from src.quotes.service import QuoteService
from src.quotes.ticket_link import (
    FOLLOWUP_STALE_DAYS,
    fingerprint_after_sent,
    followup_state,
    resolve_ticket_activity_at,
    ticket_activity_fingerprint,
)

FIXED = datetime(2026, 9, 29, 15, 0, tzinfo=timezone.utc)


def _iso(when: datetime) -> str:
    return when.replace(microsecond=0).isoformat()


def test_fingerprint_ignores_updated_at() -> None:
    older = mock_followup_ticket("9001", now=FIXED)
    newer = mock_followup_ticket("9002", now=FIXED)
    assert older is not None and newer is not None
    assert ticket_activity_fingerprint(older) == ticket_activity_fingerprint(newer)


def test_fingerprint_after_sent_matches_overlay() -> None:
    ticket = {
        "services_catalog": {"item_name": "1 - Triagem"},
        "responsible": {"id": 3, "name": "Antes"},
        "stage": {"name": "Triagem"},
        "status": {"name": "Aberto"},
    }
    sent = fingerprint_after_sent(
        ticket,
        stage_name="Orçamento enviado",
        status_name="Aguardando cliente",
        status_id=4,
        responsible_id=9,
    )
    mirrored = {
        "services_catalog": {"item_name": "1 - Triagem"},
        "responsible_id": 9,
        "stage": {"name": "Orçamento enviado"},
        "status": {"name": "Aguardando cliente", "id": 4},
    }
    assert sent == ticket_activity_fingerprint(mirrored)


def test_resolve_same_fingerprint_does_not_advance() -> None:
    ticket = mock_followup_ticket("9001", now=FIXED)
    assert ticket is not None
    fingerprint = ticket_activity_fingerprint(ticket)
    stored = _iso(FIXED - timedelta(days=8))
    resolved = resolve_ticket_activity_at(
        stored_at=stored,
        stored_fingerprint=fingerprint,
        payload_at=stored,
        payload_fingerprint=fingerprint,
        now=_iso(FIXED),
    )
    assert resolved == stored


def test_resolve_newer_timestamp_advances_without_fingerprint_change() -> None:
    ticket = mock_followup_ticket("9001", now=FIXED)
    assert ticket is not None
    fingerprint = ticket_activity_fingerprint(ticket)
    stored = _iso(FIXED - timedelta(days=8))
    fresh = _iso(FIXED - timedelta(days=1))
    resolved = resolve_ticket_activity_at(
        stored_at=stored,
        stored_fingerprint=fingerprint,
        payload_at=fresh,
        payload_fingerprint=fingerprint,
        now=_iso(FIXED),
    )
    assert resolved == fresh


def test_resolve_movement_updates_even_if_payload_timestamp_is_older() -> None:
    stored = _iso(FIXED - timedelta(days=8))
    resolved = resolve_ticket_activity_at(
        stored_at=stored,
        stored_fingerprint="old",
        payload_at=_iso(FIXED - timedelta(days=10)),
        payload_fingerprint="new",
        now=_iso(FIXED),
    )
    assert resolved == _iso(FIXED)


def test_followup_state_boundaries() -> None:
    sent = _iso(FIXED - timedelta(days=FOLLOWUP_STALE_DAYS))
    stale, days = followup_state(
        status="sent",
        ticket_link_status="novo",
        ticket_number="9001",
        sent_at=sent,
        activity_at=sent,
        now=FIXED,
    )
    assert stale is True
    assert days == FOLLOWUP_STALE_DAYS

    recent = _iso(FIXED - timedelta(days=FOLLOWUP_STALE_DAYS) + timedelta(seconds=1))
    stale, days = followup_state(
        status="sent",
        ticket_link_status="novo",
        ticket_number="9001",
        sent_at=recent,
        activity_at=recent,
        now=FIXED,
    )
    assert stale is False
    assert days == FOLLOWUP_STALE_DAYS - 1

    stale, days = followup_state(
        status="sent",
        ticket_link_status="aprovado",
        ticket_number="9004",
        sent_at=_iso(FIXED - timedelta(days=10)),
        activity_at=_iso(FIXED - timedelta(days=10)),
        now=FIXED,
    )
    assert stale is False
    assert days is None

    stale, _days = followup_state(
        status="draft",
        ticket_link_status="novo",
        ticket_number="1",
        sent_at=None,
        activity_at=_iso(FIXED - timedelta(days=9)),
        now=FIXED,
    )
    assert stale is False


def test_apply_keeps_clock_when_fingerprint_matches(tmp_path: Path) -> None:
    db = HubDatabase(tmp_path / "hub.db")
    seed_followup_mock_quotes(db, now=FIXED)
    svc = QuoteService(db)
    quote = next(q for q in svc.list(limit=20) if q.tiflux_ticket_number == "9001")
    assert quote.followup_stale is True
    ticket = mock_followup_ticket("9001", now=FIXED)
    assert ticket is not None
    stored = quote.sent_at
    updated = svc.apply_ticket_link_updates(
        [
            {
                "quote_id": quote.id,
                "link_status": "novo",
                "catalog": "1 - Triagem",
                "snapshot": None,
                "activity_at": stored,
                "fingerprint": ticket_activity_fingerprint(ticket),
            }
        ]
    )
    assert updated[0].followup_stale is True
    with db.connect() as conn:
        row = conn.execute(
            "SELECT ticket_activity_at FROM quotes WHERE id = ?",
            (quote.id,),
        ).fetchone()
    assert row is not None
    assert row["ticket_activity_at"] == stored


def test_mock_get_ticket_skips_http() -> None:
    settings = Settings(
        tiflux_api_token="tf-tok",
        quote_followup_mock=True,
        session_secret="pytest-only-session-secret-key-32b!!",
    )
    client = TifluxClient(settings)

    async def _run() -> dict | None:
        with patch("src.integrations.tiflux_client.httpx.AsyncClient") as http:
            ticket = await client.get_ticket_by_number("9001")
            http.assert_not_called()
            return ticket

    ticket = asyncio.run(_run())
    assert ticket is not None
    assert ticket["ticket_number"] == "9001"
    assert ticket["is_closed"] is False


@pytest.fixture()
def followup_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(tmp_path / "pdfs"))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
    monkeypatch.setenv("QUOTE_FOLLOWUP_MOCK", "true")
    clear_settings_cache()
    reset_hub_db_cache()
    seed_followup_mock_quotes(HubDatabase(hub_path), now=datetime.now(timezone.utc))
    from src.main import app

    with TestClient(app) as client:
        yield client
    reset_hub_db_cache()
    clear_settings_cache()


def test_refresh_mock_highlights_only_stale_open_ticket(followup_client: TestClient) -> None:
    listed = followup_client.get("/orcamentos")
    assert listed.status_code == 200, listed.text
    before = {q["tiflux_ticket_number"]: q for q in listed.json()["quotes"]}
    ids = [before[number]["id"] for number in ("9001", "9002", "9003", "9004")]

    refreshed = followup_client.post("/orcamentos/refresh-ticket-links", json={"quote_ids": ids})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["failures"] == []
    updated_ids = {q["id"] for q in body["updated"]}
    assert before["9004"]["id"] not in updated_ids

    listed = followup_client.get("/orcamentos")
    after = {q["tiflux_ticket_number"]: q for q in listed.json()["quotes"]}
    assert after["9001"]["followup_stale"] is True
    assert after["9001"]["followup_idle_days"] >= 5
    assert after["9002"]["followup_stale"] is False
    assert after["9002"]["followup_idle_days"] is not None
    assert after["9002"]["followup_idle_days"] < 5
    assert after["9003"]["followup_stale"] is False
    assert after["9004"]["followup_stale"] is False
    assert after["9004"]["followup_idle_days"] is None
