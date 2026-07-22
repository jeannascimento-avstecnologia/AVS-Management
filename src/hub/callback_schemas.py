"""Contrato CallbackPayload — ADR-0003."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


CallbackEvent = Literal[
    "quote.submit",
    "quote.sent",
    "quote.approved",
    "billing.approved",
    "billing.nf_prefeitura",
]
CallbackResourceType = Literal["quote", "billing_run"]
CallbackStatus = Literal["ok", "error"]


class CallbackExternal(BaseModel):
    tiflux_ticket_number: str | None = None
    vhsys_os_id: str | None = None
    vhsys_nf_id: str | None = None
    vhsys_cr_id: str | None = None
    tiflux_contract_ids: list[str] | None = None


class CallbackPayload(BaseModel):
    event: CallbackEvent
    resource_type: CallbackResourceType
    resource_id: int = Field(ge=1)
    status: CallbackStatus
    outbox_id: int = Field(ge=1)
    external: CallbackExternal | None = None
    error_message: str | None = None
    dry_run: bool | None = None
