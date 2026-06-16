import asyncio
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.cnpj.brasilapi_client import BrasilApiError, fetch_cnpj
from src.cnpj.validator import format_cnpj, normalize_cnpj, validate_cnpj
from src.config import Settings
from src.debug_log import dbg
from src.integrations.tiflux_client import (
    TifluxApiError,
    TifluxClient,
    is_duplicate_client_error,
)
from src.integrations.vhsys_client import VhsysApiError, VhsysClient
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
    all_duplicates: bool = False
    duplicates: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cnpj": self.cnpj,
            "success": self.success,
            "partial": self.partial,
            "all_duplicates": self.all_duplicates,
            "duplicates": self.duplicates,
            "company": company_to_dict(self.company) if self.company else None,
            "tiflux": _system_dict(self.tiflux),
            "vhsys": _system_dict(self.vhsys),
        }


@dataclass
class DeleteSystemPreview:
    found: bool
    matches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"found": self.found, "matches": self.matches}


@dataclass
class InactivatePreviewResult:
    query: str
    search_mode: str
    tiflux: DeleteSystemPreview

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "query": self.query,
            "search_mode": self.search_mode,
            "tiflux": self.tiflux.to_dict(),
        }


# Alias legado
DeletePreviewResult = InactivatePreviewResult


@dataclass
class ConsultSystemPreview:
    found: bool
    matches_active: list[dict[str, Any]] = field(default_factory=list)
    matches_trash: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "matches_active": self.matches_active,
            "matches_trash": self.matches_trash,
        }


@dataclass
class ConsultPreviewResult:
    query: str
    search_mode: str
    tiflux: ConsultSystemPreview
    vhsys: ConsultSystemPreview

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "query": self.query,
            "search_mode": self.search_mode,
            "tiflux": self.tiflux.to_dict(),
            "vhsys": self.vhsys.to_dict(),
        }


@dataclass
class ConsultDetailResult:
    query: str
    tiflux: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    vhsys: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "query": self.query,
            "tiflux": _system_dict(self.tiflux),
            "vhsys": _system_dict(self.vhsys),
        }


@dataclass
class InactivateResult:
    query: str
    tiflux: SystemResult = field(default_factory=lambda: SystemResult(success=False))
    success: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "success": self.success,
            "tiflux": _system_dict(self.tiflux),
        }


DeleteResult = InactivateResult


@dataclass
class DormantClientEntry:
    id: int
    name: str
    social: str
    social_revenue: str
    last_ticket_at: str | None
    last_billing_at: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "social": self.social,
            "social_revenue": self.social_revenue,
            "last_ticket_at": self.last_ticket_at,
            "last_billing_at": self.last_billing_at,
            "reasons": self.reasons,
        }


@dataclass
class DormantScanResult:
    months: int
    scanned: int
    total: int
    clients: list[DormantClientEntry]
    truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "months": self.months,
            "scanned": self.scanned,
            "total": self.total,
            "truncated": self.truncated,
            "clients": [c.to_dict() for c in self.clients],
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

    default_desks = resolve_default_desk_ids(desks, settings.default_desk_name_list)
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


def _resolve_integration_targets(targets: list[str] | None) -> frozenset[str]:
    if not targets:
        return frozenset({"tiflux", "vhsys"})
    normalized = {str(t).strip().lower() for t in targets if str(t).strip()}
    allowed = normalized & {"tiflux", "vhsys"}
    if not allowed:
        raise OrchestratorError("Informe ao menos um sistema para integrar (tiflux ou vhsys).", 400)
    return frozenset(allowed)


