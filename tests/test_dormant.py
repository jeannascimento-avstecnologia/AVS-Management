from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import clear_settings_cache
from src.orchestrator import scan_dormant_clients


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
async def test_scan_dormant_flags_no_ticket(env):
    from src.config import Settings

    old = datetime.now(timezone.utc) - timedelta(days=800)
    recent = datetime.now(timezone.utc) - timedelta(days=10)

    async def fake_iter(*, max_clients=1500, http=None):
        yield {"id": 1, "name": "A", "social": "A", "social_revenue": "123"}
        yield {"id": 2, "name": "B", "social": "B", "social_revenue": "456"}

    with patch("src.orchestrator.TifluxClient") as tf_cls:
        client = tf_cls.return_value
        client.iter_active_clients = fake_iter
        client.get_last_ticket_datetime = AsyncMock(side_effect=[None, recent])
        client.get_last_billing_datetime = AsyncMock(return_value=recent)

        result = await scan_dormant_clients(Settings(), months=24, limit=50)

    assert result.total == 1
    assert result.clients[0].id == 1
    assert "sem_ticket_24m" in result.clients[0].reasons


@pytest.mark.asyncio
async def test_scan_dormant_unlimited_collects_all_inactive(env):
    from src.config import Settings

    async def fake_iter(*, max_clients=1500, http=None):
        for i in range(1, 6):
            yield {
                "id": i,
                "name": f"C{i}",
                "social": f"C{i}",
                "social_revenue": f"{i:014d}",
            }

    with patch("src.orchestrator.TifluxClient") as tf_cls:
        client = tf_cls.return_value
        client.iter_active_clients = fake_iter
        client.get_last_ticket_datetime = AsyncMock(return_value=None)
        client.get_last_billing_datetime = AsyncMock(return_value=None)

        result = await scan_dormant_clients(Settings(), months=24, limit=0)

    assert result.total == 5
    assert result.truncated is False
    assert result.result_limit == 0
    assert result.scanned == 5


@pytest.mark.asyncio
async def test_scan_dormant_respects_result_limit(env):
    from src.config import Settings

    async def fake_iter(*, max_clients=1500, http=None):
        for i in range(1, 4):
            yield {
                "id": i,
                "name": f"C{i}",
                "social": f"C{i}",
                "social_revenue": f"{i:014d}",
            }

    with patch("src.orchestrator.TifluxClient") as tf_cls:
        client = tf_cls.return_value
        client.iter_active_clients = fake_iter
        client.get_last_ticket_datetime = AsyncMock(return_value=None)
        client.get_last_billing_datetime = AsyncMock(return_value=None)

        result = await scan_dormant_clients(Settings(), months=24, limit=2)

    assert result.total == 2
    assert result.truncated is True
    assert result.result_limit == 2
