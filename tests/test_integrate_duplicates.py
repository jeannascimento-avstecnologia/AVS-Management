from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mapping.canonical import from_brasilapi
from src.orchestrator import integrate_company

SAMPLE = {
    "cnpj": "00764239000138",
    "razao_social": "EMPRESA TESTE LTDA",
    "nome_fantasia": "EMPRESA TESTE",
    "cep": "30130100",
    "logradouro": "RUA EXEMPLO",
    "numero": "100",
    "complemento": "",
    "bairro": "CENTRO",
    "municipio": "BELO HORIZONTE",
    "uf": "MG",
    "ddd_telefone_1": "3133334444",
    "email": None,
    "descricao_situacao_cadastral": "ATIVA",
    "cnae_fiscal": 4761001,
    "cnae_fiscal_descricao": "Comércio",
}


@pytest.mark.asyncio
async def test_integrate_both_duplicates_not_success():
    company = from_brasilapi(SAMPLE)

    with (
        patch("src.orchestrator._ensure_credentials"),
        patch("src.orchestrator._refresh_registration_status", new_callable=AsyncMock),
        patch("src.orchestrator.TifluxClient") as mock_tf_cls,
        patch("src.orchestrator.VhsysClient") as mock_vh_cls,
    ):
        mock_tf_cls.return_value.find_by_cnpj = AsyncMock(return_value={"id": 1})
        mock_vh_cls.return_value.find_by_cnpj = AsyncMock(return_value={"id_cliente": 2})

        result = await integrate_company(
            company.__dict__ | {"cnpj_digits": company.cnpj_digits},
            desk_ids=[1],
            technical_group_ids=[1],
            settings=MagicMock(),
        )

    assert result.all_duplicates is True
    assert result.success is False
    assert result.duplicates == {"tiflux": True, "vhsys": True}


@pytest.mark.asyncio
async def test_integrate_only_vhsys_target_when_tiflux_exists():
    company = from_brasilapi(SAMPLE)

    with (
        patch("src.orchestrator._ensure_credentials"),
        patch("src.orchestrator._refresh_registration_status", new_callable=AsyncMock),
        patch("src.orchestrator.TifluxClient") as mock_tf_cls,
        patch("src.orchestrator.VhsysClient") as mock_vh_cls,
    ):
        mock_tf_cls.return_value.find_by_cnpj = AsyncMock(return_value={"id": 1})
        mock_vh_cls.return_value.find_by_cnpj = AsyncMock(return_value=None)
        mock_vh_cls.return_value.create_client = AsyncMock(return_value={"id_cliente": 99})

        result = await integrate_company(
            company.__dict__ | {"cnpj_digits": company.cnpj_digits},
            desk_ids=[1],
            technical_group_ids=[1],
            settings=MagicMock(),
            targets=["vhsys"],
        )

    assert result.success is True
    assert result.partial is False
    assert result.vhsys.skipped is False
    assert result.tiflux.skipped is True
