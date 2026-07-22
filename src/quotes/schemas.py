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


def _normalize_module_id(value: str) -> str:
    cleaned = value.strip().lower().replace(" ", "_")
    if not cleaned or not _MODULE_ID_RE.fullmatch(cleaned):
        raise ValueError(
            "id do módulo deve começar com letra e usar só a-z, 0-9, _ ou - (máx. 64)."
        )
    return cleaned


class QuoteModule(BaseModel):
    """Bloco do passo 2 / PDF — seed Implantação+Mensalidade ou custom."""

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    legacy_kind: LegacyModuleKind | None = None
    show_labor: bool = False
    payment_plan: str | None = None
    discount_pct: float | None = None
    discount_value: float | None = None
    labor_hours: float | None = None
    labor_hourly_rate: float | None = None
    sort_order: int = Field(default=0, ge=0)

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
    """Seed obrigatório no create: Implantação + Mensalidade."""
    return [
        QuoteModule(
            id="implantacao",
            title="Implantação",
            legacy_kind="implantacao",
            show_labor=False,
            sort_order=0,
        ),
        QuoteModule(
            id="mensalidade",
            title="Mensalidade",
            legacy_kind="mensalidade",
            show_labor=True,
            sort_order=1,
        ),
    ]


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


class QuoteItemWrite(BaseModel):
    section: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=500)
    qty: float = Field(default=1.0, gt=0)
    unit_value: float = Field(default=0.0, ge=0)
    template_key: str | None = None
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
    sort_order: int = 0


class QuoteWrite(BaseModel):
    """Create/update draft — ADR-0002 QuoteWrite."""

    cnpj: str
    client_name: str | None = None
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    lead_temperature: LeadTemperature | None = None
    billed_by_type: BilledByType | None = None
    billed_by_name: str | None = None
    implant_payment_plan: str | None = None
    implant_discount_pct: float | None = None
    implant_discount_value: float | None = None
    implant_labor_hours: float | None = None
    implant_labor_hourly_rate: float | None = None
    monthly_payment_plan: str | None = None
    monthly_discount_pct: float | None = None
    monthly_discount_value: float | None = None
    monthly_labor_hours: float | None = None
    monthly_labor_hourly_rate: float | None = None
    modules: list[QuoteModule] | None = None
    client_email: str | None = None
    extra_recipients: list[str] = Field(default_factory=list)
    notes: str | None = None
    items: list[QuoteItemWrite] = Field(default_factory=list)

    @field_validator("cnpj")
    @classmethod
    def _normalize_and_validate_cnpj(cls, value: str) -> str:
        digits = normalize_cnpj(value)
        if len(digits) != 14 or not validate_cnpj(digits):
            raise ValueError("CNPJ inválido (14 dígitos).")
        return digits

    @field_validator("client_email")
    @classmethod
    def _normalize_client_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

    @field_validator("extra_recipients")
    @classmethod
    def _normalize_extra_recipients(cls, value: list[str] | None) -> list[str]:
        return _normalize_email_list(value)

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        return _normalize_optional_notes(value)

    @model_validator(mode="after")
    def _validate_modules(self) -> QuoteWrite:
        mods = self.modules if self.modules is not None else seed_default_modules()
        # Merge flat legacy fields into seed modules when modules omitted
        if self.modules is None:
            mods = _apply_flat_to_seed(mods, self)
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
    client_name: str | None = None
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    lead_temperature: LeadTemperature | None = None
    billed_by_type: BilledByType | None = None
    billed_by_name: str | None = None
    implant_payment_plan: str | None = None
    implant_discount_pct: float | None = None
    implant_discount_value: float | None = None
    implant_labor_hours: float | None = None
    implant_labor_hourly_rate: float | None = None
    monthly_payment_plan: str | None = None
    monthly_discount_pct: float | None = None
    monthly_discount_value: float | None = None
    monthly_labor_hours: float | None = None
    monthly_labor_hourly_rate: float | None = None
    modules: list[QuoteModule] | None = None
    client_email: str | None = None
    extra_recipients: list[str] | None = None
    notes: str | None = None
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

    @field_validator("client_email")
    @classmethod
    def _normalize_client_email(cls, value: str | None) -> str | None:
        return _normalize_optional_email(value)

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
    extra_recipients: list[str] = Field(default_factory=list)
    notes: str | None = None
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
    lines: list[QuoteTemplateLine] = Field(default_factory=list)

    @field_validator("name", "title")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Campo obrigatório.")
        return cleaned

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


class QuoteModuleTemplateRead(BaseModel):
    id: int
    key: str
    name: str
    title: str
    show_labor: bool
    lines: list[QuoteTemplateLine]
    created_at: str
