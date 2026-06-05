from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, clear_settings_cache
from src.main import app
from src.mapping.canonical import from_brasilapi
from src.cnpj.validator import validate_cnpj


BAIXADA_CNPJ = "00764239000138"
BAIXADA_FORMATTED = "00.764.239/0001-38"

BAIXADA_BRASILAPI = {
    "cnpj": BAIXADA_CNPJ,
    "razao_social": "GERAIS COPIADORA E PAPELARIA LTDA",
    "nome_fantasia": "GERAIS COPIADORA",
    "cep": "30130100",
    "logradouro": "RUA EXEMPLO",
    "numero": "100",
    "complemento": "",
    "bairro": "CENTRO",
    "municipio": "BELO HORIZONTE",
    "uf": "MG",
    "ddd_telefone_1": "3133334444",
    "email": None,
    "descricao_situacao_cadastral": "BAIXADA",
    "cnae_fiscal": 4761001,
    "cnae_fiscal_descricao": "Comércio varejista de livros",
}


client = TestClient(app)


def test_cnpj_00764239000138_is_mathematically_valid():
    assert validate_cnpj(BAIXADA_CNPJ) is True


def test_from_brasilapi_baixada_maps_registration_status():
    company = from_brasilapi(BAIXADA_BRASILAPI)
    assert company.cnpj_digits == BAIXADA_CNPJ
    assert company.registration_status == "BAIXADA"
    assert company.status_active is False


@patch("src.orchestrator.VhsysClient")
@patch("src.orchestrator.TifluxClient")
@patch("src.orchestrator.fetch_cnpj", new_callable=AsyncMock)
def test_preview_baixada_cnpj_returns_warnings(mock_fetch, mock_tiflux_cls, mock_vhsys_cls):
    mock_fetch.return_value = BAIXADA_BRASILAPI

    tiflux = mock_tiflux_cls.return_value
    tiflux.list_desks = AsyncMock(return_value=[{"id": 1, "name": "Mesa", "active": True}])
    tiflux.list_technical_groups = AsyncMock(return_value=[{"id": 10, "name": "Grupo"}])
    tiflux.find_by_cnpj = AsyncMock(return_value=None)

    vhsys = mock_vhsys_cls.return_value
    vhsys.find_by_cnpj = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"TIFLUX_API_TOKEN": "t", "VHSYS_ACCESS_TOKEN": "a", "VHSYS_SECRET_ACCESS_TOKEN": "s", "REQUIRE_ACTIVE_CNPJ": "true"}):
        clear_settings_cache()
        response = client.post("/preview", data={"cnpj": BAIXADA_FORMATTED})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["company"]["registration_status"] == "BAIXADA"
    assert body["requires_inactive_override"] is True
    assert any("BAIXADA" in w for w in body["warnings"])


@patch("src.orchestrator.fetch_cnpj", new_callable=AsyncMock)
@patch("src.orchestrator.VhsysClient")
@patch("src.orchestrator.TifluxClient")
def test_integrar_baixada_without_override_blocked(mock_tiflux_cls, mock_vhsys_cls, mock_fetch):
    mock_fetch.return_value = BAIXADA_BRASILAPI
    company = from_brasilapi(BAIXADA_BRASILAPI)

    with patch.dict("os.environ", {"TIFLUX_API_TOKEN": "t", "VHSYS_ACCESS_TOKEN": "a", "VHSYS_SECRET_ACCESS_TOKEN": "s", "REQUIRE_ACTIVE_CNPJ": "true"}):
        clear_settings_cache()
        response = client.post(
            "/integrar",
            json={
                "company": {
                    "cnpj_digits": company.cnpj_digits,
                    "legal_name": company.legal_name,
                    "trade_name": company.trade_name,
                    "status_active": False,
                },
                "desk_ids": [1],
                "technical_group_ids": [10],
            },
        )

    assert response.status_code == 422
    assert "BAIXADA" in response.json()["error"]
    mock_fetch.assert_awaited()


@patch("src.orchestrator.fetch_cnpj", new_callable=AsyncMock)
@patch("src.orchestrator.VhsysClient")
@patch("src.orchestrator.TifluxClient")
def test_integrar_ativa_without_registration_status_in_payload(mock_tiflux_cls, mock_vhsys_cls, mock_fetch):
    ativa_api = {**BAIXADA_BRASILAPI, "cnpj": "19131243000197", "descricao_situacao_cadastral": "ATIVA", "situacao_cadastral": 2}
    mock_fetch.return_value = ativa_api

    tiflux = mock_tiflux_cls.return_value
    tiflux.find_by_cnpj = AsyncMock(return_value=None)
    tiflux.create_client = AsyncMock(return_value={"id": 99})

    vhsys = mock_vhsys_cls.return_value
    vhsys.find_by_cnpj = AsyncMock(return_value=None)
    vhsys.create_client = AsyncMock(return_value={"id_cliente": 88})

    with patch.dict("os.environ", {"TIFLUX_API_TOKEN": "t", "VHSYS_ACCESS_TOKEN": "a", "VHSYS_SECRET_ACCESS_TOKEN": "s", "REQUIRE_ACTIVE_CNPJ": "true"}):
        clear_settings_cache()
        response = client.post(
            "/integrar",
            json={
                "company": {
                    "cnpj_digits": "19131243000197",
                    "legal_name": "OPEN KNOWLEDGE BRASIL",
                    "trade_name": "REDE",
                },
                "desk_ids": [1],
                "technical_group_ids": [10],
            },
        )

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_preview_baixada_cnpj_live_brasilapi():
    """@tester — CNPJ 00.764.239/0001-38 deve passar no preview com aviso de BAIXADA."""
    from src.orchestrator import preview_cnpj

    clear_settings_cache()
    settings = Settings()
    if not settings.tiflux_api_token.strip():
        pytest.skip("TIFLUX_API_TOKEN não configurado")

    result = await preview_cnpj(BAIXADA_FORMATTED, settings)

    assert result.company.cnpj_digits == BAIXADA_CNPJ
    assert result.company.registration_status == "BAIXADA"
    assert result.requires_inactive_override is True
    assert any("BAIXADA" in w for w in result.warnings)
