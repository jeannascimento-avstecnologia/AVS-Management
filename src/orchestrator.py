import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.cnpj.brasilapi_client import BrasilApiError, fetch_cnpj
from src.cnpj.validator import format_cnpj, normalize_cnpj, validate_cnpj
from src.config import Settings
from src.integrations.tiflux_client import (
    TifluxApiError,
    TifluxClient,
    is_duplicate_client_error,
)
from src.integrations.vhsys_client import VhsysApiError, VhsysClient
from src.debug_log import dbg
from src.mapping.canonical import (
    CompanyPayload,
    company_from_dict,
    company_to_dict,
    extract_registration_status,
    from_brasilapi,
)


@dataclass
class SystemResult:
    success: bool
    skipped: bool = False
    message: str = ""
    data: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class IntegrationResult:
    cnpj: str
    company: CompanyPayload | None = None
    tiflux: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    vhsys: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    partial: bool = False
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cnpj": self.cnpj,
            "success": self.success,
            "partial": self.partial,
            "company": company_to_dict(self.company) if self.company else None,
            "tiflux": _system_dict(self.tiflux),
            "vhsys": _system_dict(self.vhsys),
        }


@dataclass
@dataclass
class DeleteSystemPreview:
    found: bool
    matches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"found": self.found, "matches": self.matches}


@dataclass
class DeletePreviewResult:
    query: str
    search_mode: str
    tiflux: DeleteSystemPreview
    vhsys: DeleteSystemPreview

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "query": self.query,
            "search_mode": self.search_mode,
            "tiflux": self.tiflux.to_dict(),
            "vhsys": self.vhsys.to_dict(),
        }


@dataclass
class DeleteResult:
    query: str
    tiflux: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    vhsys: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    partial: bool = False
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "success": self.success,
            "partial": self.partial,
            "tiflux": _system_dict(self.tiflux),
            "vhsys": _system_dict(self.vhsys),
        }


@dataclass
class PreviewResult:
    company: CompanyPayload
    tiflux_options: dict[str, Any]
    duplicates: dict[str, bool]
    warnings: list[str] = field(default_factory=list)
    requires_inactive_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "company": company_to_dict(self.company),
            "tiflux_options": self.tiflux_options,
            "duplicates": self.duplicates,
            "warnings": self.warnings,
            "requires_inactive_override": self.requires_inactive_override,
        }


def _system_dict(result: SystemResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "skipped": result.skipped,
        "message": result.message,
        "error": result.error,
        "data": result.data,
    }


class OrchestratorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _ensure_credentials(settings: Settings) -> None:
    missing = []
    if not settings.tiflux_api_token.strip():
        missing.append("TIFLUX_API_TOKEN")
    if not settings.vhsys_access_token.strip():
        missing.append("VHSYS_ACCESS_TOKEN")
    if not settings.vhsys_secret_access_token.strip():
        missing.append("VHSYS_SECRET_ACCESS_TOKEN")
    if missing:
        raise OrchestratorError(
            f"Configure no .env: {', '.join(missing)}.",
            500,
        )


async def _fetch_company(raw_cnpj: str, settings: Settings) -> CompanyPayload:
    digits = normalize_cnpj(raw_cnpj)
    if not validate_cnpj(digits):
        raise OrchestratorError("CNPJ inválido.", 400)

    try:
        raw_data = await fetch_cnpj(digits, settings)
    except BrasilApiError as exc:
        raise OrchestratorError(str(exc), exc.status_code or 502) from exc

    return from_brasilapi(raw_data)


def _receita_is_active(company: CompanyPayload) -> bool:
    return company.registration_status.strip().upper() == "ATIVA"


async def _refresh_registration_status(company: CompanyPayload, settings: Settings) -> None:
    """Reconsulta a Receita na integração — não confia só no payload da UI."""
    raw_data = await fetch_cnpj(company.cnpj_digits, settings)
    company.registration_status = extract_registration_status(raw_data)


def _build_preview_warnings(company: CompanyPayload, settings: Settings) -> tuple[list[str], bool]:
    warnings: list[str] = []
    requires_override = False
    if company.registration_status and not _receita_is_active(company):
        warnings.append(
            f"Situação cadastral na Receita Federal: {company.registration_status}."
        )
        if settings.require_active_cnpj:
            warnings.append(
                "Para cadastrar, marque a autorização na etapa de revisão "
                "ou defina REQUIRE_ACTIVE_CNPJ=false no .env."
            )
            requires_override = True
    return warnings, requires_override


