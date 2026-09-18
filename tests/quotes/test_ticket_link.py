from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.models import AuthDatabase
from src.auth.permissions import PERMISSION_ORCAMENTOS, empty_permissions
from src.config import Settings, clear_settings_cache
from src.hub.models import HubDatabase
from src.hub.store import reset_hub_db_cache
from src.integrations.tiflux_client import TifluxApiError, TifluxClient
from src.quotes.schemas import QuoteWrite, TifluxTicketPreview
from src.quotes.service import QuoteService
from src.quotes.ticket_link import (
    APPROVED_CATALOG_LABEL,
    build_create_ticket_payload,
    classify_ticket_link,
    extract_ticket_catalog,
    extract_ticket_closed,
    pick_default_catalog_item_id,
    pick_default_priority_id,
)
from tests.auth_helpers import create_test_user, login_and_csrf

CNPJ = "11222333000181"
QUOTE_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "AVS Teste LTDA",
    "lead_temperature": "quente",
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


def _open_ticket(**overrides: object) -> dict:
    ticket: dict = {
        "ticket_number": 5790,
        "title": "Proposta comercial",
        "is_closed": False,
        "client": {"id": 1, "name": "Cliente AVS", "social": "Cliente AVS"},
        "status": {"id": 79, "name": "Opened", "default_close": False, "default_open": True},
        "services_catalog": None,
        "sla_info": {"solved_in_time": None},
    }
    ticket.update(overrides)
    return ticket


def _closed_ticket(*, catalog: str | None) -> dict:
    cat = None if catalog is None else {"id": 3, "item_name": catalog, "area_name": "Vendas", "catalog_name": "Comercial"}
    return _open_ticket(
        is_closed=True,
        status={"id": 80, "name": "Closed", "default_close": True, "default_open": False},
        services_catalog=cat,
    )


def test_classify_novo_when_not_closed() -> None:
    assert classify_ticket_link(_open_ticket()) == "novo"


def test_classify_aprovado() -> None:
    assert classify_ticket_link(_closed_ticket(catalog=APPROVED_CATALOG_LABEL)) == "aprovado"


def test_classify_aprovado_item_name_sem_prefixo() -> None:
    assert classify_ticket_link(_closed_ticket(catalog="Aprovado")) == "aprovado"


def test_classify_rejeitado_reprovado() -> None:
    assert classify_ticket_link(_closed_ticket(catalog="Microsoft 365 - Reprovado")) == "rejeitado"


def test_classify_rejeitado_wrong_catalog() -> None:
    assert classify_ticket_link(_closed_ticket(catalog="1 - Triagem")) == "rejeitado"


def test_classify_rejeitado_no_catalog() -> None:
    assert classify_ticket_link(_closed_ticket(catalog=None)) == "rejeitado"


def test_extract_catalog_nested_dict() -> None:
    assert extract_ticket_catalog(_closed_ticket(catalog="3 - Aprovado")) == "3 - Aprovado"


def test_extract_catalog_string() -> None:
    assert extract_ticket_catalog({"services_catalog": "3 - Aprovado"}) == "3 - Aprovado"


def test_extract_ticket_closed_ignores_sla() -> None:
    ticket = _open_ticket(sla_info={"solved_in_time": True})
    assert extract_ticket_closed(ticket) is False


@pytest.mark.asyncio
async def test_get_ticket_by_number_404_returns_none() -> None:
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    http.get = AsyncMock(return_value=MagicMock(status_code=404, text="{}"))
    result = await client.get_ticket_by_number("123", http=http)
    assert result is None


@pytest.mark.asyncio
async def test_get_ticket_by_number_invalid_raises_422() -> None:
    client = TifluxClient(Settings(tiflux_api_token="t"))
    with pytest.raises(TifluxApiError) as exc:
        await client.get_ticket_by_number("abc")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_get_ticket_by_number_403_raises() -> None:
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    http.get = AsyncMock(return_value=MagicMock(status_code=403, text="forbidden"))
    with pytest.raises(TifluxApiError) as exc:
        await client.get_ticket_by_number("123", http=http)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_ticket_by_number_unwraps_envelope() -> None:
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    payload = {"ticket": _open_ticket()}
    ok = MagicMock(status_code=200, text="{}")
    ok.json = MagicMock(return_value=payload)
    http.get = AsyncMock(return_value=ok)
    result = await client.get_ticket_by_number("5790", http=http)
    assert result is not None
    assert result["ticket_number"] == 5790


@pytest.fixture()
def quotes_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
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


