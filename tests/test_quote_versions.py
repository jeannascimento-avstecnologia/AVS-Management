"""Versões de orçamento + rascunho de mensalidades."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.hub.store import reset_hub_db_cache

from tests.test_quotes import QUOTE_PAYLOAD


@pytest.fixture()
def quotes_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    clear_settings_cache()
    reset_hub_db_cache()
    yield hub_path
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def quotes_client(quotes_env: Path):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_create_versions_and_monthly_draft(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    assert created.status_code == 201, created.text
    body = created.json()
    quote_id = body["id"]
    assert body["current_version_number"] is None
    assert "Ticket no." in (body.get("notes") or "")
    item_ids = [i["id"] for i in body["items"]]
    monthly_id = next(i["id"] for i in body["items"] if i["section"] == "mensalidade")
    assert monthly_id in item_ids

    bad = quotes_client.put(
        f"/orcamentos/{quote_id}/mensalidades",
        json={
            "license_item_ids": [monthly_id],
            "charges": [{"name": "Fornecedor", "amount": 1.0, "sort_order": 0}],
        },
    )
    assert bad.status_code == 409, bad.text

    monthly_total = next(
        float(i["total_value"]) for i in body["items"] if i["id"] == monthly_id
    )
    ok = quotes_client.put(
        f"/orcamentos/{quote_id}/mensalidades",
        json={
            "license_item_ids": [monthly_id],
            "charges": [
                {"name": "Fornecedor", "amount": round(monthly_total / 2, 2), "sort_order": 0},
                {
                    "name": "Intermediador",
                    "amount": round(monthly_total - round(monthly_total / 2, 2), 2),
                    "sort_order": 1,
                },
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["monthly_draft_json"]

    v1 = quotes_client.post(f"/orcamentos/{quote_id}/versions")
    assert v1.status_code == 201, v1.text
    assert v1.json()["version_number"] == 1
    assert v1.json()["pdf_path"]

    listed = quotes_client.get(f"/orcamentos/{quote_id}/versions")
    assert listed.status_code == 200
    assert len(listed.json()["versions"]) == 1

    got = quotes_client.get(f"/orcamentos/{quote_id}")
    assert got.json()["current_version_number"] == 1
    assert got.json()["active_quote_version_id"] == v1.json()["id"]

    notes = quotes_client.put(
        f"/orcamentos/{quote_id}",
        json={"notes": "Observacao da v2", "items": QUOTE_PAYLOAD["items"]},
    )
    assert notes.status_code == 200, notes.text

    v2 = quotes_client.post(f"/orcamentos/{quote_id}/versions")
    assert v2.status_code == 201, v2.text
    assert v2.json()["version_number"] == 2
    assert v2.json()["snapshot_notes"] == "Observacao da v2"
    assert v1.json()["id"] != v2.json()["id"]

    pdf = quotes_client.get(
        f"/orcamentos/{quote_id}/versions/{v1.json()['id']}/pdf"
    )
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    listed2 = quotes_client.get(f"/orcamentos/{quote_id}/versions")
    assert len(listed2.json()["versions"]) == 2
