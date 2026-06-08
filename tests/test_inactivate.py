from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import clear_settings_cache
from src.main import app
from src.orchestrator import execute_inactivate, preview_inactivate_client

client = TestClient(app)

ENV = {
    "TIFLUX_API_TOKEN": "t",
    "VHSYS_ACCESS_TOKEN": "a",
    "VHSYS_SECRET_ACCESS_TOKEN": "s",
    "AUTH_ENABLED": "false",
}


@pytest.fixture
def env():
    with patch.dict("os.environ", ENV):
        clear_settings_cache()
        yield
    clear_settings_cache()


@pytest.mark.asyncio
async def test_preview_inactivate_by_cnpj(env):
    from src.config import Settings

    tf_match = {"id": 10, "name": "Fantasia", "social": "Razao", "social_revenue": "19131243000197"}

    with patch("src.orchestrator.TifluxClient") as tf_cls:
        tf_cls.return_value.find_matches_by_cnpj = AsyncMock(return_value=[tf_match])

        result = await preview_inactivate_client("19.131.243/0001-97", Settings())

    assert result.search_mode == "cnpj"
    assert result.tiflux.found is True
    assert result.tiflux.matches[0]["id"] == 10


@pytest.mark.asyncio
async def test_execute_inactivate_tiflux(env):
    from src.config import Settings

    with patch("src.orchestrator.TifluxClient") as tf_cls:
        tf_cls.return_value.resolve_client_id = AsyncMock(return_value=10)
        tf_cls.return_value.delete_client = AsyncMock(return_value=None)

        result = await execute_inactivate(
            "19131243000197",
            Settings(),
            tiflux_client_id=10,
        )

    assert result.success is True
    assert result.tiflux.success is True
    assert "inativado" in result.tiflux.message


def test_inativar_preview_route_ok(env):
    with patch("src.main.preview_inactivate_client", new_callable=AsyncMock) as mock_preview:
        from src.orchestrator import DeleteSystemPreview, InactivatePreviewResult

        mock_preview.return_value = InactivatePreviewResult(
            query="test",
            search_mode="name",
            tiflux=DeleteSystemPreview(found=False),
        )
        res = client.post("/inativar/preview", json={"query": "Empresa X"})
    assert res.status_code == 200
    assert res.json()["success"] is True


def test_inativar_execute_requires_tiflux_id(env):
    res = client.post("/inativar", json={"query": "19131243000197"})
    assert res.status_code == 400
