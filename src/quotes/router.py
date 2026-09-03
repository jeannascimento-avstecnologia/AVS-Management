from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from src.auth.audit import log_action
from src.auth.deps import require_permission
from src.auth.permissions import PERMISSION_APROVAR_ORCAMENTO, PERMISSION_ORCAMENTOS
from src.cnpj.validator import normalize_cnpj
from src.config import get_settings
from src.hub.outbox import dispatch_outbox, get_outbox_row
from src.hub.store import get_hub_db
from src.integrations.tiflux_client import TifluxApiError, TifluxClient
from src.integrations.vhsys_client import VhsysApiError, VhsysClient, normalize_vhsys_party
from src.quotes.schemas import (
    LeadTemperature,
    QuoteModuleTemplateUpdate,
    QuoteModuleTemplateWrite,
    QuoteProposalTemplateUpdate,
    QuoteProposalTemplateWrite,
    QuoteStatus,
    QuoteTemplateUpdate,
    QuoteTemplateWrite,
    QuoteUpdate,
    QuoteWrite,
    QuoteMonthlyDraftWrite,
    QuoteMonthlySuggestBody,
    VhsysCatalogCreateBody,
)
from src.quotes.service import (
    QuoteConflictError,
    QuoteNotFoundError,
    QuoteService,
    build_monthly_suggestion,
)