async def preview_cnpj(raw_cnpj: str, settings: Settings) -> PreviewResult:
    _ensure_credentials(settings)
    company = await _fetch_company(raw_cnpj, settings)

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)

    desks, groups = await asyncio.gather(
        tiflux.list_desks(),
        tiflux.list_technical_groups(),
    )

    existing_tf = None
    existing_vh = None
    try:
        existing_tf = await tiflux.find_by_cnpj(company.cnpj_digits)
        existing_vh = await vhsys.find_by_cnpj(company.cnpj_formatted)
    except (TifluxApiError, VhsysApiError) as exc:
        raise OrchestratorError(str(exc), getattr(exc, "status_code", None) or 502) from exc

    default_desks = [d["id"] for d in desks if d.get("active", True)]
    default_groups = [g["id"] for g in groups]

    warnings, requires_override = _build_preview_warnings(company, settings)

    return PreviewResult(
        company=company,
        tiflux_options={
            "desks": desks,
            "technical_groups": groups,
            "defaults": {
                "desk_ids": default_desks,
                "technical_group_ids": default_groups,
            },
        },
        duplicates={
            "tiflux": existing_tf is not None,
            "vhsys": existing_vh is not None,
        },
        warnings=warnings,
        requires_inactive_override=requires_override,
    )


async def integrate_company(
    company_data: dict[str, Any],
    desk_ids: list[int],
    technical_group_ids: list[int],
    settings: Settings,
    *,
    override_inactive_registration: bool = False,
) -> IntegrationResult:
    _ensure_credentials(settings)
    company = company_from_dict(company_data)

    if not validate_cnpj(company.cnpj_digits):
        raise OrchestratorError("CNPJ inválido.", 400)
    if not company.legal_name.strip():
        raise OrchestratorError("Razão social é obrigatória.", 400)
    if not company.trade_name.strip():
        company.trade_name = company.legal_name

    try:
        await _refresh_registration_status(company, settings)
    except BrasilApiError as exc:
        raise OrchestratorError(str(exc), exc.status_code or 502) from exc

    if (
        settings.require_active_cnpj
        and not _receita_is_active(company)
        and not override_inactive_registration
    ):
        situacao = company.registration_status or "INDETERMINADA"
        raise OrchestratorError(
            f"CNPJ com situação cadastral {situacao} na Receita Federal (BrasilAPI). "
            "Marque a autorização na revisão para prosseguir.",
            422,
        )

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)
    digits = company.cnpj_digits

    existing_tf = await tiflux.find_by_cnpj(digits)
    existing_vh = await vhsys.find_by_cnpj(company.cnpj_formatted)

    result = IntegrationResult(cnpj=company.cnpj_formatted, company=company)

    async def _tiflux_task() -> SystemResult:
        if existing_tf:
            return SystemResult(
                success=True,
                skipped=True,
                message="Cliente já cadastrado no TiFlux.",
                data=existing_tf,
            )
        try:
            data = await tiflux.create_client(
                company,
                desk_ids=desk_ids,
                technical_group_ids=technical_group_ids,
            )
            return SystemResult(success=True, message="Cliente criado no TiFlux.", data=data)
        except TifluxApiError as exc:
            if is_duplicate_client_error(exc):
                verified = await tiflux.find_by_cnpj(digits)
                if verified:
                    return SystemResult(
                        success=True,
                        skipped=True,
                        message="Cliente já cadastrado no TiFlux.",
                        data=verified,
                    )
                return SystemResult(
                    success=False,
                    error=(
                        "TiFlux rejeitou o CNPJ como duplicado, mas o cliente não foi "
                        "encontrado na API (registro órfão). Contate o suporte TiFlux."
                    ),
                    message="Falha no TiFlux.",
                )
            return SystemResult(success=False, error=str(exc), message="Falha no TiFlux.")

    async def _vhsys_task() -> SystemResult:
        if existing_vh:
            return SystemResult(
                success=True,
                skipped=True,
                message="Cliente já cadastrado no VHSYS.",
                data=existing_vh,
            )
        try:
            data = await vhsys.create_client(company)
            return SystemResult(success=True, message="Cliente criado no VHSYS.", data=data)
        except VhsysApiError as exc:
            return SystemResult(success=False, error=str(exc), message="Falha no VHSYS.")

    tf_res, vh_res = await asyncio.gather(_tiflux_task(), _vhsys_task())
    result.tiflux = tf_res
    result.vhsys = vh_res

    ok_count = int(tf_res.success) + int(vh_res.success)
    result.partial = ok_count == 1
    result.success = ok_count == 2

    return result


def _tiflux_match_summary(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "name": item.get("name") or "",
        "social": item.get("social") or "",
        "social_revenue": item.get("social_revenue") or "",
        "status": item.get("status"),
    }


def _vhsys_match_summary(item: dict) -> dict[str, Any]:
    return {
        "id": item.get("id_cliente"),
        "razao_cliente": item.get("razao_cliente") or "",
        "fantasia_cliente": item.get("fantasia_cliente") or "",
        "cnpj_cliente": item.get("cnpj_cliente") or "",
        "situacao_cliente": item.get("situacao_cliente") or "",
    }


