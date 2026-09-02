from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.hub.store import reset_hub_db_cache
from src.quotes.totals import apply_section_discount


@pytest.fixture()
def quotes_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.delenv("VHSYS_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("VHSYS_SECRET_ACCESS_TOKEN", raising=False)
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


def test_apply_section_discount_linked_prefers_value() -> None:
    # % e R$ espelhados (10% de 1000 = 100) — não soma
    discount, net = apply_section_discount(1000.0, 10.0, 100.0)
    assert discount == 100.0
    assert net == 900.0


def test_apply_section_discount_pct_only() -> None:
    discount, net = apply_section_discount(1000.0, 10.0, None)
    assert discount == 100.0
    assert net == 900.0


def test_apply_section_discount_value_only() -> None:
    discount, net = apply_section_discount(1000.0, None, 50.0)
    assert discount == 50.0
    assert net == 950.0


def test_apply_section_discount_clamps_to_subtotal() -> None:
    discount, net = apply_section_discount(100.0, 100.0, 120.0)
    assert discount == 100.0
    assert net == 0.0


def test_vhsys_catalog_requires_credentials(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "")
    clear_settings_cache()
    res = quotes_client.get("/orcamentos/vhsys/catalog?q=monitor")
    assert res.status_code == 503
    clear_settings_cache()


def test_vhsys_catalog_search(quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()

    fake_items = [
        {
            "id": 11,
            "kind": "produto",
            "name": "Monitor 24",
            "code": "MON24",
            "unit_value": 899.9,
        }
    ]
    with patch(
        "src.quotes.router.VhsysClient.search_catalog_items",
        new=AsyncMock(return_value=fake_items),
    ):
        res = quotes_client.get("/orcamentos/vhsys/catalog?q=monitor&limit=10")
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "monitor"
    assert body["count"] == 1
    assert body["items"][0]["name"] == "Monitor 24"
    clear_settings_cache()


def test_vhsys_catalog_create_via_dupla(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    created_item = {
        "id": 99,
        "kind": "produto",
        "name": "Servico Novo AVS",
        "code": None,
        "unit_value": 150.0,
    }
    with patch(
        "src.quotes.router.VhsysClient.find_or_create_catalog_item",
        new=AsyncMock(return_value=(created_item, True)),
    ) as mocked:
        res = quotes_client.post(
            "/orcamentos/vhsys/catalog",
            json={"name": "Servico Novo AVS", "unit_value": 150, "tipo_produto": "Servico"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["created"] is True
    assert body["item"]["id"] == 99
    mocked.assert_awaited_once()
    clear_settings_cache()


def test_vhsys_catalog_create_reuses_existing(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    existing = {
        "id": 7,
        "kind": "produto",
        "name": "Ja Existe",
        "code": "X",
        "unit_value": 10.0,
    }
    with patch(
        "src.quotes.router.VhsysClient.find_or_create_catalog_item",
        new=AsyncMock(return_value=(existing, False)),
    ):
        res = quotes_client.post(
            "/orcamentos/vhsys/catalog",
            json={"name": "Ja Existe", "unit_value": 99},
        )
    assert res.status_code == 200
    assert res.json()["created"] is False
    assert res.json()["item"]["id"] == 7
    clear_settings_cache()


def test_vhsys_catalog_all_default_limit_zero(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    fake = [
        {"id": i, "kind": "produto", "name": f"P{i}", "code": None, "unit_value": 1.0}
        for i in range(3)
    ]
    with patch(
        "src.quotes.router.VhsysClient.search_catalog_items",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        res = quotes_client.get("/orcamentos/vhsys/catalog")
    assert res.status_code == 200
    assert res.json()["count"] == 3
    mocked.assert_awaited_once()
    assert mocked.await_args.kwargs["limit"] == 0
    clear_settings_cache()


def test_vhsys_parties_min_query(quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    res = quotes_client.get("/orcamentos/vhsys/parties?q=a")
    assert res.status_code == 200
    assert res.json()["parties"] == []
    clear_settings_cache()


def test_vhsys_parties_search(quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    raw = [
        {
            "id_cliente": 42,
            "razao_cliente": "Distribuidor Alfa LTDA",
            "fantasia_cliente": "Alfa",
            "cnpj_cliente": "11.222.333/0001-81",
        }
    ]
    with patch(
        "src.quotes.router.VhsysClient.find_matches_by_name",
        new=AsyncMock(return_value=raw),
    ):
        res = quotes_client.get("/orcamentos/vhsys/parties?q=alfa")
    assert res.status_code == 200
    parties = res.json()["parties"]
    assert len(parties) == 1
    assert parties[0]["id"] == 42
    assert parties[0]["name"] == "Distribuidor Alfa LTDA"
    clear_settings_cache()


def test_vhsys_client_contact_email(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    with patch(
        "src.quotes.router.VhsysClient.get_by_id",
        new=AsyncMock(
            return_value={
                "id_cliente": 9,
                "razao_cliente": "Empresa X",
                "email_cliente": "compras@empresa.com",
            }
        ),
    ):
        res = quotes_client.get("/orcamentos/vhsys/clients/9")
    assert res.status_code == 200
    assert res.json()["email"] == "compras@empresa.com"
    clear_settings_cache()


def test_vhsys_categories_list(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    fake = [{"id": 10, "name": "VOIP", "subcategories": []}, {"id": 11, "name": "Cloud", "subcategories": []}]
    with patch(
        "src.quotes.router.VhsysClient.list_catalog_categories",
        new=AsyncMock(return_value=fake),
    ):
        res = quotes_client.get("/orcamentos/vhsys/categories")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2
    assert body["categories"][0]["name"] == "VOIP"
    clear_settings_cache()


def test_vhsys_catalog_filter_by_category(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    fake = [
        {
            "id": 1,
            "kind": "produto",
            "name": "Ramal",
            "code": None,
            "unit_value": 50.0,
            "category_id": 10,
        }
    ]
    with patch(
        "src.quotes.router.VhsysClient.search_catalog_items",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        res = quotes_client.get("/orcamentos/vhsys/catalog?category_id=10&limit=20")
    assert res.status_code == 200
    body = res.json()
    assert body["category_id"] == 10
    assert body["items"][0]["category_id"] == 10
    assert mocked.await_args.kwargs["category_id"] == 10
    clear_settings_cache()


def test_vhsys_catalog_filter_by_subcategory(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "sec")
    clear_settings_cache()
    fake = [
        {
            "id": 2,
            "kind": "produto",
            "name": "Firewall",
            "code": None,
            "unit_value": 100.0,
            "category_id": 10,
            "subcategory_ids": [22],
        }
    ]
    with patch(
        "src.quotes.router.VhsysClient.search_catalog_items",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        res = quotes_client.get(
            "/orcamentos/vhsys/catalog?category_id=10&subcategory_id=22&limit=20"
        )
    assert res.status_code == 200
    body = res.json()
    assert body["subcategory_id"] == 22
    assert mocked.await_args.kwargs["subcategory_id"] == 22
    clear_settings_cache()


def test_tiflux_quote_clients_search(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
    clear_settings_cache()
    with patch(
        "src.quotes.router.TifluxClient.find_matches_by_cnpj",
        new=AsyncMock(
            return_value=[
                {"id": 55, "name": "Cliente TF", "social_revenue": "11222333000181"}
            ]
        ),
    ):
        res = quotes_client.get("/orcamentos/tiflux/clients?q=11.222.333/0001-81")
    assert res.status_code == 200
    clients = res.json()["clients"]
    assert len(clients) == 1
    assert clients[0]["id"] == 55
    assert clients[0]["cnpj"] == "11222333000181"
    clear_settings_cache()


def test_tiflux_quote_clients_by_name(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
    clear_settings_cache()
    with patch(
        "src.quotes.router.TifluxClient.find_by_name",
        new=AsyncMock(return_value=[{"id": 77, "name": "Acme", "social_revenue": ""}]),
    ):
        res = quotes_client.get("/orcamentos/tiflux/clients?q=acme")
    assert res.status_code == 200
    assert res.json()["clients"][0]["id"] == 77
    clear_settings_cache()


def test_tiflux_client_contact_email(
    quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tf-tok")
    clear_settings_cache()
    with (
        patch(
            "src.quotes.router.TifluxClient.get_by_id",
            new=AsyncMock(return_value={"id": 55, "name": "Cliente TF"}),
        ),
        patch(
            "src.quotes.router.TifluxClient.get_client_contacts",
            new=AsyncMock(return_value=[{"email": "contato@tiflux.example"}]),
        ),
    ):
        res = quotes_client.get("/orcamentos/tiflux/clients/55")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == 55
    assert body["email"] == "contato@tiflux.example"
    clear_settings_cache()


def test_normalize_catalog_category_and_product() -> None:
    from src.integrations.vhsys_client import (
        _normalize_catalog_category,
        _normalize_catalog_product,
        _normalize_catalog_subcategory,
        _product_subcategory_ids,
    )

    cat = _normalize_catalog_category(
        {
            "id_categoria": 9,
            "nome_categoria": "VOIP",
            "status_categoria": "Ativo",
            "lixeira": "Nao",
            "subcategorias": [
                {"id_subcategoria": 21, "nome_subcategoria": "Ramais", "status_subcategoria": "Ativo"}
            ],
        }
    )
    assert cat == {
        "id": 9,
        "name": "VOIP",
        "subcategories": [{"id": 21, "name": "Ramais"}],
    }
    inactive = _normalize_catalog_category(
        {"id_categoria": 1, "nome_categoria": "X", "status_categoria": "Inativo"}
    )
    assert inactive is None
    sub = _normalize_catalog_subcategory(
        {
            "id_subcategoria": 21,
            "id_categoria": 9,
            "nome_subcategoria": "Ramais",
            "status_subcategoria": "Ativo",
            "lixeira": "Nao",
        }
    )
    assert sub == {"id": 21, "name": "Ramais", "category_id": 9}
    prod = _normalize_catalog_product(
        {
            "id_produto": 3,
            "desc_produto": "Ramal",
            "valor_produto": "99,90",
            "id_categoria": 9,
            "subcategoria": [{"id_subcategoria": 21}],
        }
    )
    assert prod is not None
    assert prod["category_id"] == 9
    assert prod["unit_value"] == 99.9
    assert prod["subcategory_ids"] == [21]
    assert _product_subcategory_ids({"id_subcategoria": 7, "subcategoria": [7, 8]}) == [7, 8]