def _finalize_integration_result(
    result: IntegrationResult,
    tf_res: SystemResult,
    vh_res: SystemResult,
    targets: frozenset[str],
) -> IntegrationResult:
    in_tf = "tiflux" in targets
    in_vh = "vhsys" in targets

    dup_tf = in_tf and tf_res.skipped and tf_res.success
    dup_vh = in_vh and vh_res.skipped and vh_res.success
    created_tf = in_tf and tf_res.success and not tf_res.skipped
    created_vh = in_vh and vh_res.success and not vh_res.skipped

    result.duplicates = {"tiflux": dup_tf, "vhsys": dup_vh}

    targeted: list[SystemResult] = []
    if in_tf:
        targeted.append(tf_res)
    if in_vh:
        targeted.append(vh_res)

    if targeted and all(r.skipped and r.success for r in targeted):
        result.all_duplicates = True
        result.success = False
        result.partial = False
        return result

    if created_tf or created_vh:
        result.success = True
        result.partial = dup_tf or dup_vh or (created_tf != created_vh and in_tf and in_vh)
        result.all_duplicates = False
        return result

    result.success = False
    result.partial = False
    result.all_duplicates = False
    return result


async def integrate_company(
    company_data: dict[str, Any],
    desk_ids: list[int],
    technical_group_ids: list[int],
    settings: Settings,
    *,
    override_inactive_registration: bool = False,
    targets: list[str] | None = None,
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
    # #region agent log
    dbg(
        "H1",
        "orchestrator.py:integrate_company",
        "duplicate_lookup",
        {
            "exists_tiflux": existing_tf is not None,
            "exists_vhsys": existing_vh is not None,
        },
    )
    # #endregion

    target_set = _resolve_integration_targets(targets)
    result = IntegrationResult(cnpj=company.cnpj_formatted, company=company)

    async def _tiflux_task() -> SystemResult:
        if "tiflux" not in target_set:
            return SystemResult(
                success=True,
                skipped=True,
                message="TiFlux não incluído nesta integração.",
            )
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
        if "vhsys" not in target_set:
            return SystemResult(
                success=True,
                skipped=True,
                message="VHSYS não incluído nesta integração.",
            )
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
    _finalize_integration_result(result, tf_res, vh_res, target_set)
    # #region agent log
    dbg(
        "H5",
        "orchestrator.py:integrate_company",
        "integration_result_flags",
        {
            "targets": sorted(target_set),
            "partial": result.partial,
            "success": result.success,
            "all_duplicates": result.all_duplicates,
            "tf_success": tf_res.success,
            "tf_skipped": tf_res.skipped,
            "vh_success": vh_res.success,
            "vh_skipped": vh_res.skipped,
        },
    )
    # #endregion

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


def _resolve_client_search(query: str) -> tuple[str, str]:
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


def _resolve_delete_search(query: str) -> tuple[str, str]:
    return _resolve_client_search(query)


async def preview_consult_client(query: str, settings: Settings) -> ConsultPreviewResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_client_search(query)

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)

    async def _search_tiflux() -> list[dict]:
        if search_mode == "cnpj":
            return await tiflux.find_matches_by_cnpj(term, limit=10)
        return await tiflux.find_by_name(term, limit=10)

    async def _search_vhsys() -> tuple[list[dict], list[dict]]:
        if search_mode == "cnpj":
            return await vhsys.find_matches_active_and_trash_by_cnpj(format_cnpj(term), limit=10)
        return await vhsys.find_matches_active_and_trash_by_name(term, limit=10)

    try:
        tf_items, (vh_active, vh_trash) = await asyncio.gather(
            _search_tiflux(),
            _search_vhsys(),
        )
    except (TifluxApiError, VhsysApiError) as exc:
        raise OrchestratorError(str(exc), getattr(exc, "status_code", None) or 502) from exc

    tf_matches = [_tiflux_match_summary(x) for x in tf_items if x.get("id") is not None]
    vh_active_matches = [_vhsys_match_summary(x) for x in vh_active if x.get("id_cliente") is not None]
    vh_trash_matches = [_vhsys_match_summary(x) for x in vh_trash if x.get("id_cliente") is not None]

    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    return ConsultPreviewResult(
        query=display_query,
        search_mode=search_mode,
        tiflux=ConsultSystemPreview(
            found=bool(tf_matches),
            matches_active=tf_matches,
        ),
        vhsys=ConsultSystemPreview(
            found=bool(vh_active_matches or vh_trash_matches),
            matches_active=vh_active_matches,
            matches_trash=vh_trash_matches,
        ),
    )