def _resolve_delete_search(query: str) -> tuple[str, str]:
    raw = (query or "").strip()
    if not raw:
        raise OrchestratorError("Informe um CNPJ ou nome para buscar.", 400)
    digits = normalize_cnpj(raw)
    if len(digits) == 14 and validate_cnpj(digits):
        return "cnpj", digits
    if len(digits) == 14:
        raise OrchestratorError("CNPJ inválido.", 400)
    if len(raw) < 3:
        raise OrchestratorError("Informe ao menos 3 caracteres para busca por nome.", 400)
    return "name", raw


async def preview_delete_client(query: str, settings: Settings) -> DeletePreviewResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_delete_search(query)

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)

    async def _search_tiflux() -> list[dict]:
        if search_mode == "cnpj":
            return await tiflux.find_matches_by_cnpj(term, limit=10)
        return await tiflux.find_by_name(term, limit=10)

    async def _search_vhsys() -> list[dict]:
        if search_mode == "cnpj":
            return await vhsys.find_matches_by_cnpj(format_cnpj(term), limit=10)
        return await vhsys.find_by_name(term, limit=10)

    try:
        tf_items, vh_items = await asyncio.gather(_search_tiflux(), _search_vhsys())
    except (TifluxApiError, VhsysApiError) as exc:
        raise OrchestratorError(str(exc), getattr(exc, "status_code", None) or 502) from exc

    tf_matches = [_tiflux_match_summary(x) for x in tf_items if x.get("id") is not None]
    vh_matches = [_vhsys_match_summary(x) for x in vh_items if x.get("id_cliente") is not None]

    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    return DeletePreviewResult(
        query=display_query,
        search_mode=search_mode,
        tiflux=DeleteSystemPreview(found=bool(tf_matches), matches=tf_matches),
        vhsys=DeleteSystemPreview(found=bool(vh_matches), matches=vh_matches),
    )


async def execute_delete(
    query: str,
    settings: Settings,
    *,
    tiflux_client_id: int | None = None,
    vhsys_client_id: int | None = None,
) -> DeleteResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_delete_search(query)
    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    if tiflux_client_id is None and vhsys_client_id is None:
        raise OrchestratorError(
            "Selecione ao menos um cliente para excluir (TiFlux ou VHSYS).",
            400,
        )

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)
    result = DeleteResult(query=display_query)

    async def _tiflux_delete() -> SystemResult:
        if tiflux_client_id is None:
            return SystemResult(
                success=True,
                skipped=True,
                message="TiFlux não selecionado para exclusão.",
            )
        try:
            client_id = int(tiflux_client_id)
            if search_mode == "cnpj":
                client_id = await tiflux.resolve_client_id(client_id, cnpj_digits=term)
            await tiflux.delete_client(client_id)
            return SystemResult(
                success=True,
                message="Cliente inativado no TiFlux.",
                data={"id": client_id},
            )
        except TifluxApiError as exc:
            return SystemResult(success=False, error=str(exc), message="Falha no TiFlux.")

    async def _vhsys_delete() -> SystemResult:
        if vhsys_client_id is None:
            return SystemResult(
                success=True,
                skipped=True,
                message="VHSYS não selecionado para exclusão.",
            )
        try:
            data = await vhsys.delete_client(vhsys_client_id)
            return SystemResult(
                success=True,
                message="Cliente enviado à lixeira no VHSYS.",
                data=data,
            )
        except VhsysApiError as exc:
            return SystemResult(success=False, error=str(exc), message="Falha no VHSYS.")

    tf_res, vh_res = await asyncio.gather(_tiflux_delete(), _vhsys_delete())
    result.tiflux = tf_res
    result.vhsys = vh_res

    attempted = [
        r for r, selected in ((tf_res, tiflux_client_id is not None), (vh_res, vhsys_client_id is not None))
        if selected
    ]
    ok_count = sum(1 for r in attempted if r.success)
    result.success = bool(attempted) and ok_count == len(attempted)
    result.partial = bool(attempted) and 0 < ok_count < len(attempted)

    return result


async def integrate_cnpj(raw_cnpj: str, settings: Settings) -> IntegrationResult:
    """Fluxo legado: consulta + cadastro com mesas/grupos padrão da API."""
    preview = await preview_cnpj(raw_cnpj, settings)
    defaults = preview.tiflux_options.get("defaults") or {}
    return await integrate_company(
        company_to_dict(preview.company),
        desk_ids=defaults.get("desk_ids") or [],
        technical_group_ids=defaults.get("technical_group_ids") or [],
        settings=settings,
    )

