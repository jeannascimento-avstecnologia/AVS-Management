from unittest.mock import patch

import pytest

from src.config import Settings, clear_settings_cache
from src.orchestrator import scan_dormant_clients

ENV = {
    "TIFLUX_API_TOKEN": "t",
    "VHSYS_ACCESS_TOKEN": "a",
    "VHSYS_SECRET_ACCESS_TOKEN": "s",
}


@pytest.mark.asyncio
async def test_scan_dormant_emits_progress(monkeypatch):
    events: list[dict] = []

    async def fake_iter(*, max_clients=1500):
        yield {"id": 1, "name": "A", "social": "Empresa A", "social_revenue": "123"}
        yield {"id": 2, "name": "B", "social": "Empresa B", "social_revenue": "456"}

    class FakeTiflux:
        async def iter_active_clients(self, *, max_clients=1500):
            async for item in fake_iter(max_clients=max_clients):
                yield item

        async def get_last_ticket_datetime(self, client_id: int):
            return None

        async def get_last_billing_datetime(self, client_id: int):
            return None

    monkeypatch.setattr("src.orchestrator.TifluxClient", lambda settings: FakeTiflux())
    async def _noop_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("src.orchestrator.asyncio.sleep", _noop_sleep)

    async def on_progress(payload: dict) -> None:
        events.append(payload)

    with patch.dict("os.environ", ENV):
        clear_settings_cache()
        result = await scan_dormant_clients(Settings(), months=24, limit=10, on_progress=on_progress)
    clear_settings_cache()

    assert result.total == 2
    assert events[0]["phase"] == "start"
    assert any(e.get("phase") == "billing" for e in events)
    assert events[-1]["found"] == 2
