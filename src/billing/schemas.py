"""Schemas Pydantic — billing_runs / items / artifacts (ADR-0002)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.cnpj.validator import normalize_cnpj, validate_cnpj

BillingStatus = Literal[
    "draft",
    "approved",
    "awaiting_prefeitura",
    "emitting",
    "sent",
    "error",
]
BillingItemSource = Literal["contract", "ticket"]
PaymentMethod = Literal["boleto", "pix"]
ArtifactKind = Literal["report", "nf", "boleto"]

_COMPETENCE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BillingItemWrite(BaseModel):
    source: BillingItemSource
    external_ref: str | None = None
    description: str = Field(min_length=1, max_length=1000)
    amount: float
    sort_order: int = Field(default=0, ge=0)


class BillingItemRead(BaseModel):
    id: int
    run_id: int
    source: BillingItemSource
    external_ref: str | None = None
    description: str
    amount: float
    sort_order: int = 0


class BillingArtifactWrite(BaseModel):
    kind: ArtifactKind
    path_or_url: str = Field(min_length=1, max_length=2000)


class BillingArtifactRead(BaseModel):
    id: int
    run_id: int
    kind: ArtifactKind
    path_or_url: str
    created_at: str


class BillingRunWrite(BaseModel):
    """Montar fila — ADR-0002 BillingRunWrite."""

    cnpj: str
    client_name: str | None = None
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    competence: str
    due_date: str | None = None
    has_retencao: bool = False
    payment_method: PaymentMethod | None = "boleto"
    gross_total: float | None = None
    discount_pct: float | None = Field(default=None, ge=0, le=100)
    discount_value: float | None = Field(default=None, ge=0)
    items: list[BillingItemWrite] = Field(default_factory=list)

    @field_validator("cnpj")
    @classmethod
    def _normalize_and_validate_cnpj(cls, value: str) -> str:
        digits = normalize_cnpj(value)
        if len(digits) != 14 or not validate_cnpj(digits):
            raise ValueError("CNPJ inválido (14 dígitos).")
        return digits

    @field_validator("competence")
    @classmethod
    def _validate_competence(cls, value: str) -> str:
        if not _COMPETENCE_RE.match(value):
            raise ValueError("competence deve ser YYYY-MM.")
        return value

    @field_validator("due_date")
    @classmethod
    def _validate_due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DATE_RE.match(value):
            raise ValueError("due_date deve ser YYYY-MM-DD.")
        return value


class BillingRunUpdate(BaseModel):
    """Update parcial de draft; `items` None = não altera itens."""

    cnpj: str | None = None
    client_name: str | None = None
    tiflux_client_id: int | None = None
    vhsys_client_id: int | None = None
    competence: str | None = None
    due_date: str | None = None
    has_retencao: bool | None = None
    payment_method: PaymentMethod | None = None
    gross_total: float | None = None
    discount_pct: float | None = Field(default=None, ge=0, le=100)
    discount_value: float | None = Field(default=None, ge=0)
    items: list[BillingItemWrite] | None = None

    @field_validator("cnpj")
    @classmethod
    def _normalize_and_validate_cnpj(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = normalize_cnpj(value)
        if len(digits) != 14 or not validate_cnpj(digits):
            raise ValueError("CNPJ inválido (14 dígitos).")
        return digits

    @field_validator("competence")
    @classmethod
    def _validate_competence(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _COMPETENCE_RE.match(value):
            raise ValueError("competence deve ser YYYY-MM.")
        return value

    @field_validator("due_date")
    @classmethod
    def _validate_due_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _DATE_RE.match(value):
            raise ValueError("due_date deve ser YYYY-MM-DD.")
        return value

    @model_validator(mode="after")
    def _at_least_one_field(self) -> BillingRunUpdate:
        data = self.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class BillingPrefeituraInput(BaseModel):
    """Branch retenção — ADR-0002 BillingPrefeituraInput."""

    nf_prefeitura_number: str = Field(min_length=1, max_length=100)
    net_total: float = Field(gt=0)


class BillingRunRead(BaseModel):
    id: int
    cnpj: str
    client_name: str | None
    tiflux_client_id: int | None
    vhsys_client_id: int | None
    competence: str
    due_date: str | None
    status: BillingStatus
    has_retencao: bool
    payment_method: str | None
    gross_total: float | None
    discount_pct: float | None
    discount_value: float | None
    net_total: float | None
    nf_prefeitura_number: str | None
    tiflux_ticket_number: str | None
    vhsys_nf_id: str | None
    vhsys_cr_id: str | None
    error_message: str | None
    approved_by: int | None
    created_by: int | None
    created_at: str
    updated_at: str
    approved_at: str | None
    sent_at: str | None
    items: list[BillingItemRead] = Field(default_factory=list)
    artifacts: list[BillingArtifactRead] = Field(default_factory=list)
