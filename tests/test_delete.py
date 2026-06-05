from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.main import app
from src.orchestrator import execute_delete, preview_delete_client


client = TestClient(app)

ENV = {
    "TIFLUX_API_TOKEN": "t",
    "VHSYS_ACCESS_TOKEN": "a",
    "VHSYS_SECRET_ACCESS_TOKEN": "s",
}


@pytest.fixture
def env():
    with patch.dict("os.environ", ENV):
        clear_settings_cache()
        yield
    clear_settings_cache()


@pytest.mark.asyncio
async def test_preview_delete_by_cnpj(env):
    from src.config import Settings

    tf_match = {"id": 10, "name": "Fantasia", "social": "Razao", "social_revenue": "19131243000197"}
    vh_match = {"id_cliente": 20, "razao_cliente": "Razao", "fantasia_cliente": "Fan", "cnpj_cliente": "19.131.243/0001-97"}

    with patch("src.orchestrator.TifluxClient") as tf_cls, patch("src.orchestrator.VhsysClient") as vh_cls:
        tf_cls.return_value.find_matches_by_cnpj = AsyncMock(return_value=[tf_match])
        vh_cls.return_value.find_matches_by_cnpj = AsyncMock(return_value=[vh_match])

        result = await preview_delete_client("19.131.243/0001-97", Settings())

    assert result.search_mode == "cnpj"
    assert result.tiflux.found is True
    assert result.tiflux.matches[0]["id"] == 10
    assert result.vhsys.found is True
    assert result.vhsys.matches[0]["id"] == 20


@pytest.mark.asyncio
async def test_preview_delete_by_name(env):
    from src.config import Settings

    with patch("src.orchestrator.TifluxClient") as tf_cls, patch("src.orchestrator.VhsysClient") as vh_cls:
        tf_cls.return_value.find_by_name = AsyncMock(return_value=[{"id": 1, "name": "A", "social": "B", "social_revenue": ""}])
        vh_cls.return_value.find_by_name = AsyncMock(return_value=[])

        result = await preview_delete_client("Open Knowledge", Settings())

    assert result.search_mode == "name"
    assert result.tiflux.found is True
    assert result.vhsys.found is False


@pytest.mark.asyncio
async def test_execute_delete_tiflux_only(env):
    from src.config import Settings

    with patch("src.orchestrator.TifluxClient") as tf_cls, patch("src.orchestrator.VhsysClient") as vh_cls:
        tf_cls.return_value.resolve_client_id = AsyncMock(return_value=10)
        tf_cls.return_value.delete_client = AsyncMock(return_value=None)
        vh_cls.return_value.delete_client = AsyncMock()

        result = await execute_delete(
            "19131243000197",
            Settings(),
            tiflux_client_id=10,
            vhsys_client_id=None,
        )

    assert result.success is True
    assert result.tiflux.success is True
    assert "inativado" in result.tiflux.message
    assert result.vhsys.skipped is True
    vh_cls.return_value.delete_client.assert_not_called()


@pytest.mark.asyncio
async def test_execute_delete_partial_failure(env):
    from src.config import Settings
    from src.integrations.tiflux_client import TifluxApiError

    with patch("src.orchestrator.TifluxClient") as tf_cls, patch("src.orchestrator.VhsysClient") as vh_cls:
        tf_cls.return_value.resolve_client_id = AsyncMock(return_value=10)
        tf_cls.return_value.delete_client = AsyncMock(side_effect=TifluxApiError("negado", 403))
        vh_cls.return_value.delete_client = AsyncMock(return_value={"code": 200})

        result = await execute_delete(
            "19131243000197",
            Settings(),
            tiflux_client_id=10,
            vhsys_client_id=20,
        )

    assert result.success is False
    assert result.partial is True
    assert result.vhsys.success is True


def test_excluir_preview_route_missing_query(env):
    res = client.post("/excluir/preview", json={})
    assert res.status_code == 400


def test_excluir_preview_route_ok(env):
    with patch("src.main.preview_delete_client", new_callable=AsyncMock) as mock_preview:
        from src.orchestrator import DeletePreviewResult, DeleteSystemPreview

        mock_preview.return_value = DeletePreviewResult(
            query="test",
            search_mode="name",
            tiflux=DeleteSystemPreview(found=False),
            vhsys=DeleteSystemPreview(found=False),
        )
        res = client.post("/excluir/preview", json={"query": "Empresa X"})
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_index_has_excluir_menu(env):
    res = client.get("/")
    assert res.status_code == 200
    assert "Excluir Clientes" in res.text
    assert "menuExcluir" in res.text
