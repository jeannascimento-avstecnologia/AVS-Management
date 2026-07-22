"""F1.1 — billing_runs CRUD + perms + approve dry-run outbox."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.auth.models import AuthDatabase
from src.auth.permissions import (
    PERMISSION_APROVAR_FATURA,
    PERMISSION_FATURAR,
    empty_permissions,
)
from src.config import clear_settings_cache
from src.hub.store import get_hub_db, reset_hub_db_cache
from tests.auth_helpers import create_test_user, login_and_csrf

CNPJ = "11222333000181"

RUN_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "Cliente Fatura LTDA",
    "tiflux_client_id": 1001,
    "vhsys_client_id": 2002,
    "competence": "2026-07",
    "due_date": "2026-07-25",
    "has_retencao": False,
    "payment_method": "boleto",
    "gross_total": 1500.0,
    "items": [
        {
            "source": "contract",
            "external_ref": "CTR-1",
            "description": "Mensalidade AVS",
            "amount": 1200.0,
            "sort_order": 0,
        },
        {
            "source": "ticket",
            "external_ref": "T-42",
            "description": "Adicional máquina",
            "amount": 300.0,
            "sort_order": 1,
        },
    ],
}


@pytest.fixture()
def billing_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("HUB_DRY_RUN_NOTIFY_N8N", "false")
    monkeypatch.setenv("N8N_BILLING_WEBHOOK_URL", "")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    clear_settings_cache()
    reset_hub_db_cache()
    yield hub_path
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def billing_client(billing_env: Path):
    from src.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def billing_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auth_path = tmp_path / "auth.db"
    hub_path = tmp_path / "hub.db"
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("AUTH_DB_PATH", str(auth_path))
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("HUB_DRY_RUN_NOTIFY_N8N", "false")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-key-for-pytest-only")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv(
        "ALLOWED_USER_EMAILS",
        "user@avs.com.br,limited@avs.com.br,admin@avs.com.br",
    )
    monkeypatch.setenv("SMTP_HOST", "")
    clear_settings_cache()
    reset_hub_db_cache()
    from src.auth.store import reset_auth_db_cache

    reset_auth_db_cache()
    yield {"auth": auth_path, "hub": hub_path}
    reset_auth_db_cache()
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def billing_auth_client(billing_auth_env: dict[str, Path]):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_create_list_get_run(billing_client: TestClient) -> None:
    created = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] > 0
    assert body["status"] == "draft"
    assert body["cnpj"] == CNPJ
    assert body["competence"] == "2026-07"
    assert body["has_retencao"] is False
    assert body["gross_total"] == 1500.0
    assert body["net_total"] == 1500.0
    assert body["discount_pct"] is None
    assert body["discount_value"] is None
    assert len(body["items"]) == 2
    run_id = body["id"]

    listed = billing_client.get("/faturamento/runs")
    assert listed.status_code == 200
    runs = listed.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["id"] == run_id

    got = billing_client.get(f"/faturamento/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["items"][0]["description"] == "Mensalidade AVS"


def test_create_run_with_discount(billing_client: TestClient) -> None:
    payload = {
        **RUN_PAYLOAD,
        "discount_pct": 10.0,
        "discount_value": 50.0,
    }
    created = billing_client.post("/faturamento/runs", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["gross_total"] == 1500.0
    assert body["discount_pct"] == 10.0
    assert body["discount_value"] == 50.0
    # 10% de 1500 = 150 + 50 = 200 → líquido 1300
    assert body["net_total"] == 1300.0

    run_id = body["id"]
    updated = billing_client.put(
        f"/faturamento/runs/{run_id}",
        json={"discount_pct": 5.0, "discount_value": 0.0},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["net_total"] == 1425.0


def test_update_delete_draft(billing_client: TestClient) -> None:
    created = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    run_id = created.json()["id"]

    updated = billing_client.put(
        f"/faturamento/runs/{run_id}",
        json={"client_name": "Cliente Renomeado", "payment_method": "pix"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["client_name"] == "Cliente Renomeado"
    assert updated.json()["payment_method"] == "pix"

    deleted = billing_client.delete(f"/faturamento/runs/{run_id}")
    assert deleted.status_code == 204
    assert billing_client.get(f"/faturamento/runs/{run_id}").status_code == 404


def test_artifacts_crud(billing_client: TestClient) -> None:
    created = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    run_id = created.json()["id"]

    art = billing_client.post(
        f"/faturamento/runs/{run_id}/artifacts",
        json={"kind": "report", "path_or_url": "https://example.com/relatorio.pdf"},
    )
    assert art.status_code == 201, art.text
    artifact_id = art.json()["id"]
    assert art.json()["kind"] == "report"

    got = billing_client.get(f"/faturamento/runs/{run_id}")
    assert len(got.json()["artifacts"]) == 1

    deleted = billing_client.delete(
        f"/faturamento/runs/{run_id}/artifacts/{artifact_id}"
    )
    assert deleted.status_code == 204
    got2 = billing_client.get(f"/faturamento/runs/{run_id}")
    assert got2.json()["artifacts"] == []


def test_approve_dry_run_creates_outbox_sent(
    billing_client: TestClient, billing_env: Path
) -> None:
    created = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    run_id = created.json()["id"]

    approved = billing_client.post(f"/faturamento/runs/{run_id}/approve")
    assert approved.status_code == 202, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_at"] is not None
    assert body["dry_run"] is True
    assert body["outbox_id"] > 0
    assert body["outbox_status"] == "sent"

    db = get_hub_db()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT event, status, idempotency_key, payload_json FROM webhook_outbox WHERE id = ?",
            (body["outbox_id"],),
        ).fetchone()
    assert row is not None
    assert row["event"] == "billing.approved"
    assert row["status"] == "sent"
    assert row["idempotency_key"] == f"billing.approved:billing_run:{run_id}"
    envelope = json.loads(str(row["payload_json"]))
    assert envelope["dry_run"] is True
    assert envelope["resource_type"] == "billing_run"
    assert "billing_run" in envelope["payload"]


def test_approve_retencao_awaits_prefeitura(billing_client: TestClient) -> None:
    payload = {**RUN_PAYLOAD, "has_retencao": True, "tiflux_client_id": 1002}
    created = billing_client.post("/faturamento/runs", json=payload)
    run_id = created.json()["id"]
    assert created.json()["net_total"] is None

    approved = billing_client.post(f"/faturamento/runs/{run_id}/approve")
    assert approved.status_code == 202, approved.text
    body = approved.json()
    assert body["status"] == "awaiting_prefeitura"
    assert body["outbox_id"] is None

    pref = billing_client.post(
        f"/faturamento/runs/{run_id}/prefeitura",
        json={"nf_prefeitura_number": "NF-999", "net_total": 1350.0},
    )
    assert pref.status_code == 202, pref.text
    pref_body = pref.json()
    assert pref_body["status"] == "approved"
    assert pref_body["nf_prefeitura_number"] == "NF-999"
    assert pref_body["net_total"] == 1350.0
    assert pref_body["outbox_id"] > 0
    assert pref_body["outbox_status"] == "sent"

    db = get_hub_db()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT event, status FROM webhook_outbox WHERE id = ?",
            (pref_body["outbox_id"],),
        ).fetchone()
    assert row is not None
    assert row["event"] == "billing.nf_prefeitura"
    assert row["status"] == "sent"


def test_faturamento_403_without_permission(billing_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "limited@avs.com.br",
        "Limitado",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_FATURAR] = False
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(billing_auth_client, "limited@avs.com.br", password)
    blocked = billing_auth_client.get("/faturamento/runs", headers=headers)
    assert blocked.status_code == 403

    blocked_post = billing_auth_client.post(
        "/faturamento/runs",
        json=RUN_PAYLOAD,
        headers=headers,
    )
    assert blocked_post.status_code == 403


def test_approve_requires_aprovar_fatura(billing_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "user@avs.com.br",
        "Usuário",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_FATURAR] = True
    # sem PERMISSION_APROVAR_FATURA
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(billing_auth_client, "user@avs.com.br", password)
    created = billing_auth_client.post(
        "/faturamento/runs", json=RUN_PAYLOAD, headers=headers
    )
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]

    blocked = billing_auth_client.post(
        f"/faturamento/runs/{run_id}/approve",
        headers=headers,
    )
    assert blocked.status_code == 403


def test_duplicate_tiflux_competence_409(billing_client: TestClient) -> None:
    first = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    assert first.status_code == 201
    second = billing_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    assert second.status_code == 409


def test_tiflux_clients_search(billing_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    clear_settings_cache()
    raw = [{"id": 31116, "name": "AFIADORA", "social_revenue": "58507435000107"}]
    with patch(
        "src.billing.router.TifluxClient.find_by_name",
        new=AsyncMock(return_value=raw),
    ):
        res = billing_client.get("/faturamento/tiflux/clients?q=afia")
    assert res.status_code == 200
    clients = res.json()["clients"]
    assert len(clients) == 1
    assert clients[0]["id"] == 31116
    assert clients[0]["cnpj"] == "58507435000107"
    clear_settings_cache()


def test_tiflux_contracts_list(billing_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    clear_settings_cache()
    raw = [
        {
            "id": 81017,
            "name": "AC | BACKUP M365",
            "total_value": "1525.00",
            "status": "actives",
        }
    ]
    with patch(
        "src.billing.router.TifluxClient.list_contracts",
        new=AsyncMock(return_value=raw),
    ):
        res = billing_client.get("/faturamento/tiflux/clients/31116/contracts")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["contracts"][0]["amount"] == 1525.0
    clear_settings_cache()


def test_tiflux_history_filters(billing_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    clear_settings_cache()
    raw = [
        {
            "billing_id": 425020,
            "billing_date": "2026-07-17",
            "due_date": "2026-08-05",
            "client_id": 37720,
            "client_name": "ARPEJO",
            "real_value": "4205.54",
            "nfe_number": None,
            "paid": False,
            "reversal": False,
        }
    ]
    with patch(
        "src.billing.router.TifluxClient.list_billing_history",
        new=AsyncMock(return_value=raw),
    ) as mocked:
        res = billing_client.get(
            "/faturamento/tiflux/history?billing_day=2026-07-17&client_id=37720"
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 1
    assert body["items"][0]["billing_id"] == 425020
    assert body["items"][0]["real_value"] == 4205.54
    assert body["filters"]["billing_start_date"] == "2026-07-17"
    assert body["filters"]["billing_end_date"] == "2026-07-17"
    mocked.assert_awaited_once()
    kwargs = mocked.await_args.kwargs
    assert kwargs["billing_start_date"] == "2026-07-17"
    assert kwargs["client_id"] == 37720
    clear_settings_cache()


def test_tiflux_history_competence_range(
    billing_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    clear_settings_cache()
    with patch(
        "src.billing.router.TifluxClient.list_billing_history",
        new=AsyncMock(return_value=[]),
    ) as mocked:
        res = billing_client.get("/faturamento/tiflux/history?competence=2026-07")
    assert res.status_code == 200
    assert res.json()["filters"]["billing_start_date"] == "2026-07-01"
    assert res.json()["filters"]["billing_end_date"] == "2026-07-31"
    assert mocked.await_args.kwargs["billing_start_date"] == "2026-07-01"
    clear_settings_cache()


def test_tiflux_contracts_global_list(
    billing_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, patch

    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    clear_settings_cache()
    raw = [
        {
            "id": 81017,
            "name": "AC | BACKUP M365",
            "total_value": "1525.00",
            "status": "actives",
            "client": {"id": 31116, "name": "AFIADORA"},
        }
    ]
    with patch(
        "src.billing.router.TifluxClient.list_contracts",
        new=AsyncMock(return_value=raw),
    ):
        res = billing_client.get("/faturamento/tiflux/contracts?competence=2026-07")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["contracts"][0]["client_id"] == 31116
    assert body["contracts"][0]["local_run_id"] is None
    clear_settings_cache()