@pytest.fixture()
def quotes_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auth_path = tmp_path / "auth.db"
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("AUTH_DB_PATH", str(auth_path))
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("SESSION_SECRET", "pytest-only-session-secret-key-32b!!")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "user@avs.com.br,limited@avs.com.br")
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
    clear_settings_cache()
    reset_hub_db_cache()
    from src.auth.store import reset_auth_db_cache

    reset_auth_db_cache()
    yield {"auth": auth_path, "hub": hub_path}
    reset_auth_db_cache()
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def quotes_auth_client(quotes_auth_env: dict[str, Path]):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_link_ticket_persists_and_reads_back(quotes_env: Path) -> None:
    svc = QuoteService(HubDatabase(quotes_env))
    created = svc.create(
        QuoteWrite.model_validate(QUOTE_PAYLOAD),
        created_by=1,
    )
    preview = TifluxTicketPreview.model_validate(
        {
            "ticket_number": "5790",
            "subject": "Proposta",
            "client_name": "Cliente AVS",
            "status": "Opened",
            "catalog": None,
            "closed": False,
            "suggested_link_status": "novo",
        }
    )
    linked = svc.link_ticket(
        created.id,
        "5790",
        catalog=None,
        link_status="novo",
        snapshot=preview,
    )
    assert linked.tiflux_ticket_number == "5790"
    assert linked.ticket_link_status == "novo"
    assert linked.ticket_link_checked_at
    assert linked.ticket_link_snapshot is not None
    assert linked.ticket_link_snapshot.subject == "Proposta"
    got = svc.get(created.id)
    assert got.tiflux_ticket_number == "5790"
    assert got.ticket_link_status == "novo"


def test_unlink_sets_null(quotes_env: Path) -> None:
    svc = QuoteService(HubDatabase(quotes_env))
    created = svc.create(QuoteWrite.model_validate(QUOTE_PAYLOAD), created_by=1)
    svc.link_ticket(
        created.id,
        "10",
        catalog="1 - Triagem",
        link_status="rejeitado",
        snapshot=None,
    )
    unlinked = svc.unlink_ticket(created.id)
    assert unlinked.tiflux_ticket_number is None
    assert unlinked.ticket_link_status is None
    assert unlinked.ticket_link_catalog is None
    assert unlinked.ticket_link_snapshot is None


def test_refresh_ticket_links_batch(quotes_env: Path) -> None:
    svc = QuoteService(HubDatabase(quotes_env))
    ids: list[int] = []
    for name in ("A", "B", "C", "D"):
        created = svc.create(
            QuoteWrite.model_validate({**QUOTE_PAYLOAD, "client_name": name}),
            created_by=1,
        )
        svc.link_ticket(created.id, str(created.id), catalog=None, link_status="novo", snapshot=None)
        ids.append(created.id)
    updated = svc.apply_ticket_link_updates(
        [
            {"quote_id": ids[0], "link_status": "novo", "catalog": None, "snapshot": None},
            {
                "quote_id": ids[1],
                "link_status": "aprovado",
                "catalog": APPROVED_CATALOG_LABEL,
                "snapshot": None,
            },
            {"quote_id": ids[2], "link_status": "rejeitado", "catalog": "1 - Triagem", "snapshot": None},
        ]
    )
    by_id = {q.id: q for q in updated}
    assert by_id[ids[0]].ticket_link_status == "novo"
    assert by_id[ids[1]].ticket_link_status == "aprovado"
    assert by_id[ids[2]].ticket_link_status == "rejeitado"
    still_novo = svc.get(ids[3])
    assert still_novo.ticket_link_status == "novo"


def test_lead_filter_excludes_approved_rejected(quotes_env: Path) -> None:
    svc = QuoteService(HubDatabase(quotes_env))
    hot = svc.create(
        QuoteWrite.model_validate({**QUOTE_PAYLOAD, "lead_temperature": "quente", "client_name": "Hot"}),
        created_by=1,
    )
    approved = svc.create(
        QuoteWrite.model_validate({**QUOTE_PAYLOAD, "lead_temperature": "quente", "client_name": "Won"}),
        created_by=1,
    )
    svc.link_ticket(
        approved.id,
        "99",
        catalog=APPROVED_CATALOG_LABEL,
        link_status="aprovado",
        snapshot=None,
    )
    listed = svc.list(lead_temperature="quente")
    ids = {q.id for q in listed}
    assert hot.id in ids
    assert approved.id not in ids


def test_get_tiflux_ticket_preview(quotes_client: TestClient) -> None:
    with patch(
        "src.quotes.router.TifluxClient.get_ticket_by_number",
        new=AsyncMock(return_value=_open_ticket()),
    ):
        res = quotes_client.get("/orcamentos/tiflux/tickets/5790")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ticket_number"] == "5790"
    assert body["closed"] is False
    assert body["suggested_link_status"] == "novo"


