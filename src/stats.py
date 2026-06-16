"""Agregação de métricas para o dashboard (cache em memória)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import Settings
from src.debug_log import dbg
from src.integrations.tiflux_client import TifluxClient
from src.integrations.vhsys_client import VhsysClient
from src.orchestrator import _ensure_credentials, _parse_iso_datetime, scan_dormant_clients

_STATS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
STATS_CACHE_TTL = 600
DORMANT_CACHE_TTL = 3600
_VHSYS_MAX_PAGES = 40

_CREATED_FIELDS = ("created_at", "created", "registration_date", "registered_at")
_UPDATED_FIELDS = (
    "data_modificacao",
    "data_atualizacao",
    "data_alteracao",
    "updated_at",
    "modified_at",
)

_dormant_warm_task: asyncio.Task[None] | None = None
_dormant_warm_lock = asyncio.Lock()


def _parse_client_date(client: dict[str, Any], fields: tuple[str, ...]) -> datetime | None:
    for field in fields:
        dt = _parse_iso_datetime(client.get(field))
        if dt is not None:
            return dt
    return None


def _read_dormant_cache() -> tuple[int | None, str]:
    now = time.time()
    cached = _STATS_CACHE.get("dormant")
    if cached is None:
        return None, "pending"
    ts, data = cached
    if now - ts >= DORMANT_CACHE_TTL:
        return None, "stale"
    return int(data["count"]), "ready"


async def _count_tiflux_clients(tiflux: TifluxClient) -> tuple[int, int]:
    total = 0
    registered_30d = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async for client in tiflux.iter_active_clients(max_clients=2000):
        total += 1
        created = _parse_client_date(client, _CREATED_FIELDS)
        if created is not None and created >= cutoff:
            registered_30d += 1

    return total, registered_30d


async def _paginate_vhsys(vhsys: VhsysClient, *, lixeira: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    offset = 0
    limit = 250
    page_num = 0

    while page_num < _VHSYS_MAX_PAGES:
        page = await vhsys._list_clientes({"lixeira": lixeira, "limit": limit, "offset": offset})
        dbg(
            "B",
            "stats.py:_paginate_vhsys",
            "vhsys_page",
            {
                "lixeira": lixeira,
                "offset": offset,
                "page_len": len(page),
                "total_so_far": len(items),
                "page_num": page_num,
            },
        )
        if not page:
            break

        added = 0
        for item in page:
            cid = item.get("id_cliente")
            if cid is None:
                continue
            key = int(cid)
            if key in seen_ids:
                continue
            seen_ids.add(key)
            items.append(item)
            added += 1

        if len(page) < limit:
            break
        if added == 0:
            dbg("B", "stats.py:_paginate_vhsys", "vhsys_offset_ignored", {"lixeira": lixeira, "offset": offset})
            break

        offset += limit
        page_num += 1

    return items


async def _count_vhsys_clients(vhsys: VhsysClient) -> tuple[int, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    active_items, trash_items = await asyncio.gather(
        _paginate_vhsys(vhsys, lixeira="Nao"),
        _paginate_vhsys(vhsys, lixeira="Sim"),
    )

    inactivated_30d = 0
    for item in trash_items:
        updated = _parse_client_date(item, _UPDATED_FIELDS)
        if updated is not None and updated >= cutoff:
            inactivated_30d += 1

    return len(active_items), inactivated_30d


async def _warm_dormant_cache(settings: Settings) -> None:
    async with _dormant_warm_lock:
        now = time.time()
        cached = _STATS_CACHE.get("dormant")
        if cached is not None and now - cached[0] < DORMANT_CACHE_TTL:
            return

        dbg("A", "stats.py:_warm_dormant_cache", "dormant_warm_start", {})
        try:
            result = await scan_dormant_clients(settings, months=24, limit=200)
            count = result.total
            _STATS_CACHE["dormant"] = (time.time(), {"count": count})
            _STATS_CACHE.pop("global", None)
            dbg("A", "stats.py:_warm_dormant_cache", "dormant_warm_done", {"count": count})
        except Exception as exc:
            dbg("A", "stats.py:_warm_dormant_cache", "dormant_warm_error", {"error": str(exc)})


def _schedule_dormant_warm(settings: Settings) -> None:
    global _dormant_warm_task
    if _dormant_warm_task is not None and not _dormant_warm_task.done():
        return
    _dormant_warm_task = asyncio.create_task(_warm_dormant_cache(settings))


async def compute_stats(settings: Settings, *, ttl: int = STATS_CACHE_TTL) -> dict[str, Any]:
    cache_key = "global"
    now = time.time()
    cached = _STATS_CACHE.get(cache_key)
    if cached is not None:
        ts, data = cached
        if now - ts < ttl:
            dbg("A", "stats.py:compute_stats", "cache_hit", {"age_s": int(now - ts)})
            merged = dict(data)
            dormant, dormant_status = _read_dormant_cache()
            merged["tiflux_dormant"] = dormant
            merged["dormant_status"] = dormant_status
            return merged

    dbg("A", "stats.py:compute_stats", "cache_miss_compute_start", {})
    _ensure_credentials(settings)

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)

    (tiflux_total, registered_30d), (vhsys_total, inactivated_30d) = await asyncio.gather(
        _count_tiflux_clients(tiflux),
        _count_vhsys_clients(vhsys),
    )

    tiflux_dormant, dormant_status = _read_dormant_cache()
    if dormant_status == "pending":
        _schedule_dormant_warm(settings)

    computed_at = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "success": True,
        "tiflux_total": tiflux_total,
        "vhsys_total": vhsys_total,
        "registered_30d": registered_30d,
        "inactivated_30d": inactivated_30d,
        "inactivated_30d_source": "vhsys_lixeira",
        "tiflux_dormant": tiflux_dormant,
        "dormant_status": dormant_status,
        "computed_at": computed_at,
        "stale_after_seconds": ttl,
    }

    dbg(
        "A",
        "stats.py:compute_stats",
        "compute_done",
        {
            "tiflux_total": tiflux_total,
            "vhsys_total": vhsys_total,
            "registered_30d": registered_30d,
            "inactivated_30d": inactivated_30d,
            "tiflux_dormant": tiflux_dormant,
            "dormant_status": dormant_status,
        },
    )

    _STATS_CACHE[cache_key] = (now, payload)
    return payload
