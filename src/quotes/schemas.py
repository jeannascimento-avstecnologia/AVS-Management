from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.cnpj.validator import normalize_cnpj, validate_cnpj

QuoteStatus = Literal["draft", "submitted", "sent", "approved", "rejected", "contracted"]
LegacyModuleKind = Literal["implantacao", "mensalidade"]
# section = module.id (seed + custom); keep aliases for callers/tests
QuoteSection = str
BilledByType = Literal["distribuidor", "fornecedor"]
LeadTemperature = Literal["quente", "morno", "frio"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")


def _normalize_optional_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if not _EMAIL_RE.match(cleaned):
        raise ValueError(f"E-mail inválido: {value}")
    return cleaned


def _normalize_email_list(value: list[str] | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in value:
        email = _normalize_optional_email(raw)
        if email and email not in seen:
            seen.add(email)
            out.append(email)
    return out


def _normalize_optional_notes(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 4000:
        raise ValueError("Observações: máximo 4000 caracteres.")
    return cleaned


def _normalize_optional_internal_notes(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 4000:
        raise ValueError("Observações internas: máximo 4000 caracteres.")
    return cleaned


def _normalize_module_id(value: str) -> str:
    cleaned = value.strip().lower().replace(" ", "_")
    if not cleaned or not _MODULE_ID_RE.fullmatch(cleaned):
        raise ValueError(
            "id do módulo deve começar com letra e usar só a-z, 0-9, _ ou - (máx. 64)."
        )
    return cleaned


class InstallmentLine(BaseModel):
    """Uma parcela individual com data e valor."""

    due_date: str = Field(max_length=10)
    amount: float = Field(ge=0)


class QuoteModule(BaseModel):
    """Bloco do passo 2 / PDF — seed Implantação+Mensalidade ou custom."""

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    legacy_kind: LegacyModuleKind | None = None
    show_labor: bool = False
    payment_plan: str | None = Field(default=None, max_length=200)
    discount_pct: float | None = None
    discount_value: float | None = None
    labor_hours: float | None = None
    labor_hourly_rate: float | None = None
    notes: str | None = None
    billed_by_name: str | None = Field(default=None, max_length=300)
    billed_by_cnpj: str | None = None
    simplified: bool = False
    display_name: str | None = Field(default=None, max_length=200)
    sort_order: int = Field(default=0, ge=0)
    installments_json: list[InstallmentLine] | None = None

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        return _normalize_module_id(value)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Título do módulo é obrigatório.")
        return cleaned

    @field_validator("notes")
    @classmethod
    def _normalize_module_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @field_validator("billed_by_name")
    @classmethod
    def _normalize_module_billed_by(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Faturado por")

    @field_validator("billed_by_cnpj")
    @classmethod
    def _normalize_module_billed_cnpj(cls, value: str | None) -> str | None:
        return _normalize_optional_cnpj(value)

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=200, label="Nome de exibição")

    @model_validator(mode="after")
    def _legacy_kind_matches_id(self) -> QuoteModule:
        if self.legacy_kind is not None and self.id != self.legacy_kind:
            raise ValueError(
                f"legacy_kind '{self.legacy_kind}' exige id igual (got '{self.id}')."
            )
        if self.legacy_kind == "implantacao":
            # Implantação seed: sem mão de obra
            object.__setattr__(self, "show_labor", False)
            object.__setattr__(self, "labor_hours", None)
            object.__setattr__(self, "labor_hourly_rate", None)
        return self


def seed_default_modules() -> list[QuoteModule]:
    """Create sem `modules` e sem itens → canvas vazio.

    Clientes que omitem `modules` mas enviam itens (legado) recebem módulos inferidos.
    """
    return []


def _preset_implant() -> QuoteModule:
    return QuoteModule(
        id="implantacao",
        title="Implantação",
        legacy_kind="implantacao",
        show_labor=False,
        sort_order=0,
    )


def _preset_monthly() -> QuoteModule:
    return QuoteModule(
        id="mensalidade",
        title="Mensalidade",
        legacy_kind="mensalidade",
        show_labor=True,
        sort_order=1,
    )


def infer_modules_from_items(items: list[QuoteItemWrite]) -> list[QuoteModule]:
    """Quando create omite `modules` mas traz itens, reconstroi blocos pelos `section`."""
    sections: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item.section not in seen:
            seen.add(item.section)
            sections.append(item.section)
    out: list[QuoteModule] = []
    for idx, section in enumerate(sections):
        if section == "implantacao":
            out.append(_preset_implant().model_copy(update={"sort_order": idx}))
        elif section == "mensalidade":
            out.append(_preset_monthly().model_copy(update={"sort_order": idx}))
        else:
            out.append(
                QuoteModule(
                    id=section,
                    title=section.replace("_", " ").title(),
                    sort_order=idx,
                )
            )
    return out


def validate_modules_and_items(
    modules: list[QuoteModule],
    items: list[QuoteItemWrite],
) -> list[QuoteModule]:
    """Ids únicos; itens só de módulos existentes; normaliza sort_order."""
    if not modules and items:
        raise ValueError("Itens referenciam módulos, mas a lista de módulos está vazia.")
    ids = [m.id for m in modules]
    if len(ids) != len(set(ids)):
        raise ValueError("Ids de módulo devem ser únicos.")
    id_set = set(ids)
    for item in items:
        if item.section not in id_set:
            raise ValueError(
                f"Item '{item.name}' referencia módulo inexistente '{item.section}'."
            )
    ordered = sorted(enumerate(modules), key=lambda pair: (pair[1].sort_order, pair[0]))
    return [
        mod.model_copy(update={"sort_order": idx})
        for idx, (_orig, mod) in enumerate(ordered)
    ]


DEFAULT_QUOTE_NOTES = ""


def seed_quote_notes(notes: str | None, *, ticket: str | None = None) -> str:
    cleaned = (notes or "").strip()
    if cleaned:
        return cleaned
    if not DEFAULT_QUOTE_NOTES:
        return ""
    number = (ticket or "").strip()
    if number:
        return f"{DEFAULT_QUOTE_NOTES} {number}"
    return DEFAULT_QUOTE_NOTES


class QuoteItemWrite(BaseModel):
    id: int | None = Field(default=None, ge=1)
    section: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=500)
    qty: float = Field(default=1.0, gt=0)
    unit_value: float = Field(default=0.0, ge=0)
    template_key: str | None = None
    vhsys_product_id: int | None = Field(default=None, ge=1)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("section")
    @classmethod
    def _normalize_section(cls, value: str) -> str:
        return _normalize_module_id(value)

    def computed_total(self) -> float:
        return round(self.qty * self.unit_value, 2)


class VhsysCatalogCreateBody(BaseModel):
    """Via dupla — cadastra no VHSYS se nome ainda não existir."""

    name: str = Field(min_length=1, max_length=500)
    unit_value: float = Field(default=0.0, ge=0)
    tipo_produto: Literal["Servico", "Produto"] = "Servico"
    unidade_produto: str = Field(default="UN", min_length=1, max_length=20)
    id_categoria: int | None = Field(default=None, ge=1)
    id_subcategoria: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome do produto é obrigatório.")
        return cleaned


class QuoteItemRead(BaseModel):
    id: int
    quote_id: int
    section: str
    name: str
    qty: float
    unit_value: float
    total_value: float
    template_key: str | None = None
    vhsys_product_id: int | None = None
    sort_order: int = 0


def _normalize_optional_cnpj(value: str | None) -> str | None:
    if value is None:
        return None
    digits = normalize_cnpj(value)
    if not digits:
        return None
    if len(digits) != 14 or not validate_cnpj(digits):
        raise ValueError("CNPJ inválido (14 dígitos).")
    return digits


def _normalize_optional_text(value: str | None, *, max_len: int, label: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise ValueError(f"{label}: máximo {max_len} caracteres.")
    return cleaned


class QuoteWrite(BaseModel):
    """Create/update draft — ADR-0002 QuoteWrite."""

    cnpj: str
    client_name: str | None = Field(default=None, max_length=300)
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    lead_temperature: LeadTemperature | None = None
    billed_by_type: BilledByType | None = None
    billed_by_name: str | None = Field(default=None, max_length=300)
    implant_payment_plan: str | None = Field(default=None, max_length=200)
    implant_discount_pct: float | None = None
    implant_discount_value: float | None = None
    implant_labor_hours: float | None = None
    implant_labor_hourly_rate: float | None = None
    monthly_payment_plan: str | None = Field(default=None, max_length=200)
    monthly_discount_pct: float | None = None
    monthly_discount_value: float | None = None
    monthly_labor_hours: float | None = None
    monthly_labor_hourly_rate: float | None = None
    modules: list[QuoteModule] | None = None
    client_email: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    extra_recipients: list[str] = Field(default_factory=list)
    monthly_draft_json: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    title: str | None = None
    items: list[QuoteItemWrite] = Field(default_factory=list)

    @field_validator("cnpj")
    @classmethod
    def _normalize_and_validate_cnpj(cls, value: str) -> str:
        digits = normalize_cnpj(value)
        if len(digits) != 14 or not validate_cnpj(digits):
            raise ValueError("CNPJ inválido (14 dígitos).")
        return digits

    @field_validator("client_name")
    @classmethod
    def _normalize_client_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Nome do cliente")

    @field_validator("billed_by_name")
    @classmethod
    def _normalize_billed_by_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Faturado por")

    @field_validator("implant_payment_plan", "monthly_payment_plan")
    @classmethod
    def _normalize_payment_plan(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=200, label="Plano de pagamento")

    @field_validator("client_email")
    @classmethod
    def _normalize_client_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

    @field_validator("contact_name")
    @classmethod
    def _normalize_contact_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Nome do contato")

    @field_validator("contact_email")
    @classmethod
    def _normalize_contact_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

    @field_validator("contact_phone")
    @classmethod
    def _normalize_contact_phone(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=40, label="Telefone do contato")

    @field_validator("extra_recipients")
    @classmethod
    def _normalize_extra_recipients(cls, value: list[str] | None) -> list[str]:
        return _normalize_email_list(value)

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @field_validator("internal_notes")
    @classmethod
    def _normalize_internal_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_internal_notes(value)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=120, label="Nome do orçamento")

    @model_validator(mode="after")
    def _validate_modules(self) -> QuoteWrite:
        if self.modules is not None:
            mods = self.modules
        elif self.items:
            mods = infer_modules_from_items(self.items)
            mods = _apply_flat_to_seed(mods, self)
        else:
            mods = seed_default_modules()
        mods = validate_modules_and_items(mods, self.items)
        object.__setattr__(self, "modules", mods)
        return self


def _apply_flat_to_seed(mods: list[QuoteModule], data: QuoteWrite | QuoteUpdate) -> list[QuoteModule]:
    out: list[QuoteModule] = []
    for mod in mods:
        if mod.legacy_kind == "implantacao":
            out.append(
                mod.model_copy(
                    update={
                        "payment_plan": getattr(data, "implant_payment_plan", None),
                        "discount_pct": getattr(data, "implant_discount_pct", None),
                        "discount_value": getattr(data, "implant_discount_value", None),
                        "labor_hours": None,
                        "labor_hourly_rate": None,
                        "show_labor": False,
                    }
                )
            )
        elif mod.legacy_kind == "mensalidade":
            out.append(
                mod.model_copy(
                    update={
                        "payment_plan": getattr(data, "monthly_payment_plan", None),
                        "discount_pct": getattr(data, "monthly_discount_pct", None),
                        "discount_value": getattr(data, "monthly_discount_value", None),
                        "labor_hours": getattr(data, "monthly_labor_hours", None),
                        "labor_hourly_rate": getattr(data, "monthly_labor_hourly_rate", None),
                        "show_labor": True,
                    }
                )
            )
        else:
            out.append(mod)
    return out


class QuoteUpdate(BaseModel):
    """Update parcial de draft; `items` None = não altera itens; `modules` None = não altera."""

    cnpj: str | None = None
    client_name: str | None = Field(default=None, max_length=300)
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    lead_temperature: LeadTemperature | None = None
    billed_by_type: BilledByType | None = None
    billed_by_name: str | None = Field(default=None, max_length=300)
    implant_payment_plan: str | None = Field(default=None, max_length=200)
    implant_discount_pct: float | None = None
    implant_discount_value: float | None = None
    implant_labor_hours: float | None = None
    implant_labor_hourly_rate: float | None = None
    monthly_payment_plan: str | None = Field(default=None, max_length=200)
    monthly_discount_pct: float | None = None
    monthly_discount_value: float | None = None
    monthly_labor_hours: float | None = None
    monthly_labor_hourly_rate: float | None = None
    modules: list[QuoteModule] | None = None
    client_email: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    extra_recipients: list[str] | None = None
    notes: str | None = None
    internal_notes: str | None = None
    title: str | None = None
    items: list[QuoteItemWrite] | None = None

    @field_validator("cnpj")
    @classmethod
    def _normalize_and_validate_cnpj(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = normalize_cnpj(value)
        if len(digits) != 14 or not validate_cnpj(digits):
            raise ValueError("CNPJ inválido (14 dígitos).")
        return digits

    @field_validator("client_name")
    @classmethod
    def _normalize_client_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Nome do cliente")

    @field_validator("billed_by_name")
    @classmethod
    def _normalize_billed_by_name(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Faturado por")

    @field_validator("implant_payment_plan", "monthly_payment_plan")
    @classmethod
    def _normalize_payment_plan(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=200, label="Plano de pagamento")

    @field_validator("client_email")
    @classmethod
    def _normalize_client_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

    @field_validator("contact_name")
    @classmethod
    def _normalize_contact_name_upd(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Nome do contato")

    @field_validator("contact_email")
    @classmethod
    def _normalize_contact_email_upd(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

    @field_validator("contact_phone")
    @classmethod
    def _normalize_contact_phone_upd(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=40, label="Telefone do contato")

    @field_validator("extra_recipients")
    @classmethod
    def _normalize_extra_recipients(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return _normalize_email_list(value)

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @field_validator("internal_notes")
    @classmethod
    def _normalize_internal_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_internal_notes(value)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=120, label="Nome do orçamento")

    @model_validator(mode="after")
    def _at_least_one_field(self) -> QuoteUpdate:
        data = self.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("Informe ao menos um campo para atualizar.")
        if self.modules is not None and self.items is not None:
            object.__setattr__(
                self,
                "modules",
                validate_modules_and_items(self.modules, self.items),
            )
        elif self.modules is not None:
            object.__setattr__(
                self,
                "modules",
                validate_modules_and_items(self.modules, []),
            )
        return self


class QuoteRead(BaseModel):
    id: int
    cnpj: str
    client_name: str | None
    tiflux_client_id: int | None
    vhsys_client_id: int | None
    status: QuoteStatus
    lead_temperature: str | None
    billed_by_type: str | None
    billed_by_name: str | None
    active_quote_version_id: int | None = None
    current_version_number: int | None = None
    implant_payment_plan: str | None
    implant_discount_pct: float | None
    implant_discount_value: float | None
    implant_labor_hours: float | None = None
    implant_labor_hourly_rate: float | None = None
    monthly_payment_plan: str | None
    monthly_discount_pct: float | None
    monthly_discount_value: float | None
    monthly_labor_hours: float | None = None
    monthly_labor_hourly_rate: float | None = None
    modules: list[QuoteModule] = Field(default_factory=list)
    client_email: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    extra_recipients: list[str] = Field(default_factory=list)
    monthly_draft_json: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    title: str | None = None
    tiflux_ticket_number: str | None
    vhsys_os_id: str | None
    pdf_path: str | None
    created_by: int | None
    created_at: str
    updated_at: str
    submitted_at: str | None
    sent_at: str | None
    approved_at: str | None
    items: list[QuoteItemRead] = Field(default_factory=list)

    @field_validator("internal_notes")
    @classmethod
    def _normalize_internal_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_internal_notes(value)


class QuoteMonthlyChargeWrite(BaseModel):
    """Uma cobrança mensal (legado; preferir allocations)."""

    name: str = Field(min_length=1, max_length=200)
    amount: float = Field(ge=0)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome da mensalidade é obrigatório.")
        return cleaned


class QuoteMonthlyAllocationWrite(BaseModel):
    """Fornecedor + intermediador de uma linha selecionada."""

    item_id: int = Field(ge=1)
    fornecedor_name: str = Field(default="Fornecedor", max_length=200)
    fornecedor_amount: float = Field(ge=0)
    intermediador_name: str = Field(default="Intermediador", max_length=200)
    intermediador_amount: float = Field(ge=0)
    vhsys_product_id: int | None = Field(default=None, ge=1)
    source: Literal["vhsys", "manual"] = "manual"
    warning: str | None = None

    @field_validator("fornecedor_name", "intermediador_name")
    @classmethod
    def _strip_party(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome da parte da mensalidade é obrigatório.")
        return cleaned


class QuoteMonthlySuggestBody(BaseModel):
    item_ids: list[int] = Field(min_length=1)

    @field_validator("item_ids")
    @classmethod
    def _unique_ids(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("item_ids não deve conter duplicados.")
        return value


class QuoteMonthlyDraftWrite(BaseModel):
    """
    Rascunho das mensalidades: cada linha selecionada tem fornecedor+intermediador
    cuja soma deve bater com o total daquela linha.
    """

    allocations: list[QuoteMonthlyAllocationWrite] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_items(self) -> QuoteMonthlyDraftWrite:
        ids = [a.item_id for a in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("allocations não deve conter itens duplicados.")
        return self


class QuoteVersionRead(BaseModel):
    id: int
    quote_id: int
    version_number: int
    snapshot_notes: str | None = None
    snapshot_monthly_json: str | None = None
    pdf_path: str | None = None
    created_at: str


class QuoteTemplateLine(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    qty: float = Field(default=1.0, gt=0)
    unit_value: float = Field(default=0.0, ge=0)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def _strip_line_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome da linha é obrigatório.")
        return cleaned


class QuoteTemplateWrite(BaseModel):
    """Cria modelo pré-preenchido (section = module.id)."""

    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    section: str = Field(min_length=1, max_length=64)
    lines: list[QuoteTemplateLine] = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome do modelo é obrigatório.")
        return cleaned

    @field_validator("section")
    @classmethod
    def _normalize_section(cls, value: str) -> str:
        return _normalize_module_id(value)

    @field_validator("key")
    @classmethod
    def _normalize_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower().replace(" ", "_")
        if not cleaned:
            return None
        if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]{0,79}", cleaned):
            raise ValueError(
                "key deve começar com letra/dígito e usar só a-z, 0-9, _ ou -."
            )
        return cleaned


class QuoteTemplateUpdate(BaseModel):
    """Atualiza nome, seção e/ou linhas do modelo."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    section: str | None = Field(default=None, min_length=1, max_length=64)
    lines: list[QuoteTemplateLine] | None = Field(default=None, min_length=1)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome do modelo é obrigatório.")
        return cleaned

    @field_validator("section")
    @classmethod
    def _normalize_section(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_module_id(value)


class QuoteTemplateRead(BaseModel):
    id: int
    key: str
    name: str
    section: str
    lines: list[QuoteTemplateLine]
    created_at: str


class QuoteModuleTemplateWrite(BaseModel):
    """Cria modelo de módulo (bloco reutilizável)."""

    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    show_labor: bool = False
    notes: str | None = None
    billed_by_name: str | None = Field(default=None, max_length=300)
    billed_by_cnpj: str | None = None
    simplified: bool = False
    display_name: str | None = Field(default=None, max_length=200)
    lines: list[QuoteTemplateLine] = Field(default_factory=list)

    @field_validator("name", "title")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Campo obrigatório.")
        return cleaned

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @field_validator("billed_by_name")
    @classmethod
    def _normalize_billed_by(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Faturado por")

    @field_validator("billed_by_cnpj")
    @classmethod
    def _normalize_billed_cnpj(cls, value: str | None) -> str | None:
        return _normalize_optional_cnpj(value)

    @field_validator("display_name")
    @classmethod
    def _normalize_display(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=200, label="Nome de exibição")

    @field_validator("key")
    @classmethod
    def _normalize_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower().replace(" ", "_")
        if not cleaned:
            return None
        if not re.fullmatch(r"[a-z0-9][a-z0-9_\-]{0,79}", cleaned):
            raise ValueError(
                "key deve começar com letra/dígito e usar só a-z, 0-9, _ ou -."
            )
        return cleaned


class QuoteModuleTemplateUpdate(BaseModel):
    """Atualiza modelo de módulo (parcial)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    show_labor: bool | None = None
    notes: str | None = None
    billed_by_name: str | None = Field(default=None, max_length=300)
    billed_by_cnpj: str | None = None
    simplified: bool | None = None
    display_name: str | None = Field(default=None, max_length=200)
    lines: list[QuoteTemplateLine] | None = None

    @field_validator("name", "title")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Campo obrigatório.")
        return cleaned

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @field_validator("billed_by_name")
    @classmethod
    def _normalize_billed_by(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=300, label="Faturado por")

    @field_validator("billed_by_cnpj")
    @classmethod
    def _normalize_billed_cnpj(cls, value: str | None) -> str | None:
        return _normalize_optional_cnpj(value)

    @field_validator("display_name")
    @classmethod
    def _normalize_display(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, max_len=200, label="Nome de exibição")


class QuoteModuleTemplateRead(BaseModel):
    id: int
    key: str
    name: str
    title: str
    show_labor: bool
    notes: str | None = None
    billed_by_name: str | None = None
    billed_by_cnpj: str | None = None
    simplified: bool = False
    display_name: str | None = None
    lines: list[QuoteTemplateLine]
    created_at: str


class QuoteProposalTemplateWrite(BaseModel):
    """Snapshot do canvas do passo 2 (sem cliente)."""

    name: str = Field(min_length=1, max_length=200)
    modules: list[QuoteModule] = Field(default_factory=list)
    items: list[QuoteItemWrite] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome do modelo é obrigatório.")
        return cleaned

    @model_validator(mode="after")
    def _validate_canvas(self) -> QuoteProposalTemplateWrite:
        mods = validate_modules_and_items(self.modules, self.items)
        object.__setattr__(self, "modules", mods)
        return self


class QuoteProposalTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    modules: list[QuoteModule] | None = None
    items: list[QuoteItemWrite] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Nome do modelo é obrigatório.")
        return cleaned

    @model_validator(mode="after")
    def _validate_canvas(self) -> QuoteProposalTemplateUpdate:
        if self.modules is not None:
            items = self.items if self.items is not None else []
            object.__setattr__(
                self, "modules", validate_modules_and_items(self.modules, items)
            )
        return self


class QuoteProposalTemplateRead(BaseModel):
    id: int
    name: str
    modules: list[QuoteModule]
    items: list[QuoteItemWrite]
    created_at: str
    updated_at: str
