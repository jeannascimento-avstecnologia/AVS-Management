from __future__ import annotations

from src.quotes.margin import (
    compute_quote_margin,
    effective_analyst_hourly_cost,
    infer_margin_kind,
)
from src.quotes.schemas import QuoteItemRead, QuoteModule, QuoteRead


def _quote(**kwargs: object) -> QuoteRead:
    defaults: dict[str, object] = {
        "id": 1,
        "cnpj": "11222333000181",
        "client_name": "X",
        "tiflux_client_id": None,
        "vhsys_client_id": None,
        "status": "draft",
        "lead_temperature": None,
        "billed_by_type": None,
        "billed_by_name": None,
        "implant_payment_plan": None,
        "implant_discount_pct": None,
        "implant_discount_value": None,
        "monthly_payment_plan": None,
        "monthly_discount_pct": None,
        "monthly_discount_value": None,
        "tiflux_ticket_number": None,
        "vhsys_os_id": None,
        "pdf_path": None,
        "created_by": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "submitted_at": None,
        "sent_at": None,
        "approved_at": None,
        "modules": [],
        "items": [],
    }
    defaults.update(kwargs)
    return QuoteRead.model_validate(defaults)


def _item(**kwargs: object) -> QuoteItemRead:
    base: dict[str, object] = {
        "id": 1,
        "quote_id": 1,
        "section": "implantacao",
        "name": "Licença",
        "qty": 2.0,
        "unit_value": 100.0,
        "total_value": 200.0,
        "sort_order": 0,
    }
    base.update(kwargs)
    return QuoteItemRead.model_validate(base)


def test_effective_rate_null_uses_default() -> None:
    assert effective_analyst_hourly_cost(None, 80.0) == 80.0


def test_effective_rate_zero_is_override() -> None:
    assert effective_analyst_hourly_cost(0.0, 80.0) == 0.0


def test_infer_servico_is_implantacao() -> None:
    assert infer_margin_kind(tipo_produto="Servico", name="Setup") == "implantacao"


def test_infer_produto_license_heuristic() -> None:
    assert infer_margin_kind(tipo_produto="Produto", name="Licença M365") == "licenca"
    assert infer_margin_kind(tipo_produto="Produto", name="Backup Acronis") == "licenca"


def test_infer_produto_plain() -> None:
    assert infer_margin_kind(tipo_produto="Produto", name="Switch 24p") == "produto"


def test_infer_unknown_without_tipo() -> None:
    assert infer_margin_kind(tipo_produto=None, name="Qualquer") is None