def test_get_tiflux_ticket_404(quotes_client: TestClient) -> None:
    with patch(
        "src.quotes.router.TifluxClient.get_ticket_by_number",
        new=AsyncMock(return_value=None),
    ):
        res = quotes_client.get("/orcamentos/tiflux/tickets/1")
    assert res.status_code == 404


def test_get_tiflux_ticket_without_token(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIFLUX_API_TOKEN", "")
    clear_settings_cache()
    res = quotes_client.get("/orcamentos/tiflux/tickets/1")
    assert res.status_code == 503
    clear_settings_cache()


@pytest.mark.asyncio
async def test_list_tickets_sends_client_ids_and_desk_ids() -> None:
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    ok = MagicMock(status_code=200, text="[]")
    ok.json = MagicMock(return_value=[_open_ticket()])
    http.get = AsyncMock(return_value=ok)
    result = await client.list_tickets(client_id=11, desk_id=36089, http=http)
    assert result[0]["ticket_number"] == 5790
    params = http.get.await_args.kwargs["params"]
    assert params["client_ids"] == "11"
    assert params["desk_ids"] == "36089"


def test_list_tiflux_tickets_by_client(quotes_client: TestClient) -> None:
    mock_list = AsyncMock(
        return_value=[_open_ticket(), _closed_ticket(catalog="1 - Triagem")],
    )
    with patch("src.quotes.router.TifluxClient.list_tickets", new=mock_list):
        res = quotes_client.get("/orcamentos/tiflux/tickets?client_id=31116")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["client_id"] == 31116
    assert body["desk_id"] == 36089
    numbers = [row["ticket_number"] for row in body["tickets"]]
    assert "5790" in numbers
    assert mock_list.await_args.kwargs["client_id"] == 31116
    assert mock_list.await_args.kwargs["desk_id"] == 36089


def test_list_tiflux_tickets_requires_client_id(quotes_client: TestClient) -> None:
    res = quotes_client.get("/orcamentos/tiflux/tickets")
    assert res.status_code == 422


def test_link_and_unlink_quote_ticket(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    with patch(
        "src.quotes.router.TifluxClient.get_ticket_by_number",
        new=AsyncMock(return_value=_closed_ticket(catalog=APPROVED_CATALOG_LABEL)),
    ):
        linked = quotes_client.post(
            f"/orcamentos/{quote_id}/ticket",
            json={"ticket_number": "5790"},
        )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["tiflux_ticket_number"] == "5790"
    assert body["ticket_link_status"] == "aprovado"
    assert body["ticket_link_catalog"] == APPROVED_CATALOG_LABEL
    assert body["ticket_link_snapshot"]["subject"] == "Proposta comercial"

    with patch(
        "src.quotes.router.TifluxClient.get_ticket_by_number",
        new=AsyncMock(return_value=None),
    ):
        missing = quotes_client.post(
            f"/orcamentos/{quote_id}/ticket",
            json={"ticket_number": "0"},
        )
    assert missing.status_code == 404

    deleted = quotes_client.delete(f"/orcamentos/{quote_id}/ticket")
    assert deleted.status_code == 200
    assert deleted.json()["tiflux_ticket_number"] is None
    assert deleted.json()["ticket_link_status"] is None


def test_refresh_ticket_links_route_partial_failure(quotes_client: TestClient) -> None:
    ids: list[int] = []
    for name in ("Open", "Won", "Lost"):
        created = quotes_client.post(
            "/orcamentos",
            json={**QUOTE_PAYLOAD, "client_name": name},
        )
        qid = created.json()["id"]
        ids.append(qid)
        with patch(
            "src.quotes.router.TifluxClient.get_ticket_by_number",
            new=AsyncMock(return_value=_open_ticket(ticket_number=qid)),
        ):
            linked = quotes_client.post(
                f"/orcamentos/{qid}/ticket",
                json={"ticket_number": str(qid)},
            )
        assert linked.status_code == 200, linked.text

    async def _fake_get(self, ticket_number, *, http=None):  # noqa: ANN001
        number = str(ticket_number)
        if number == str(ids[0]):
            return _open_ticket(ticket_number=ids[0])
        if number == str(ids[1]):
            return _closed_ticket(catalog=APPROVED_CATALOG_LABEL)
        raise TifluxApiError("boom", 502)

    with patch("src.quotes.router.TifluxClient.get_ticket_by_number", new=_fake_get):
        res = quotes_client.post(
            "/orcamentos/refresh-ticket-links",
            json={"quote_ids": ids},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    updated = {q["id"]: q["ticket_link_status"] for q in body["updated"]}
    assert updated[ids[0]] == "novo"
    assert updated[ids[1]] == "aprovado"
    assert len(body["failures"]) == 1
    assert body["failures"][0]["quote_id"] == ids[2]


def test_ticket_routes_require_permission(quotes_auth_client: TestClient) -> None:
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
    perms[PERMISSION_ORCAMENTOS] = False
    db.set_permissions(user.id, perms)
    headers = login_and_csrf(quotes_auth_client, "limited@avs.com.br", password)
    blocked = quotes_auth_client.get("/orcamentos/tiflux/tickets/1", headers=headers)
    assert blocked.status_code == 403


def test_pick_default_catalog_prefers_triagem() -> None:
    items = [
        {"id": 3, "item_name": APPROVED_CATALOG_LABEL},
        {"id": 9, "item_name": "2 - Negociação"},
        {"id": 1, "item_name": "1 - Triagem"},
    ]
    assert pick_default_catalog_item_id(items) == 1


def test_pick_default_priority_prefers_baixa() -> None:
    items = [
        {"id": 10, "name": "Alta", "order": 1},
        {"id": 11, "name": "Baixa", "order": 3},
    ]
    assert pick_default_priority_id(items) == 11


def test_build_create_ticket_payload_requestor_id_wins() -> None:
    payload = build_create_ticket_payload(
        title="T",
        description="D",
        client_id=11,
        desk_id=36089,
        services_catalogs_item_id=1,
        priority_id=2,
        requestor_id=99,
        requestor_name="Ana",
        requestor_email="ana@avs.com.br",
    )
    assert payload["desk_id"] == 36089
    assert payload["requestor_id"] == 99
    assert "requestor_email" not in payload


def test_ticket_defaults_requires_client(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    res = quotes_client.get(f"/orcamentos/{quote_id}/ticket-defaults")
    assert res.status_code == 422


def test_ticket_defaults_prefills_comercial_desk(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "tiflux_client_id": 31116, "title": "Backup M365"},
    )
    quote_id = created.json()["id"]
    with (
        patch(
            "src.quotes.router.TifluxClient.get_desk",
            new=AsyncMock(return_value={"id": 36089, "display_name": "Comercial"}),
        ),
        patch(
            "src.quotes.router.TifluxClient.list_desk_priorities",
            new=AsyncMock(return_value=[{"id": 11, "name": "Baixa", "order": 2}]),
        ),
        patch(
            "src.quotes.router.TifluxClient.list_desk_catalog_items",
            new=AsyncMock(
                return_value=[
                    {"id": 1, "item_name": "1 - Triagem", "area_name": "Vendas"},
                    {"id": 3, "item_name": APPROVED_CATALOG_LABEL},
                ]
            ),
        ),
        patch(
            "src.quotes.router.TifluxClient.get_client_requestors",
            new=AsyncMock(return_value=[{"id": 77, "name": "Ana", "email": "ana@avs.com.br"}]),
        ),
    ):
        res = quotes_client.get(f"/orcamentos/{quote_id}/ticket-defaults")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["desk_id"] == 36089
    assert body["desk_name"] == "Comercial"
    assert body["default_catalog_item_id"] == 1
    assert body["default_priority_id"] == 11
    assert body["default_requestor_id"] == 77
    assert body["title"] == "Backup M365"


def test_create_ticket_links_quote(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "tiflux_client_id": 31116, "title": "Backup M365"},
    )
    quote_id = created.json()["id"]
    with patch(
        "src.quotes.router.TifluxClient.create_ticket",
        new=AsyncMock(return_value=_open_ticket(ticket_number=65219)),
    ) as mock_create:
        res = quotes_client.post(
            f"/orcamentos/{quote_id}/ticket/create",
            json={
                "title": "Backup M365",
                "description": "Orçamento M1",
                "services_catalogs_item_id": 1,
                "priority_id": 11,
                "requestor_id": 77,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tiflux_ticket_number"] == "65219"
    assert body["ticket_link_status"] == "novo"
    sent = mock_create.await_args.args[0]
    assert sent["desk_id"] == 36089
    assert sent["client_id"] == 31116
    assert sent["services_catalogs_item_id"] == 1


def test_create_ticket_conflict_when_already_linked(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "tiflux_client_id": 31116},
    )
    quote_id = created.json()["id"]
    with patch(
        "src.quotes.router.TifluxClient.get_ticket_by_number",
        new=AsyncMock(return_value=_open_ticket()),
    ):
        linked = quotes_client.post(
            f"/orcamentos/{quote_id}/ticket",
            json={"ticket_number": "5790"},
        )
    assert linked.status_code == 200
    res = quotes_client.post(
        f"/orcamentos/{quote_id}/ticket/create",
        json={"title": "X", "description": "Y"},
    )
    assert res.status_code == 409
