from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.integrations.tiflux_client import TifluxClient


@pytest.mark.asyncio
async def test_get_last_billing_datetime_uses_billing_history():
    client = TifluxClient(Settings(tiflux_api_token="t"))
    payload = [
        {"billing_id": 1, "billing_date": "2024-08-22", "client_id": 23, "reversal": True},
        {"billing_id": 2, "billing_date": "2026-06-08", "client_id": 23, "reversal": False},
    ]
    mock_response = MagicMock(status_code=200, text="[]")
    mock_response.json.return_value = payload

    with patch.object(client, "_get_with_retry", new_callable=AsyncMock) as retry:
        retry.return_value = mock_response
        result = await client.get_last_billing_datetime(23)

    assert result == datetime(2026, 6, 8, tzinfo=timezone.utc)
    retry.assert_awaited_once()
    call_kwargs = retry.await_args.kwargs
    assert call_kwargs["params"]["client_id"] == 23
    assert "reports/billings/history" in retry.await_args.args[1]


@pytest.mark.asyncio
async def test_list_billing_history_passes_openapi_filters():
    client = TifluxClient(Settings(tiflux_api_token="t"))
    mock_response = MagicMock(status_code=200, text="[]")
    mock_response.json.return_value = [
        {"billing_id": 1, "billing_date": "2026-07-17", "client_id": 10}
    ]

    with patch.object(client, "_get_with_retry", new_callable=AsyncMock) as retry:
        retry.return_value = mock_response
        items = await client.list_billing_history(
            client_id=10,
            billing_start_date="2026-07-01",
            billing_end_date="2026-07-31",
            billing_type="billed",
            limit=50,
            offset=1,
        )

    assert len(items) == 1
    params = retry.await_args.kwargs["params"]
    assert params["client_id"] == 10
    assert params["billing_start_date"] == "2026-07-01"
    assert params["billing_end_date"] == "2026-07-31"
    assert params["_type"] == "billed"
    assert "reports/billings/history" in retry.await_args.args[1]
