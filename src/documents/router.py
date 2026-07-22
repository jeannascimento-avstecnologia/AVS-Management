"""API GET /documentos — busca orçamentos, PDFs e faturamentos."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from src.auth.deps import require_any_permission, user_has_permission
from src.auth.permissions import PERMISSION_FATURAR, PERMISSION_ORCAMENTOS
from src.documents.service import DocumentsService
from src.hub.store import get_hub_db


def _service() -> DocumentsService:
    return DocumentsService(get_hub_db())


def _perm_flags(user: dict[str, Any]) -> tuple[bool, bool]:
    include_quotes = user_has_permission(user, PERMISSION_ORCAMENTOS)
    include_billing = user_has_permission(user, PERMISSION_FATURAR)
    if not include_quotes and not include_billing:
        raise HTTPException(status_code=403, detail="Sem permissão para esta operação.")
    return include_quotes, include_billing


def build_documents_router() -> APIRouter:
    router = APIRouter(prefix="/documentos", tags=["documentos"])

    @router.get("/recent")
    async def recent_documents(
        limit: int = Query(default=50, ge=1, le=100),
        user: dict[str, Any] = Depends(
            require_any_permission(PERMISSION_ORCAMENTOS, PERMISSION_FATURAR)
        ),
    ) -> dict[str, Any]:
        include_quotes, include_billing = _perm_flags(user)
        result = _service().list_recent(
            include_quotes=include_quotes,
            include_billing=include_billing,
            limit=limit,
        )
        return result.model_dump()

    @router.get("")
    async def search_documents(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=50, ge=1, le=100),
        user: dict[str, Any] = Depends(
            require_any_permission(PERMISSION_ORCAMENTOS, PERMISSION_FATURAR)
        ),
    ) -> dict[str, Any]:
        term = q.strip()
        if not term:
            raise HTTPException(status_code=422, detail="Informe q (empresa ou ordem).")

        include_quotes, include_billing = _perm_flags(user)
        result = await _service().search(
            term,
            include_quotes=include_quotes,
            include_billing=include_billing,
            limit=limit,
            enrich=True,
        )
        return result.model_dump()

    return router