def _user_id(user: dict[str, Any]) -> int | None:
    raw = user.get("id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _service() -> QuoteService:
    return QuoteService(get_hub_db())


def _technician_name(quote: Any, user: dict[str, Any]) -> str:
    created_by = getattr(quote, "created_by", None)
    if created_by is not None:
        try:
            from src.auth.store import get_auth_db

            db_user = get_auth_db().get_user_by_id(int(created_by))
            if db_user and (db_user.name or "").strip():
                return db_user.name.strip()
        except Exception:
            pass
    name = str(user.get("name") or "").strip()
    return name or "-"


def _normalize_tiflux_quote_client(row: dict) -> dict[str, Any] | None:
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


def build_quotes_router() -> APIRouter:
    router = APIRouter(prefix="/orcamentos", tags=["orcamentos"])

    @router.get("/templates")
    async def list_templates(
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        templates = _service().list_templates()
        return {"templates": [t.model_dump() for t in templates]}

    @router.post("/templates", status_code=201)
    async def create_template(
        request: Request,
        body: QuoteTemplateWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            template = _service().create_template(body)
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.template.create",
            resource=str(template.id),
            detail={"key": template.key, "section": template.section},
            user=user,
        )
        return template.model_dump()

    @router.put("/templates/{template_id}")
    async def update_template(
        request: Request,
        template_id: int,
        body: QuoteTemplateUpdate,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            template = _service().update_template(template_id, body)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.template.update",
            resource=str(template.id),
            detail={"key": template.key, "section": template.section},
            user=user,
        )
        return template.model_dump()

    @router.delete("/templates/{template_id}", status_code=204)
    async def delete_template(
        request: Request,
        template_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> None:
        try:
            _service().delete_template(template_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.template.delete",
            resource=str(template_id),
            detail={},
            user=user,
        )

    @router.get("/module-templates")
    async def list_module_templates(
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        templates = _service().list_module_templates()
        return {"templates": [t.model_dump() for t in templates]}

    @router.post("/module-templates", status_code=201)
    async def create_module_template(
        request: Request,
        body: QuoteModuleTemplateWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            template = _service().create_module_template(body)
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.module_template.create",
            resource=str(template.id),
            detail={"key": template.key},
            user=user,
        )
        return template.model_dump()

    @router.patch("/module-templates/{template_id}")
    async def update_module_template(
        request: Request,
        template_id: int,
        body: QuoteModuleTemplateUpdate,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            template = _service().update_module_template(template_id, body)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.module_template.update",
            resource=str(template.id),
            detail={"key": template.key},
            user=user,
        )
        return template.model_dump()

    @router.delete("/module-templates/{template_id}", status_code=204)
    async def delete_module_template(
        request: Request,
        template_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> None:
        try:
            _service().delete_module_template(template_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.module_template.delete",
            resource=str(template_id),
            detail={},
            user=user,
        )

    @router.get("/proposal-templates")
    async def list_proposal_templates(
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        templates = _service().list_proposal_templates()
        return {"templates": [t.model_dump() for t in templates]}

    @router.post("/proposal-templates", status_code=201)
    async def create_proposal_template(
        request: Request,
        body: QuoteProposalTemplateWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        template = _service().create_proposal_template(body)
        log_action(
            request,
            action="orcamento.proposal_template.create",
            resource=str(template.id),
            detail={"name": template.name},
            user=user,
        )
        return template.model_dump()

    @router.patch("/proposal-templates/{template_id}")
    async def update_proposal_template(
        request: Request,
        template_id: int,
        body: QuoteProposalTemplateUpdate,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            template = _service().update_proposal_template(template_id, body)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.proposal_template.update",
            resource=str(template.id),
            detail={"name": template.name},
            user=user,
        )
        return template.model_dump()

    @router.delete("/proposal-templates/{template_id}", status_code=204)
    async def delete_proposal_template(
        request: Request,
        template_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> None:
        try:
            _service().delete_proposal_template(template_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.proposal_template.delete",
            resource=str(template_id),
            detail={},
            user=user,
        )

    @router.get("/tiflux/clients")
    async def search_tiflux_clients(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=20, ge=1, le=50),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Autocomplete clientes TiFlux (CNPJ ou nome) para o passo Cliente do wizard."""
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
        clients = [c for c in (_normalize_tiflux_quote_client(r) for r in raw) if c is not None]
        return {"clients": clients[:limit], "query": term}

    @router.get("/tiflux/clients/{client_id}")
    async def get_tiflux_client_contact(
        client_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """E-mail do cliente TiFlux (contacts) — prefill do campo Para no envio."""
        from src.quotes.pdf_parties import _pick_email

        settings = get_settings()
        if not settings.tiflux_api_token:
            raise HTTPException(status_code=503, detail="Credenciais TiFlux não configuradas.")
        client = TifluxClient(settings)
        try:
            detail = await client.get_by_id(client_id, show_entities=False)
            contacts = await client.get_client_contacts(client_id)
        except TifluxApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        if not detail:
            raise HTTPException(status_code=404, detail="Cliente TiFlux não encontrado.")
        name = str(detail.get("name") or detail.get("social") or "").strip() or None
        email = _pick_email(contacts if isinstance(contacts, list) else []) or None
        # Fallback: campos diretos no cadastro do cliente
        if not email:
            for key in ("email", "email_financial", "email_commercial"):
                raw = str(detail.get(key) or "").strip()
                if raw:
                    email = raw
                    break
        return {"id": client_id, "name": name, "email": email}

    @router.get("/vhsys/categories")
    async def list_vhsys_categories(
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Categorias + subcategorias VHSYS — filtro do catálogo no wizard."""
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(
                status_code=503,
                detail="Credenciais VHSYS não configuradas.",
            )
        try:
            categories = await VhsysClient(settings).list_catalog_categories()
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return {"categories": categories, "count": len(categories)}

    @router.get("/vhsys/catalog")
    async def search_vhsys_catalog(
        q: str = Query(default="", max_length=200),
        limit: int = Query(
            default=0,
            ge=0,
            le=10_000,
            description="0 = catálogo completo (paginação VHSYS).",
        ),
        category_id: int | None = Query(default=None, ge=1),
        subcategory_id: int | None = Query(default=None, ge=1),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Autocomplete catálogo VHSYS. Default: puxa tudo (paginado no client VHSYS)."""
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(
                status_code=503,
                detail="Credenciais VHSYS não configuradas.",
            )
        try:
            items = await VhsysClient(settings).search_catalog_items(
                q,
                limit=limit,
                category_id=category_id,
                subcategory_id=subcategory_id,
            )
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return {
            "items": items,
            "query": q.strip(),
            "count": len(items),
            "category_id": category_id,
            "subcategory_id": subcategory_id,
        }

    @router.post("/vhsys/catalog")
    async def create_vhsys_catalog_item(
        request: Request,
        body: VhsysCatalogCreateBody,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Via dupla: find-or-create produto/serviço no VHSYS (POST /produtos se novo)."""
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(
                status_code=503,
                detail="Credenciais VHSYS não configuradas.",
            )
        try:
            item, created = await VhsysClient(settings).find_or_create_catalog_item(
                name=body.name,
                unit_value=body.unit_value,
                tipo_produto=body.tipo_produto,
                unidade_produto=body.unidade_produto,
                id_categoria=body.id_categoria,
                id_subcategoria=body.id_subcategoria,
            )
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            if status == 422:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc

        log_action(
            request,
            action="quotes.vhsys.catalog.create" if created else "quotes.vhsys.catalog.reuse",
            resource=f"vhsys_product:{item.get('id')}",
            detail={
                "name": item.get("name"),
                "created": created,
                "category_id": body.id_categoria,
                "subcategory_id": body.id_subcategoria,
            },
            user=user,
        )
        return {"item": item, "created": created}

    @router.get("/vhsys/parties")
    async def search_vhsys_parties(
        q: str = Query(default="", max_length=200),
        limit: int = Query(default=20, ge=1, le=50),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Autocomplete 'Faturado por' — clientes VHSYS por nome."""
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(
                status_code=503,
                detail="Credenciais VHSYS não configuradas.",
            )
        term = q.strip()
        if len(term) < 2:
            return {"parties": [], "query": term}
        try:
            raw = await VhsysClient(settings).find_matches_by_name(term, limit=limit)
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        parties = [p for p in (normalize_vhsys_party(r) for r in raw) if p is not None]
        return {"parties": parties[:limit], "query": term}

    @router.get("/vhsys/clients/{client_id}")
    async def get_vhsys_client_contact(
        client_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Contato do cliente VHSYS — e-mail sugerido para envio do orçamento."""
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(
                status_code=503,
                detail="Credenciais VHSYS não configuradas.",
            )
        try:
            row = await VhsysClient(settings).get_by_id(client_id)
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        if not row:
            raise HTTPException(status_code=404, detail="Cliente VHSYS não encontrado.")
        email = str(row.get("email_cliente") or "").strip() or None
        name = str(
            row.get("razao_cliente") or row.get("fantasia_cliente") or ""
        ).strip() or None
        return {
            "id": client_id,
            "name": name,
            "email": email,
        }

    @router.get("")
    async def list_quotes(
        status: QuoteStatus | None = Query(default=None),
        lead_temperature: LeadTemperature | None = Query(default=None),
        client: str | None = Query(default=None, max_length=300),
        number: str | None = Query(default=None, max_length=32),
        date_from: str | None = Query(default=None, max_length=10),
        date_to: str | None = Query(default=None, max_length=10),
        q: str | None = Query(default=None, max_length=200),
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        quotes = _service().list(
            status=status,
            lead_temperature=lead_temperature,
            client=client,
            number=number,
            date_from=date_from,
            date_to=date_to,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {"quotes": [q.model_dump() for q in quotes]}

    @router.post("", status_code=201)
    async def create_quote(
        request: Request,
        body: QuoteWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        quote = _service().create(body, created_by=_user_id(user))
        log_action(
            request,
            action="orcamento.create",
            resource=str(quote.id),
            detail={"status": quote.status, "cnpj": quote.cnpj},
            user=user,
        )
        return quote.model_dump()

    @router.get("/{quote_id}")
    async def get_quote(
        quote_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            quote = _service().get(quote_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return quote.model_dump()

    @router.put("/{quote_id}")
    async def update_quote(
        request: Request,
        quote_id: int,
        body: QuoteUpdate,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            quote = _service().update(quote_id, body)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        log_action(
            request,
            action="orcamento.update",
            resource=str(quote.id),
            detail={"status": quote.status},
            user=user,
        )
        return quote.model_dump()

    @router.delete("/{quote_id}", status_code=204)
    async def delete_quote(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> None:
        try:
            _service().delete(quote_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.delete",
            resource=str(quote_id),
            detail={},
            user=user,
        )

    @router.post("/{quote_id}/approve")
    async def approve_quote(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_APROVAR_ORCAMENTO)),
    ) -> dict[str, Any]:
        """Transição status→approved. Outbox quote.approved = O3 (não dispara aqui)."""
        try:
            before = _service().get(quote_id)
            quote = _service().approve(quote_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if before.status != quote.status:
            log_action(
                request,
                action="quote.approve",
                resource=f"quote:{quote.id}",
                detail={"from": before.status, "to": quote.status},
                user=user,
            )
        return quote.model_dump()

    @router.post("/{quote_id}/submit", status_code=202)
    async def submit_quote(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """draft→submitted + outbox quote.submit. Dry-run: sem POST externo."""
        settings = get_settings()
        svc = _service()
        try:
            result, outbox_id = svc.submit(quote_id, settings=settings)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        outbox_status = await dispatch_outbox(get_hub_db(), outbox_id, settings=settings)
        row = get_outbox_row(get_hub_db(), outbox_id)
        final_status = str(row["status"]) if row else outbox_status

        log_action(
            request,
            action="quote.submit",
            resource=f"quote:{quote_id}",
            detail={
                "outbox_id": outbox_id,
                "outbox_status": final_status,
                "dry_run": settings.hub_dry_run,
            },
            user=user,
        )
        payload = result.to_dict()
        payload["outbox_status"] = final_status
        return payload

    @router.post("/{quote_id}/mark-sent", status_code=202)
    async def mark_sent_quote(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """submitted→sent + outbox quote.sent (stage kanban via n8n)."""
        settings = get_settings()
        svc = _service()
        try:
            result, outbox_id = svc.mark_sent(quote_id, settings=settings)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        outbox_status = await dispatch_outbox(get_hub_db(), outbox_id, settings=settings)
        row = get_outbox_row(get_hub_db(), outbox_id)
        final_status = str(row["status"]) if row else outbox_status

        log_action(
            request,
            action="quote.sent",
            resource=f"quote:{quote_id}",
            detail={
                "outbox_id": outbox_id,
                "outbox_status": final_status,
                "dry_run": settings.hub_dry_run,
            },
            user=user,
        )
        payload = result.to_dict()
        payload["outbox_status"] = final_status
        return payload

    @router.post("/{quote_id}/mensalidades/sugerir")
    async def suggest_quote_monthly(
        quote_id: int,
        body: QuoteMonthlySuggestBody,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        settings = get_settings()
        if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
            raise HTTPException(status_code=503, detail="Credenciais VHSYS não configuradas.")
        try:
            quote = _service().get(quote_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        wanted = set(body.item_ids)
        items = [i for i in quote.items if i.id in wanted]
        if len(items) != len(wanted):
            raise HTTPException(
                status_code=404,
                detail="Mensalidades: alguns quote_items não pertencem ao orçamento.",
            )
        issuer_name = (settings.quote_issuer_name or "AVS TECNOLOGIA").strip() or "AVS TECNOLOGIA"
        vhsys = VhsysClient(settings)
        allocations = []
        try:
            for item in items:
                product = None
                if item.vhsys_product_id:
                    product = await vhsys.get_product(item.vhsys_product_id)
                if product is None and (item.name or "").strip():
                    found = await vhsys.search_catalog_items(item.name.strip(), limit=20)
                    needle = item.name.strip().casefold()
                    product = next(
                        (p for p in found if str(p.get("name") or "").strip().casefold() == needle),
                        None,
                    )
                alloc = build_monthly_suggestion(
                    item, product, intermediador_name=issuer_name
                )
                allocations.append(alloc.model_dump())
        except VhsysApiError as exc:
            status = exc.status_code if exc.status_code and exc.status_code >= 400 else 502
            if status == 401:
                raise HTTPException(status_code=502, detail="Tokens VHSYS inválidos.") from exc
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return {"allocations": allocations}

    @router.put("/{quote_id}/mensalidades", status_code=200)
    async def update_quote_monthly_draft(
        request: Request,
        quote_id: int,
        body: QuoteMonthlyDraftWrite,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        """Atualiza rascunho de mensalidades (validado) no quote (draft)."""
        try:
            updated = _service().update_monthly_draft(quote_id, body)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.mensalidades.draft.update",
            resource=str(quote_id),
            detail={"has_charges": True},
            user=user,
        )
        return updated.model_dump()

    @router.get("/{quote_id}/versions")
    async def list_quote_versions(
        quote_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        versions = _service().list_versions(quote_id)
        return {"versions": [v.model_dump() for v in versions]}

    @router.post("/{quote_id}/versions", status_code=201)
    async def create_quote_version(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> dict[str, Any]:
        try:
            created_by = _user_id(user)
            version = _service().create_version(quote_id, created_by=created_by)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.version.create",
            resource=str(quote_id),
            detail={"version_number": version.version_number},
            user=user,
        )
        return version.model_dump()

    @router.get("/{quote_id}/versions/{version_id}/pdf")
    async def download_quote_version_pdf(
        quote_id: int,
        version_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> FileResponse:
        try:
            version = _service().get_version(quote_id, version_id)
            path = _service().get_version_pdf_file(quote_id, version_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"orcamento-M{quote_id}-v{version.version_number}.pdf",
        )

    @router.post("/{quote_id}/pdf")
    async def generate_quote_pdf(
        request: Request,
        quote_id: int,
        user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> FileResponse:
        """Gera PDF local (UUID sob HUB_PDF_DIR) e devolve o arquivo."""
        from src.quotes.pdf_parties import resolve_pdf_parties

        try:
            quote = _service().get(quote_id)
            issuer, client = await resolve_pdf_parties(quote, get_settings())
            quote, path = _service().generate_pdf(
                quote_id,
                issuer=issuer,
                client=client,
                from_live=True,
                technician_name=_technician_name(quote, user),
            )
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except QuoteConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        log_action(
            request,
            action="orcamento.pdf",
            resource=str(quote.id),
            detail={"pdf_path": quote.pdf_path},
            user=user,
        )
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"orcamento-M{quote.id}.pdf",
        )

    @router.get("/{quote_id}/pdf")
    async def download_quote_pdf(
        quote_id: int,
        _user: dict[str, Any] = Depends(require_permission(PERMISSION_ORCAMENTOS)),
    ) -> FileResponse:
        """Baixa PDF já gerado. 404 se inexistente."""
        try:
            quote = _service().get(quote_id)
            path = _service().get_pdf_file(quote_id)
        except QuoteNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"orcamento-M{quote.id}.pdf",
        )

    return router
