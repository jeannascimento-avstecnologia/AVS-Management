"""Rotas `/faturamento/*` — CRUD fila + approve/prefeitura (F1.1) + lista TiFlux (F1 lista)."""

from __future__ import annotations

import calendar
import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError

from src.auth.audit import log_action
from src.auth.deps import require_permission
from src.auth.permissions import PERMISSION_APROVAR_FATURA, PERMISSION_FATURAR
from src.billing.schemas import (
    BillingArtifactWrite,
    BillingPrefeituraInput,
    BillingRunUpdate,
    BillingRunWrite,
)
from src.billing.service import (
    BillingConflictError,
    BillingNotFoundError,
    BillingService,
)
from src.cnpj.validator import normalize_cnpj
from src.config import get_settings
from src.hub.outbox import dispatch_outbox, get_outbox_row
from src.hub.store import get_hub_db
from src.integrations.tiflux_client import TifluxApiError, TifluxClient

_COMPETENCE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DAY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_BILLING_TYPES = frozenset({"billed", "reversed", "paid"})


def _user_id(user: dict[str, Any]) -> int | None:
    raw = user.get("id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _service() -> BillingService:
    return BillingService(get_hub_db())


def _parse_money(raw: object) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace("R$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_tiflux_client(row: dict) -> dict[str, Any] | None:
    raw_id = row.get("id")
    try:
        client_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    name = str(row.get("name") or row.get("social") or "").strip()
    cnpj_digits = normalize_cnpj(str(row.get("social_revenue") or ""))
    return {
        "id": client_id,
        "name": name or f"Cliente #{client_id}",
        "cnpj": cnpj_digits if len(cnpj_digits) == 14 else None,
    }


def _normalize_tiflux_contract(row: dict) -> dict[str, Any] | None:
    raw_id = row.get("id")
    try:
        contract_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    name = str(row.get("name") or "").strip() or f"Contrato #{contract_id}"
    amount = _parse_money(row.get("total_value") or row.get("rider_value"))
    client_raw = row.get("client") if isinstance(row.get("client"), dict) else {}
    client_id: int | None = None
    client_name: str | None = None
    if client_raw:
        try:
            client_id = int(client_raw["id"]) if client_raw.get("id") is not None else None
        except (TypeError, ValueError):
            client_id = None
        client_name = str(client_raw.get("name") or "").strip() or None
    return {
        "id": contract_id,
        "name": name,
        "amount": amount,
        "status": str(row.get("status") or ""),
        "external_ref": str(contract_id),
        "client_id": client_id,
        "client_name": client_name,
        "modality": str(row.get("modality") or "") or None,
        "expiration_date": row.get("expiration_date"),
        "readjustment_date": row.get("readjustment_date"),
    }


def _normalize_tiflux_billing_history(row: dict) -> dict[str, Any] | None:
    raw_id = row.get("billing_id")
    if raw_id is None:
        return None
    try:
        billing_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    client_id: int | None = None
    if row.get("client_id") is not None:
        try:
            client_id = int(row["client_id"])
        except (TypeError, ValueError):
            client_id = None
    return {
        "billing_id": billing_id,
        "billing_date": str(row.get("billing_date") or "") or None,
        "due_date": str(row.get("due_date") or "") or None,
        "client_id": client_id,
        "client_name": str(row.get("client_name") or "").strip() or None,
        "real_value": _parse_money(row.get("real_value")),
        "nfe_number": row.get("nfe_number"),
        "paid": bool(row.get("paid")),
        "reversal": bool(row.get("reversal")),
    }


def _competence_range(competence: str) -> tuple[str, str]:
    year_s, month_s = competence.split("-", 1)
    year, month = int(year_s), int(month_s)
    last = calendar.monthrange(year, month)[1]
    return f"{competence}-01", f"{competence}-{last:02d}"


def _resolve_billing_date_range(
    *,
    billing_day: str | None,
    competence: str | None,
) -> tuple[str | None, str | None]:
    if billing_day:
        if not _DAY_RE.match(billing_day):
            raise HTTPException(
                status_code=422,
                detail="billing_day deve ser YYYY-MM-DD.",
            )
        return billing_day, billing_day
    if competence:
        if not _COMPETENCE_RE.match(competence):
            raise HTTPException(
                status_code=422,
                detail="competence deve ser YYYY-MM.",
            )
        return _competence_range(competence)
    return None, None


def _local_run_ids_by_client(
    competence: str | None,
) -> dict[int, int]:
    """Mapa tiflux_client_id → billing_run.id para a competência (primeiro match)."""
    if not competence or not _COMPETENCE_RE.match(competence):
        return {}
    runs = _service().list(competence=competence, limit=500, offset=0)
    out: dict[int, int] = {}
    for run in runs:
        if run.tiflux_client_id is None:
            continue
        cid = int(run.tiflux_client_id)
        if cid not in out:
            out[cid] = int(run.id)
    return out


def build_billing_router() -> APIRouter:
    router = APIRouter(prefix="/faturamento", tags=["faturamento"])

    @router.get("/tiflux/clients")
    async def search_tiflux_clients(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=20, ge=1, le=50),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        """Autocomplete clientes TiFlux (CNPJ ou nome) para montar fila."""
        settings = get_settings()
        if not settings.tiflux_api_token:
            raise HTTPException(status_code=503, detail="Credenciais TiFlux não configuradas.")
        term = q.strip()
        if len(term) < 2:
            return {"clients": [], "query": term}
        client = TifluxClient(settings)
        try:
            digits = normalize_cnpj(term)
            if len(digits) >= 11:
                raw = await client.find_matches_by_cnpj(digits, limit=limit)
            else:
                raw = await client.find_by_name(term, limit=limit)
        except TifluxApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        clients = [c for c in (_normalize_tiflux_client(r) for r in raw) if c is not None]
        return {"clients": clients[:limit], "query": term}

    @router.get("/tiflux/clients/{client_id}/contracts")
    async def list_tiflux_client_contracts(
        client_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        """Contratos ativos do cliente TiFlux → itens sugeridos da fila."""
        settings = get_settings()
        if not settings.tiflux_api_token:
            raise HTTPException(status_code=503, detail="Credenciais TiFlux não configuradas.")
        try:
            raw = await TifluxClient(settings).list_contracts(
                client_id=client_id,
                status="actives",
                limit=100,
            )
        except TifluxApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        contracts = [c for c in (_normalize_tiflux_contract(r) for r in raw) if c is not None]
        return {"contracts": contracts, "client_id": client_id, "count": len(contracts)}

    @router.get("/tiflux/history")
    async def list_tiflux_billing_history(
        billing_day: str | None = Query(
            default=None,
            description="Dia único YYYY-MM-DD (billing_start=end).",
        ),
        competence: str | None = Query(
            default=None,
            description="Competência YYYY-MM → range do mês (ignorado se billing_day).",
        ),
        client_id: int | None = Query(default=None, ge=1),
        billing_type: Literal["billed", "reversed", "paid"] | None = Query(default=None),
        due_start_date: str | None = Query(default=None),
        due_end_date: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=1, ge=1),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        """
        Proxy GET /reports/billings/history.
        Pending/faturar = No-Go; lista inicial usa histórico + filtros OpenAPI.
        """
        settings = get_settings()
        if not settings.tiflux_api_token:
            raise HTTPException(status_code=503, detail="Credenciais TiFlux não configuradas.")
        start, end = _resolve_billing_date_range(
            billing_day=billing_day,
            competence=competence,
        )
        if billing_type is not None and billing_type not in _BILLING_TYPES:
            raise HTTPException(status_code=422, detail="billing_type inválido.")
        try:
            raw = await TifluxClient(settings).list_billing_history(
                client_id=client_id,
                billing_start_date=start,
                billing_end_date=end,
                due_start_date=due_start_date,
                due_end_date=due_end_date,
                billing_type=billing_type,
                limit=limit,
                offset=offset,
            )
        except TifluxApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        items = [h for h in (_normalize_tiflux_billing_history(r) for r in raw) if h is not None]
        local_map = _local_run_ids_by_client(competence)
        for item in items:
            cid = item.get("client_id")
            item["local_run_id"] = local_map.get(int(cid)) if cid is not None else None

        return {
            "items": items,
            "count": len(items),
            "filters": {
                "billing_day": billing_day,
                "competence": competence,
                "billing_start_date": start,
                "billing_end_date": end,
                "client_id": client_id,
                "billing_type": billing_type,
                "due_start_date": due_start_date,
                "due_end_date": due_end_date,
                "limit": limit,
                "offset": offset,
            },
            "source": "tiflux_reports_billings_history",
            "note": (
                "API TiFlux sem pending/faturar (404). "
                "Lista = histórico; fila local = billing_runs."
            ),
        }

    @router.get("/tiflux/contracts")
    async def list_tiflux_contracts(
        client_id: int | None = Query(default=None, ge=1),
        status: str = Query(default="actives"),
        competence: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=200),
        offset: int = Query(default=1, ge=1),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        """Lista contratos TiFlux (opcionalmente por cliente) para montar fila."""
        settings = get_settings()
        if not settings.tiflux_api_token:
            raise HTTPException(status_code=503, detail="Credenciais TiFlux não configuradas.")
        if competence and not _COMPETENCE_RE.match(competence):
            raise HTTPException(status_code=422, detail="competence deve ser YYYY-MM.")
        try:
            raw = await TifluxClient(settings).list_contracts(
                client_id=client_id,
                status=status or "actives",
                limit=limit,
                offset=offset,
            )
        except TifluxApiError as exc:
            status_code = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            raise HTTPException(status_code=status_code, detail=str(exc)) from exc

        contracts = [c for c in (_normalize_tiflux_contract(r) for r in raw) if c is not None]
        local_map = _local_run_ids_by_client(competence)
        for contract in contracts:
            cid = contract.get("client_id")
            contract["local_run_id"] = (
                local_map.get(int(cid)) if cid is not None else None
            )

        return {
            "contracts": contracts,
            "count": len(contracts),
            "client_id": client_id,
            "status": status or "actives",
            "competence": competence,
        }

    @router.get("/runs")
    async def list_runs(
        status: str | None = Query(default=None),
        competence: str | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        runs = _service().list(
            status=status,
            competence=competence,
            limit=limit,
            offset=offset,
        )
        return {"runs": [r.model_dump() for r in runs]}

    @router.post("/runs", status_code=201)
    async def create_run(
        request: Request,
        body: BillingRunWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        try:
            run = _service().create(body, created_by=_user_id(user))
        except BillingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="faturamento.create",
            resource=str(run.id),
            detail={
                "status": run.status,
                "cnpj": run.cnpj,
                "competence": run.competence,
            },
            user=user,
        )
        return run.model_dump()

    @router.get("/runs/{run_id}")
    async def get_run(
        run_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        try:
            run = _service().get(run_id)
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return run.model_dump()

    @router.put("/runs/{run_id}")
    async def update_run(
        request: Request,
        run_id: int,
        body: BillingRunUpdate,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        try:
            run = _service().update(run_id, body)
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BillingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        log_action(
            request,
            action="faturamento.update",
            resource=str(run.id),
            detail={"status": run.status},
            user=user,
        )
        return run.model_dump()

    @router.delete("/runs/{run_id}", status_code=204)
    async def delete_run(
        request: Request,
        run_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> None:
        try:
            _service().delete(run_id)
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BillingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="faturamento.delete",
            resource=str(run_id),
            detail={},
            user=user,
        )

    @router.post("/runs/{run_id}/artifacts", status_code=201)
    async def add_artifact(
        request: Request,
        run_id: int,
        body: BillingArtifactWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> dict[str, Any]:
        try:
            artifact = _service().add_artifact(run_id, body)
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="faturamento.artifact.create",
            resource=f"run:{run_id}",
            detail={"artifact_id": artifact.id, "kind": artifact.kind},
            user=user,
        )
        return artifact.model_dump()

    @router.delete("/runs/{run_id}/artifacts/{artifact_id}", status_code=204)
    async def delete_artifact(
        request: Request,
        run_id: int,
        artifact_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_FATURAR)),
    ) -> None:
        try:
            _service().delete_artifact(run_id, artifact_id)
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="faturamento.artifact.delete",
            resource=f"run:{run_id}",
            detail={"artifact_id": artifact_id},
            user=user,
        )

    @router.post("/runs/{run_id}/approve", status_code=202)
    async def approve_run(
        request: Request,
        run_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_APROVAR_FATURA)),
    ) -> dict[str, Any]:
        """
        Sem retenção: draft→approved + outbox billing.approved (dry-run skip HTTP).
        Com retenção: draft→awaiting_prefeitura (sem outbox).
        """
        settings = get_settings()
        svc = _service()
        try:
            result, outbox_id = svc.approve(
                run_id,
                approved_by=_user_id(user),
                settings=settings,
            )
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BillingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        final_status: str | None = None
        if outbox_id is not None:
            outbox_status = await dispatch_outbox(
                get_hub_db(), outbox_id, settings=settings
            )
            row = get_outbox_row(get_hub_db(), outbox_id)
            final_status = str(row["status"]) if row else outbox_status

        log_action(
            request,
            action="billing.approve",
            resource=f"billing_run:{run_id}",
            detail={
                "status": result.run.status,
                "outbox_id": outbox_id,
                "outbox_status": final_status,
                "dry_run": settings.hub_dry_run,
                "has_retencao": result.run.has_retencao,
            },
            user=user,
        )
        payload = result.to_dict()
        if outbox_id is not None:
            payload["outbox_status"] = final_status
        return payload

    @router.post("/runs/{run_id}/prefeitura", status_code=202)
    async def prefeitura_run(
        request: Request,
        run_id: int,
        body: BillingPrefeituraInput,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_APROVAR_FATURA)),
    ) -> dict[str, Any]:
        """awaiting_prefeitura → approved + outbox billing.nf_prefeitura."""
        settings = get_settings()
        svc = _service()
        try:
            result, outbox_id = svc.submit_prefeitura(
                run_id,
                body,
                approved_by=_user_id(user),
                settings=settings,
            )
        except BillingNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except BillingConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        outbox_status = await dispatch_outbox(
            get_hub_db(), outbox_id, settings=settings
        )
        row = get_outbox_row(get_hub_db(), outbox_id)
        final_status = str(row["status"]) if row else outbox_status

        log_action(
            request,
            action="billing.nf_prefeitura",
            resource=f"billing_run:{run_id}",
            detail={
                "outbox_id": outbox_id,
                "outbox_status": final_status,
                "dry_run": settings.hub_dry_run,
                "nf_prefeitura_number": body.nf_prefeitura_number,
            },
            user=user,
        )
        payload = result.to_dict()
        payload["outbox_status"] = final_status
        return payload

    return router