def test_oneshot_cogs_and_labor() -> None:
    quote = _quote(
        implementation_hours=10.0,
        analyst_hourly_cost=50.0,
        modules=[
            QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao"),
        ],
        items=[_item(unit_cost=40.0)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=80.0)
    assert margin.oneshot.revenue == 200.0
    assert margin.oneshot.cogs == 80.0
    assert margin.oneshot.labor_cost == 500.0
    assert margin.oneshot.profit == 200.0 - 80.0 - 500.0
    assert margin.incomplete is False
    assert margin.modules[0].labor_cost == 500.0
    assert margin.effective_analyst_hourly_cost == 50.0


def test_cost_missing_flags_incomplete() -> None:
    quote = _quote(
        modules=[QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao")],
        items=[_item(unit_cost=None)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.incomplete is True
    assert margin.oneshot.cogs == 0.0
    assert margin.lines[0].cost_missing is True


def test_cost_zero_is_not_missing() -> None:
    quote = _quote(
        modules=[QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao")],
        items=[_item(unit_cost=0.0)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.incomplete is False
    assert margin.lines[0].cost_missing is False


def test_cost_greater_than_sale_negative_profit() -> None:
    quote = _quote(
        modules=[QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao")],
        items=[_item(unit_cost=150.0)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.oneshot.cogs == 300.0
    assert margin.oneshot.profit == -100.0


def test_module_internal_hours_override_quote() -> None:
    quote = _quote(
        implementation_hours=10.0,
        analyst_hourly_cost=50.0,
        modules=[
            QuoteModule(
                id="implantacao",
                title="Implantação",
                legacy_kind="implantacao",
                internal_labor_hours=2.0,
                internal_hourly_cost=100.0,
            ),
        ],
        items=[_item(unit_cost=0.0)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=80.0)
    assert margin.oneshot.labor_cost == 200.0
    assert margin.modules[0].hours == 2.0


def test_monthly_allocation_excluded_from_oneshot() -> None:
    monthly = _item(
        id=2,
        section="mensalidade",
        name="Plano",
        qty=1,
        unit_value=299.9,
        total_value=299.9,
        unit_cost=100.0,
    )
    implant = _item(id=1, unit_cost=10.0)
    quote = _quote(
        monthly_draft_json=(
            '{"allocations":[{"item_id":2,"fornecedor_name":"F","fornecedor_amount":100,'
            '"intermediador_name":"AVS","intermediador_amount":199.9}]}'
        ),
        modules=[
            QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao"),
            QuoteModule(
                id="mensalidade", title="Mensalidade", legacy_kind="mensalidade", show_labor=True
            ),
        ],
        items=[implant, monthly],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.oneshot.revenue == 200.0
    assert margin.oneshot.cogs == 20.0
    assert margin.recurring.revenue == 299.9
    assert margin.recurring.fornecedor == 100.0
    assert margin.recurring.intermediador == 199.9
    buckets = {ln.item_id: ln.bucket for ln in margin.lines}
    assert buckets[1] == "oneshot"
    assert buckets[2] == "recurring"


def test_section_discount_applies_before_profit() -> None:
    quote = _quote(
        modules=[
            QuoteModule(
                id="implantacao",
                title="Implantação",
                legacy_kind="implantacao",
                discount_pct=10.0,
            )
        ],
        items=[_item(unit_cost=40.0)],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.oneshot.revenue == 180.0
    assert margin.oneshot.cogs == 80.0
    assert margin.oneshot.profit == 100.0


def test_default_rate_when_hours_set() -> None:
    quote = _quote(
        implementation_hours=2.0,
        analyst_hourly_cost=None,
        modules=[QuoteModule(id="implantacao", title="Implantação", legacy_kind="implantacao")],
        items=[],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=90.0)
    assert margin.oneshot.labor_cost == 180.0
    assert margin.effective_analyst_hourly_cost == 90.0


# --- API ---

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.hub.store import reset_hub_db_cache


@pytest.fixture()
def quotes_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("QUOTE_ANALYST_HOURLY_COST", "80")
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "t")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "s")
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


def test_get_margem_endpoint(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={
            "cnpj": "11222333000181",
            "client_name": "Margem",
            "implementation_hours": 4,
            "items": [
                {
                    "section": "implantacao",
                    "name": "Setup",
                    "qty": 1,
                    "unit_value": 1000.0,
                    "unit_cost": 200.0,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    res = quotes_client.get(f"/orcamentos/{qid}/margem")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["default_analyst_hourly_cost"] == 80.0
    assert body["oneshot"]["cogs"] == 200.0
    assert body["oneshot"]["labor_cost"] == 320.0
    assert len(body["modules"]) >= 1


def test_refresh_costs_persists_unit_cost(quotes_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={
            "cnpj": "11222333000181",
            "items": [
                {
                    "section": "implantacao",
                    "name": "Licença X",
                    "qty": 2,
                    "unit_value": 50.0,
                    "vhsys_product_id": 9,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    assert created.json()["items"][0]["unit_cost"] is None

    async def fake_get(_self: object, pid: int) -> dict[str, object]:
        assert pid == 9
        return {"id": 9, "name": "Licença X", "cost_value": 15.0, "tipo_produto": "Produto", "kind": "produto"}

    monkeypatch.setattr("src.quotes.router.VhsysClient.get_product", fake_get)
    res = quotes_client.post(f"/orcamentos/{qid}/margem/refresh-costs")
    assert res.status_code == 200, res.text
    assert res.json()["oneshot"]["cogs"] == 30.0
    got = quotes_client.get(f"/orcamentos/{qid}")
    assert got.json()["items"][0]["unit_cost"] == 15.0
    assert got.json()["items"][0]["margin_kind"] == "licenca"


def test_mensalidade_flag_excludes_from_oneshot() -> None:
    implant = _item(id=1, unit_cost=10.0)
    monthly = _item(
        id=2,
        section="lic",
        name="Plano",
        qty=1,
        unit_value=299.9,
        total_value=299.9,
        unit_cost=100.0,
    )
    quote = _quote(
        modules=[
            QuoteModule(
                id="implantacao",
                title="Implantação",
                legacy_kind="implantacao",
                is_mensalidade=False,
            ),
            QuoteModule(id="lic", title="Licenças", is_mensalidade=True),
        ],
        items=[implant, monthly],
    )
    margin = compute_quote_margin(quote, default_analyst_hourly_cost=0)
    assert margin.oneshot.revenue == 200.0
    assert margin.oneshot.cogs == 20.0
    assert margin.recurring.revenue == 299.9
    buckets = {ln.item_id: ln.bucket for ln in margin.lines}
    assert buckets[1] == "oneshot"
    assert buckets[2] == "recurring"


def test_margem_404(quotes_client: TestClient) -> None:
    res = quotes_client.get("/orcamentos/99999/margem")
    assert res.status_code == 404
