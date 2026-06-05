import pytest



from src.config import Settings, clear_settings_cache

from src.cnpj.brasilapi_client import fetch_cnpj

from src.cnpj.validator import validate_cnpj

from src.mapping.canonical import from_brasilapi



pytestmark = pytest.mark.integration



SMOKE_CNPJ = "19131243000197"

TARGET_CNPJ = "65074067000116"





def _has_tokens() -> bool:

    clear_settings_cache()

    s = Settings()

    return bool(

        s.tiflux_api_token.strip()

        and s.vhsys_access_token.strip()

        and s.vhsys_secret_access_token.strip()

    )





@pytest.mark.asyncio

async def test_brasilapi_fetch_smoke():

    clear_settings_cache()

    settings = Settings()

    assert validate_cnpj(SMOKE_CNPJ)

    data = await fetch_cnpj(SMOKE_CNPJ, settings)

    company = from_brasilapi(data)

    assert company.legal_name

    assert company.cnpj_digits == SMOKE_CNPJ





@pytest.mark.asyncio

async def test_integrate_target_cnpj_both_systems():

    """@tester — CNPJ 65.074.067/0001-16 deve constar em TiFlux e VHSYS."""

    if not _has_tokens():

        pytest.skip("Tokens não configurados no .env")



    from src.integrations.tiflux_client import TifluxClient

    from src.integrations.vhsys_client import VhsysClient

    from src.orchestrator import integrate_cnpj



    clear_settings_cache()

    settings = Settings()

    assert settings.vhsys_base_url.rstrip("/") == "https://api.vhsys.com/v2"



    result = await integrate_cnpj(TARGET_CNPJ, settings)



    assert result.company is not None

    assert result.company.cnpj_digits == TARGET_CNPJ

    assert result.tiflux.success, result.tiflux.error or result.tiflux.message

    assert result.vhsys.success, result.vhsys.error or result.vhsys.message

    assert result.success is True

    assert result.partial is False



    tiflux_found = await TifluxClient(settings).find_by_cnpj(TARGET_CNPJ)

    assert tiflux_found is not None, (

        "Cliente não encontrado no TiFlux via API após integração (falso positivo)."

    )

    assert tiflux_found.get("id"), "Resposta TiFlux sem id de cliente."



    vhsys_found = await VhsysClient(settings).find_by_cnpj(result.company.cnpj_formatted)

    assert vhsys_found is not None, "Cliente não encontrado no VHSYS via API após integração."

    assert vhsys_found.get("id_cliente"), "Resposta VHSYS sem id_cliente."


