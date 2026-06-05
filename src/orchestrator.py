import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.cnpj.brasilapi_client import BrasilApiError, fetch_cnpj
from src.cnpj.validator import normalize_cnpj, validate_cnpj
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

