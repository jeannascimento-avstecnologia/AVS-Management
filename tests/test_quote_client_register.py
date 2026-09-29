from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.cnpj.validator import validate_cpf
from src.main import app
from src.mapping.canonical import CompanyPayload
from src.mapping.vhsys_mapper import to_vhsys_payload
from src.orchestrator import (
    IntegrationResult,
    SystemResult,
    integrate_company,
    partial_registration_message,
)
from src.quotes.schemas import QuoteWrite

CPF = "11144477735"
client = TestClient(app)


def test_validate_known_cpf():
    assert validate_cpf(CPF) is True
    assert validate_cpf("111.444.777-35") is True
    assert validate_cpf("11111111111") is False


def test_vhsys_mapper_pf():
    company = CompanyPayload(
        cnpj_digits=CPF,
        cnpj_formatted="111.444.777-35",
        legal_name="Ana Souza",
        trade_name="Ana Souza",
        person_type="PF",
    )
    payload = to_vhsys_payload(company)
    assert payload["tipo_pessoa"] == "PF"
    assert payload["cnpj_cliente"] == "111.444.777-35"
    assert payload["razao_cliente"] == "Ana Souza"


def test_quote_write_accepts_cpf():
    quote = QuoteWrite(cnpj="111.444.777-35")
    assert quote.cnpj == CPF


def test_quote_write_rejects_garbage_document():
    with pytest.raises(ValidationError):
        QuoteWrite(cnpj="000")


def test_partial_message_tiflux_ok_vhsys_fail():
    result = IntegrationResult(cnpj="00.000.000/0001-91")
    result.tiflux = SystemResult(success=True, message="Cliente criado no TiFlux.", data={"id": 9})
    result.vhsys = SystemResult(success=False, error="timeout VHSYS")
    message = partial_registration_message(result)
    assert message is not None
    assert "TiFlux" in message
    assert "VHSYS falhou" in message
    assert "timeout VHSYS" in message


def test_partial_message_ignores_duplicate_skip():
    result = IntegrationResult(cnpj="00.000.000/0001-91")
    result.tiflux = SystemResult(success=True, skipped=True, data={"id": 1})
    result.vhsys = SystemResult(success=True, data={"id_cliente": 2})
    assert partial_registration_message(result) is None


@pytest.mark.asyncio
async def test_integrate_pf_skips_brasilapi():
    refresh = AsyncMock()
    with (
        patch("src.orchestrator._ensure_credentials"),
        patch("src.orchestrator._refresh_registration_status", refresh),
        patch("src.orchestrator.TifluxClient") as mock_tf_cls,
        patch("src.orchestrator.VhsysClient") as mock_vh_cls,
    ):
        mock_tf_cls.return_value.find_by_cnpj = AsyncMock(return_value=None)
        mock_tf_cls.return_value.create_client = AsyncMock(return_value={"id": 42})
        mock_vh_cls.return_value.find_by_cnpj = AsyncMock(return_value=None)
        mock_vh_cls.return_value.create_client = AsyncMock(return_value={"id_cliente": 7})

        result = await integrate_company(
            {
                "person_type": "PF",
                "cnpj_digits": CPF,
                "legal_name": "Ana Souza",
                "trade_name": "Ana",
            },
            desk_ids=[1],
            technical_group_ids=[2],
            settings=MagicMock(),
        )

    refresh.assert_not_called()
    assert result.success is True
    assert result.partial is False
    assert result.tiflux.data == {"id": 42}
    created = mock_vh_cls.return_value.create_client.await_args.args[0]
    assert created.person_type == "PF"
    assert created.cnpj_formatted == "111.444.777-35"


def test_register_quote_client_partial_207(monkeypatch):
    async def _fake(*_args, **_kwargs):
        result = IntegrationResult(cnpj="00.764.239/0001-38")
        result.success = True
        result.partial = True
        result.tiflux = SystemResult(success=True, message="ok", data={"id": 42})
        result.vhsys = SystemResult(success=False, error="timeout VHSYS")
        return result

    monkeypatch.setattr("src.quotes.router.integrate_company", _fake)
    response = client.post(
        "/orcamentos/clientes",
        json={
            "company": {
                "person_type": "PJ",
                "cnpj_digits": "00764239000138",
                "legal_name": "EMPRESA TESTE LTDA",
                "trade_name": "EMPRESA TESTE",
            },
            "desk_ids": [1],
            "technical_group_ids": [2],
        },
    )
    assert response.status_code == 207
    body = response.json()
    assert "VHSYS falhou" in body["partial_message"]
    assert body["tiflux"]["data"]["id"] == 42


def test_preview_quote_client_invalid_cpf():
    response = client.post(
        "/orcamentos/clientes/preview",
        json={"person_type": "PF", "document": "11111111111"},
    )
    assert response.status_code == 400
    assert response.json()["success"] is False
