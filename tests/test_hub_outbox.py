"""O2.2 — submit dry-run outbox + HMAC callback (ADR-0003)."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.hub.hmac import SIGNATURE_HEADER, sign_body, verify_signature
from src.hub.store import get_hub_db, reset_hub_db_cache

CNPJ = "11222333000181"

QUOTE_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "AVS Teste LTDA",
    "billed_by_type": "distribuidor",
    "billed_by_name": "Parceiro X",
    "items": [
        {
            "section": "implantacao",
            "name": "Setup inicial",
            "qty": 1,
            "unit_value": 1500.0,
            "sort_order": 0,
        }
    ],
}

SECRET = "test-n8n-hmac-secret-o22"


@pytest.fixture()
def outbox_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("HUB_DRY_RUN_NOTIFY_N8N", "false")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("N8N_COMMERCIAL_WEBHOOK_URL", "")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    clear_settings_cache()
    reset_hub_db_cache()
    yield hub_path
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def outbox_client(outbox_env: Path):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_hmac_sign_verify_roundtrip() -> None:
    body = b'{"event":"quote.submit","resource_id":1}'
    sig = sign_body(SECRET, body)
    assert verify_signature(SECRET, body, sig)
    assert not verify_signature(SECRET, body, "deadbeef")
    assert not verify_signature(SECRET, b"tampered", sig)
    assert not verify_signature("", body, sig)


def test_submit_dry_run_creates_outbox_sent_simulated(
    outbox_client: TestClient, outbox_env: Path
) -> None:
    created = outbox_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]

    submitted = outbox_client.post(f"/orcamentos/{quote_id}/submit")
    assert submitted.status_code == 202, submitted.text
    body = submitted.json()
    assert body["status"] == "submitted"
    assert body["submitted_at"] is not None
    assert body["dry_run"] is True
    assert body["outbox_id"] > 0
    # ADR: dry-run sem notify → sent simulado (sem HTTP externo)
    assert body["outbox_status"] == "sent"

    db = get_hub_db()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT event, status, idempotency_key, payload_json FROM webhook_outbox WHERE id = ?",
            (body["outbox_id"],),
        ).fetchone()
    assert row is not None
    assert row["event"] == "quote.submit"
    assert row["status"] == "sent"
    assert row["idempotency_key"] == f"quote.submit:quote:{quote_id}"
    envelope = json.loads(str(row["payload_json"]))
    assert envelope["dry_run"] is True
    assert envelope["event"] == "quote.submit"
    assert envelope["resource_id"] == quote_id


def test_callback_hmac_invalid_returns_401(outbox_client: TestClient) -> None:
    payload = {
        "event": "quote.submit",
        "resource_type": "quote",
        "resource_id": 1,
        "status": "ok",
        "outbox_id": 1,
        "dry_run": True,
    }
    raw = json.dumps(payload).encode("utf-8")
    res = outbox_client.post(
        "/webhooks/n8n/callback",
        content=raw,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: "invalid"},
    )
    assert res.status_code == 401


def test_callback_hmac_missing_returns_401(outbox_client: TestClient) -> None:
    payload = {
        "event": "quote.submit",
        "resource_type": "quote",
        "resource_id": 1,
        "status": "ok",
        "outbox_id": 1,
    }
    res = outbox_client.post("/webhooks/n8n/callback", json=payload)
    assert res.status_code == 401


def test_callback_valid_path_smoke(outbox_client: TestClient) -> None:
    created = outbox_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    submitted = outbox_client.post(f"/orcamentos/{quote_id}/submit")
    outbox_id = submitted.json()["outbox_id"]

    callback_body = {
        "event": "quote.submit",
        "resource_type": "quote",
        "resource_id": quote_id,
        "status": "ok",
        "outbox_id": outbox_id,
        "external": {
            "tiflux_ticket_number": "T-999",
            "vhsys_os_id": "OS-42",
        },
        "dry_run": True,
    }
    raw = json.dumps(callback_body).encode("utf-8")
    sig = hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()

    res = outbox_client.post(
        "/webhooks/n8n/callback",
        content=raw,
        headers={"Content-Type": "application/json", SIGNATURE_HEADER: sig},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    assert res.json()["status"] == "ok"

    db = get_hub_db()
    with db.connect() as conn:
        outbox = conn.execute(
            "SELECT status, acked_at FROM webhook_outbox WHERE id = ?",
            (outbox_id,),
        ).fetchone()
        quote = conn.execute(
            "SELECT tiflux_ticket_number, vhsys_os_id FROM quotes WHERE id = ?",
            (quote_id,),
        ).fetchone()
    assert outbox is not None
    assert outbox["status"] == "acked"
    assert outbox["acked_at"] is not None
    assert quote is not None
    assert quote["tiflux_ticket_number"] == "T-999"
    assert quote["vhsys_os_id"] == "OS-42"


def test_mark_sent_dry_run(outbox_client: TestClient) -> None:
    created = outbox_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    outbox_client.post(f"/orcamentos/{quote_id}/submit")
    marked = outbox_client.post(f"/orcamentos/{quote_id}/mark-sent")
    assert marked.status_code == 202, marked.text
    body = marked.json()
    assert body["status"] == "sent"
    assert body["outbox_status"] == "sent"
    assert body["dry_run"] is True


def test_submit_idempotent_conflict_after_sent(outbox_client: TestClient) -> None:
    created = outbox_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    first = outbox_client.post(f"/orcamentos/{quote_id}/submit")
    assert first.status_code == 202
    # já submitted — segundo submit deve 409
    second = outbox_client.post(f"/orcamentos/{quote_id}/submit")
    assert second.status_code == 409
