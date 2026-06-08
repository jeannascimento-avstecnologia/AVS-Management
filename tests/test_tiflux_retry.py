import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.tiflux_client import TifluxApiError, TifluxClient
from src.config import Settings


@pytest.mark.asyncio
async def test_get_with_retry_recovers_from_429():
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    ok = MagicMock(status_code=200, text="{}")
    rate = MagicMock(status_code=429, text="rate limit")

    http.get = AsyncMock(side_effect=[rate, ok])

    with patch("src.integrations.tiflux_client.asyncio.sleep", new_callable=AsyncMock):
        response = await client._get_with_retry(
            http,
            "https://example.com/clients",
            headers={},
            params=None,
            action="listar clientes TiFlux",
            max_retries=3,
        )

    assert response.status_code == 200
    assert http.get.await_count == 2


@pytest.mark.asyncio
async def test_get_with_retry_raises_after_exhausted_429():
    client = TifluxClient(Settings(tiflux_api_token="t"))
    http = AsyncMock()
    rate = MagicMock(status_code=429, text="rate limit")
    http.get = AsyncMock(return_value=rate)

    with patch("src.integrations.tiflux_client.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(TifluxApiError, match="Limite de requisições"):
            await client._get_with_retry(
                http,
                "https://example.com/clients",
                headers={},
                params=None,
                action="listar clientes TiFlux",
                max_retries=2,
            )
