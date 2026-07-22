"""pdf_parties.resolve_client usa quote.tiflux_client_id."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.quotes.pdf_parties import resolve_client
from src.quotes.schemas import QuoteItemRead, QuoteRead


def _quote(*, tiflux_client_id: int | None) -> QuoteRead:
    return QuoteRead(
        id=1,
        cnpj="11222333000181",
        client_name="Local Name",
        tiflux_client_id=tiflux_client_id,
        vhsys_client_id=None,
        status="draft",
        lead_temperature=None,
        billed_by_type="distribuidor",
        billed_by_name=None,
        implant_payment_plan=None,
        implant_discount_pct=None,
        implant_discount_value=None,
        implant_labor_hours=None,
        implant_labor_hourly_rate=None,
        monthly_payment_plan=None,
        monthly_discount_pct=None,
        monthly_discount_value=None,
        monthly_labor_hours=None,
        monthly_labor_hourly_rate=None,
        client_email="local@example.com",
        extra_recipients=[],
        tiflux_ticket_number=None,
        vhsys_os_id=None,
        pdf_path=None,
        created_by=1,
        created_at="2026-07-20T12:00:00+00:00",
        updated_at="2026-07-20T12:00:00+00:00",
        submitted_at=None,
        sent_at=None,
        approved_at=None,
        items=[
            QuoteItemRead(
                id=1,
                quote_id=1,
                section="implantacao",
                name="X",
                qty=1,
                unit_value=1.0,
                total_value=1.0,
                sort_order=0,
            )
        ],
    )


@pytest.mark.asyncio
async def test_resolve_client_enriches_from_tiflux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIFLUX_API_TOKEN", "tok")
    from src.config import clear_settings_cache

    clear_settings_cache()
    settings = MagicMock()
    settings.tiflux_api_token = "tok"

    detail = {
        "id": 55,
        "name": "TF Fantasia",
        "social": "TF Razao LTDA",
        "social_revenue": "11222333000181",
        "estadual_registration": "123",
    }
    addresses = [
        {
            "street": "Rua A",
            "number": "10",
            "neighborhood": "Centro",
            "city": "Campinas",
            "state": "SP",
            "cep": "13000000",
        }
    ]
    contacts = [{"email": "tf@cliente.com", "telephone": "1932439559", "use": "commercial"}]

    mock_client = MagicMock()
    mock_client.get_by_id = AsyncMock(return_value=detail)
    mock_client.get_client_addresses = AsyncMock(return_value=addresses)
    mock_client.get_client_contacts = AsyncMock(return_value=contacts)

    with patch("src.quotes.pdf_parties.TifluxClient", return_value=mock_client):
        party = await resolve_client(_quote(tiflux_client_id=55), settings)

    assert party.legal_name == "TF Razao LTDA"
    assert party.email == "tf@cliente.com"
    assert party.street == "Rua A"
    assert party.city == "Campinas"
    assert party.estadual_registration == "123"
    clear_settings_cache()


@pytest.mark.asyncio
async def test_resolve_client_falls_back_without_tiflux_id() -> None:
    party = await resolve_client(_quote(tiflux_client_id=None), MagicMock(tiflux_api_token="tok"))
    assert party.legal_name == "Local Name"
    assert party.email == "local@example.com"
    assert party.street == ""
