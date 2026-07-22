"""Schemas da consulta de documentos (SPEC_CONSULTA_DOCUMENTOS)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EnrichmentStatus = Literal["ok", "skipped", "error"]
DocType = Literal["orcamento", "faturamento", "pdf"]


class DocumentQuoteHit(BaseModel):
    id: int
    display_id: str
    doc_type: DocType = "orcamento"
    cnpj: str
    client_name: str | None = None
    status: str
    lead_temperature: str | None = None
    billed_by_type: str | None = None
    billed_by_name: str | None = None
    vhsys_os_id: str | None = None
    tiflux_ticket_number: str | None = None
    tiflux_client_id: int | None = None
    has_pdf: bool = False
    implant_net: float | None = None
    monthly_net: float | None = None
    value_total: float | None = None
    created_at: str
    updated_at: str


class DocumentPdfHit(BaseModel):
    quote_id: int
    display_id: str
    doc_type: DocType = "pdf"
    client_name: str | None = None
    cnpj: str
    status: str | None = None
    lead_temperature: str | None = None
    billed_by_type: str | None = None
    billed_by_name: str | None = None
    vhsys_os_id: str | None = None
    tiflux_ticket_number: str | None = None
    has_pdf: bool = True
    value_total: float | None = None
    pdf_path: str
    created_at: str | None = None
    updated_at: str | None = None


class DocumentBillingHit(BaseModel):
    id: int
    doc_type: DocType = "faturamento"
    cnpj: str
    client_name: str | None = None
    competence: str
    status: str
    net_total: float | None = None
    gross_total: float | None = None
    due_date: str | None = None
    payment_method: str | None = None
    vhsys_nf_id: str | None = None
    vhsys_cr_id: str | None = None
    tiflux_ticket_number: str | None = None
    tiflux_client_id: int | None = None
    created_at: str
    updated_at: str


class DocumentsEnrichment(BaseModel):
    tiflux: EnrichmentStatus = "skipped"
    vhsys: EnrichmentStatus = "skipped"
    detail: str | None = None


class DocumentsSearchResponse(BaseModel):
    query: str
    quotes: list[DocumentQuoteHit] = Field(default_factory=list)
    pdfs: list[DocumentPdfHit] = Field(default_factory=list)
    billing_runs: list[DocumentBillingHit] = Field(default_factory=list)
    enrichment: DocumentsEnrichment = Field(default_factory=DocumentsEnrichment)
