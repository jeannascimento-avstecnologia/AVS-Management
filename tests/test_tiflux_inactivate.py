from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config import Settings, clear_settings_cache
from src.integrations.tiflux_client import TifluxClient


@pytest.fixture
def env():
    with patch.dict("os.environ", {"TIFLUX_API_TOKEN": "test-token"}):
        clear_settings_cache()
        yield
    clear_settings_cache()


@pytest.mark.asyncio
async def test_delete_client_uses_put_inactivate(env):
    client = TifluxClient(Settings())
    put_response = MagicMock(status_code=200, text="")

    mock_http = AsyncMock()
    mock_http.put = AsyncMock(return_value=put_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("src.integrations.tiflux_client.httpx.AsyncClient", return_value=mock_http):
        await client.delete_client(42)

    mock_http.put.assert_awaited_once()
    call = mock_http.put.await_args
    assert call.args[0].endswith("/clients/42")
    assert call.kwargs["json"] == {"status": False}
    mock_http.delete.assert_not_called()


@pytest.mark.asyncio
async def test_find_by_filter_uses_active_not_status(env):
    client = TifluxClient(Settings())
    get_response = MagicMock(
        status_code=200,
        text="",
        json=MagicMock(
            return_value=[
                {
                    "id": 7,
                    "name": "RTC",
                    "social": "RTC ACADEMIA LTDA",
                    "social_revenue": "50149208000145",
                    "status": True,
                }
            ]
        ),
    )

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=get_response)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with patch("src.integrations.tiflux_client.httpx.AsyncClient", return_value=mock_http):
        found = await client.find_by_cnpj("50149208000145")

    assert found is not None
    assert found["id"] == 7
    first_params = mock_http.get.await_args_list[0].kwargs["params"]
    assert "status" not in first_params
    assert first_params.get("social_revenue") in ("50149208000145", "50.149.208/0001-45")