async def fetch_consult_detail(
    query: str,
    settings: Settings,
    *,
    tiflux_client_id: int | None = None,
    vhsys_client_id: int | None = None,
) -> ConsultDetailResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_client_search(query)
    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    if tiflux_client_id is None and vhsys_client_id is None:
        raise OrchestratorError(
            "Selecione ao menos um cliente para consultar (TiFlux ou VHSYS).",
            400,
        )

    tiflux = TifluxClient(settings)
    vhsys = VhsysClient(settings)
    result = ConsultDetailResult(query=display_query)

    async def _tiflux_detail() -> SystemResult:
        if tiflux_client_id is None:
            return SystemResult(
                success=True,
                skipped=True,
                message="TiFlux não selecionado para consulta.",
            )
        try:
            profile = await tiflux.get_client_profile(int(tiflux_client_id))
            return SystemResult(
                success=True,
                message="Dados TiFlux carregados.",
                data=profile,
            )
        except TifluxApiError as exc:
            return SystemResult(success=False, error=str(exc), message="Falha no TiFlux.")

    async def _vhsys_detail() -> SystemResult:
        if vhsys_client_id is None:
            return SystemResult(
                success=True,
                skipped=True,
                message="VHSYS não selecionado para consulta.",
            )
        try:
            data = await vhsys.get_by_id(vhsys_client_id)
            if not data:
                return SystemResult(
                    success=False,
                    error="Cliente não encontrado no VHSYS.",
                    message="Falha no VHSYS.",
                )
            return SystemResult(
                success=True,
                message="Dados VHSYS carregados.",
                data=data,
            )
        except VhsysApiError as exc:
            return SystemResult(success=False, error=str(exc), message="Falha no VHSYS.")

    tf_res, vh_res = await asyncio.gather(_tiflux_detail(), _vhsys_detail())
    result.tiflux = tf_res
    result.vhsys = vh_res

    attempted = [
        r
        for r, selected in (
            (tf_res, tiflux_client_id is not None),
            (vh_res, vhsys_client_id is not None),
        )
        if selected
    ]
    ok_count = sum(1 for r in attempted if r.success)
    result.success = bool(attempted) and ok_count == len(attempted)

    return result


def _normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower().strip()


def _desk_matches_name(desk: dict, target: str) -> bool:
    norm_target = _normalize_label(target)
    for field in ("display_name", "name"):
        norm = _normalize_label(str(desk.get(field) or ""))
        if not norm:
            continue
        if norm == norm_target or norm.startswith(norm_target) or norm_target in norm:
            return True
    return False


def resolve_default_desk_ids(desks: list[dict], names: list[str]) -> list[int]:
    ids: list[int] = []
    for target in names:
        for desk in desks:
            if not desk.get("active", True):
                continue
            desk_id = desk.get("id")
            if desk_id is None:
                continue
            if _desk_matches_name(desk, target) and int(desk_id) not in ids:
                ids.append(int(desk_id))
                break
    return ids


async def preview_inactivate_client(query: str, settings: Settings) -> InactivatePreviewResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_client_search(query)
    tiflux = TifluxClient(settings)

    try:
        if search_mode == "cnpj":
            tf_items = await tiflux.find_matches_by_cnpj(term, limit=10)
        else:
            tf_items = await tiflux.find_by_name(term, limit=10)
    except TifluxApiError as exc:
        raise OrchestratorError(str(exc), getattr(exc, "status_code", None) or 502) from exc

    tf_matches = [_tiflux_match_summary(x) for x in tf_items if x.get("id") is not None]
    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    return InactivatePreviewResult(
        query=display_query,
        search_mode=search_mode,
        tiflux=DeleteSystemPreview(found=bool(tf_matches), matches=tf_matches),
    )


preview_delete_client = preview_inactivate_client


