from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.stats import _STATS_CACHE, compute_stats


@pytest.fixture(autouse=True)
def clear_stats_cache():
    _STATS_CACHE.clear()
    yield
    _STATS_CACHE.clear()


@pytest.mark.asyncio
async def test_compute_stats_aggregates_counts():
    cutoff_recent = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S")
    cutoff_old = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S")

    async def fake_iter(*, max_clients: int = 1500):
        clients = [
            {"id": 1, "created_at": cutoff_recent},
            {"id": 2, "created_at": cutoff_old},
            {"id": 3},
        ]
        for c in clients[:max_clients]:
            yield c

    with (
        patch("src.stats._ensure_credentials"),
        patch("src.stats.TifluxClient") as mock_tf_cls,
        patch("src.stats.VhsysClient") as mock_vh_cls,
        patch("src.stats._schedule_dormant_warm") as mock_warm,
    ):
        mock_tf_cls.return_value.iter_active_clients = fake_iter

        async def fake_list(params):
            if params.get("lixeira") == "Nao":
                return [{"id_cliente": 1}, {"id_cliente": 2}]
            return [{"id_cliente": 10, "data_modificacao": cutoff_recent}]

        mock_vh_cls.return_value._list_clientes = AsyncMock(side_effect=fake_list)

        result = await compute_stats(MagicMock())

    assert result["tiflux_total"] == 3
    assert result["registered_30d"] == 1
    assert result["vhsys_total"] == 2
    assert result["inactivated_30d"] == 1
    assert result["tiflux_dormant"] is None
    assert result["dormant_status"] == "pending"
    assert result["success"] is True
    mock_warm.assert_called_once()

    cached = await compute_stats(MagicMock())
    assert cached == result