async def execute_inactivate(
    query: str,
    settings: Settings,
    *,
    tiflux_client_id: int | None = None,
) -> InactivateResult:
    _ensure_credentials(settings)
    search_mode, term = _resolve_delete_search(query)
    display_query = format_cnpj(term) if search_mode == "cnpj" else term

    if tiflux_client_id is None:
        raise OrchestratorError("Selecione um cliente TiFlux para inativar.", 400)

    tiflux = TifluxClient(settings)
    result = InactivateResult(query=display_query)

    try:
        client_id = int(tiflux_client_id)
        if search_mode == "cnpj":
            client_id = await tiflux.resolve_client_id(client_id, cnpj_digits=term)
        await tiflux.delete_client(client_id)
        result.tiflux = SystemResult(
            success=True,
            message="Cliente inativado no TiFlux.",
            data={"id": client_id},
        )
        result.success = True
    except TifluxApiError as exc:
        result.tiflux = SystemResult(success=False, error=str(exc), message="Falha no TiFlux.")

    return result


execute_delete = execute_inactivate


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:19], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


async def _emit_dormant_progress(
    on_progress: Any | None,
    payload: dict[str, Any],
) -> None:
    if on_progress is None:
        return
    result = on_progress(payload)
    if asyncio.iscoroutine(result):
        await result


async def scan_dormant_clients(
    settings: Settings,
    *,
    months: int = 24,
    limit: int = 100,
    on_progress: Any | None = None,
) -> DormantScanResult:
    _ensure_credentials(settings)
    tiflux = TifluxClient(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    dormant: list[DormantClientEntry] = []
    scanned = 0
    scan_cap = min(max(limit * 4, limit), 400)

    await _emit_dormant_progress(
        on_progress,
        {
            "phase": "start",
            "scanned": 0,
            "found": 0,
            "limit": limit,
            "scan_cap": scan_cap,
            "percent": 0,
        },
    )

    async for client in tiflux.iter_active_clients(max_clients=scan_cap):
        scanned += 1
        client_id = int(client["id"])
        display_name = str(client.get("social") or client.get("name") or "")

        await _emit_dormant_progress(
            on_progress,
            {
                "phase": "tickets",
                "scanned": scanned,
                "found": len(dormant),
                "limit": limit,
                "scan_cap": scan_cap,
                "percent": min(99, int((scanned / scan_cap) * 100)),
                "current_client": display_name,
            },
        )
        last_ticket = await tiflux.get_last_ticket_datetime(client_id)
        await asyncio.sleep(0.15)

        await _emit_dormant_progress(
            on_progress,
            {
                "phase": "billing",
                "scanned": scanned,
                "found": len(dormant),
                "limit": limit,
                "scan_cap": scan_cap,
                "percent": min(99, int((scanned / scan_cap) * 100)),
                "current_client": display_name,
            },
        )
        last_billing = await tiflux.get_last_billing_datetime(client_id)
        await asyncio.sleep(0.15)

        no_ticket = last_ticket is None or last_ticket < cutoff
        no_billing = last_billing is None or last_billing < cutoff
        if not (no_ticket or no_billing):
            continue

        reasons: list[str] = []
        if no_ticket:
            reasons.append("sem_ticket_24m")
        if no_billing:
            reasons.append("sem_cobranca_24m")

        dormant.append(
            DormantClientEntry(
                id=client_id,
                name=str(client.get("name") or ""),
                social=str(client.get("social") or ""),
                social_revenue=str(client.get("social_revenue") or ""),
                last_ticket_at=last_ticket.isoformat() if last_ticket else None,
                last_billing_at=last_billing.isoformat() if last_billing else None,
                reasons=reasons,
            )
        )
        await _emit_dormant_progress(
            on_progress,
            {
                "phase": "scanning",
                "scanned": scanned,
                "found": len(dormant),
                "limit": limit,
                "scan_cap": scan_cap,
                "percent": min(99, int((scanned / scan_cap) * 100)),
                "current_client": display_name,
            },
        )
        if len(dormant) >= limit:
            return DormantScanResult(
                months=months,
                scanned=scanned,
                total=len(dormant),
                clients=dormant,
                truncated=True,
            )

    return DormantScanResult(
        months=months,
        scanned=scanned,
        total=len(dormant),
        clients=dormant,
        truncated=False,
    )


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

