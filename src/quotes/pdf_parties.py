"""Resolve emitente/cliente do PDF de orçamento via TiFlux + fallback Settings."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from src.cnpj.validator import format_cnpj, normalize_cnpj
from src.config import Settings, get_settings
from src.integrations.tiflux_client import TifluxApiError, TifluxClient
from src.mapping.canonical import format_cep
from src.quotes.schemas import QuoteRead

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuotePdfIssuer:
    name: str
    cnpj: str
    address_line: str
    phone: str
    mobile: str
    email: str
    site: str


@dataclass(frozen=True)
class QuotePdfClient:
    legal_name: str
    cnpj: str
    email: str
    phone: str
    street: str
    number: str
    complement: str
    district: str
    zip_code: str
    city: str
    state: str
    estadual_registration: str = ""


def _digits_phone(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def format_br_phone(raw: str) -> str:
    digits = _digits_phone(raw)
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return (raw or "").strip()


def _format_address_row(row: dict) -> str:
    street = str(row.get("street") or "").strip()
    number = str(row.get("number") or "").strip()
    neighborhood = str(row.get("neighborhood") or row.get("district") or "").strip()
    city = str(row.get("city") or "").strip()
    state = str(row.get("state") or "").strip()
    cep_raw = str(row.get("cep") or row.get("zip_code") or "").strip()
    cep = format_cep(cep_raw) if cep_raw else ""
    street_num = ", ".join(p for p in (street, number) if p)
    locality = " - ".join(p for p in (neighborhood, city, state) if p)
    line = " ".join(p for p in (street_num, locality) if p)
    if cep:
        line = f"{line} CEP: {cep}" if line else f"CEP: {cep}"
    return line


def _pick_phones(contacts: list[dict]) -> tuple[str, str]:
    commercial = ""
    mobile = ""
    fallback = ""
    for row in contacts:
        tel = format_br_phone(str(row.get("telephone") or row.get("phone") or ""))
        if not tel:
            continue
        use = str(row.get("use") or "").strip().lower()
        if use in {"commercial", "comercial", "work", "business"} and not commercial:
            commercial = tel
        elif use in {"mobile", "celular", "cell"} and not mobile:
            mobile = tel
        elif not fallback:
            fallback = tel
    return commercial or fallback, mobile


def _pick_email(contacts: list[dict], fallback: str = "") -> str:
    for row in contacts:
        email = str(row.get("email") or "").strip()
        if email:
            return email
    return fallback


def issuer_from_settings(settings: Settings | None = None) -> QuotePdfIssuer:
    s = settings or get_settings()
    return QuotePdfIssuer(
        name=s.quote_issuer_name.strip() or "AVS TECNOLOGIA",
        cnpj=format_cnpj(s.quote_issuer_cnpj) or s.quote_issuer_cnpj,
        address_line=s.quote_issuer_address.strip(),
        phone=s.quote_issuer_phone.strip(),
        mobile=s.quote_issuer_mobile.strip(),
        email=s.quote_issuer_email.strip(),
        site=s.quote_issuer_site.strip(),
    )


def client_from_quote(quote: QuoteRead) -> QuotePdfClient:
    return QuotePdfClient(
        legal_name=(quote.client_name or "").strip() or "-",
        cnpj=format_cnpj(quote.cnpj) or quote.cnpj,
        email=(quote.client_email or "").strip(),
        phone="",
        street="",
        number="",
        complement="",
        district="",
        zip_code="",
        city="",
        state="",
    )


async def _load_tiflux_party(
    client: TifluxClient,
    client_id: int,
) -> tuple[dict, list[dict], list[dict]] | None:
    detail = await client.get_by_id(client_id, show_entities=False)
    if not detail or not isinstance(detail, dict):
        return None
    # show_entities=True wraps; ensure flat client
    if "client" in detail and isinstance(detail.get("client"), dict) and "id" not in detail:
        detail = detail["client"]
    addresses = await client.get_client_addresses(client_id)
    contacts = await client.get_client_contacts(client_id)
    return detail, addresses, contacts


async def resolve_issuer(settings: Settings | None = None) -> QuotePdfIssuer:
    """Emitente: TiFlux (issuer client / CNPJ) → merge com Settings fallback."""
    s = settings or get_settings()
    base = issuer_from_settings(s)
    if not s.tiflux_api_token:
        return base

    tiflux = TifluxClient(s)
    try:
        client_id = int(s.tiflux_issuer_client_id or 0)
        if client_id <= 0:
            found = await tiflux.find_by_cnpj(normalize_cnpj(s.quote_issuer_cnpj))
            if found and found.get("id") is not None:
                client_id = int(found["id"])
        if client_id <= 0:
            return base
        loaded = await _load_tiflux_party(tiflux, client_id)
        if not loaded:
            return base
        detail, addresses, contacts = loaded
    except (TifluxApiError, OSError, ValueError, TypeError) as exc:
        logger.warning("PDF emitente TiFlux indisponível; usando Settings. (%s)", exc)
        return base

    name = str(detail.get("name") or detail.get("social") or "").strip() or base.name
    cnpj_digits = normalize_cnpj(str(detail.get("social_revenue") or s.quote_issuer_cnpj))
    address_line = _format_address_row(addresses[0]) if addresses else ""
    phone, mobile = _pick_phones(contacts)
    email = _pick_email(contacts, base.email)
    return QuotePdfIssuer(
        name=name,
        cnpj=format_cnpj(cnpj_digits) or base.cnpj,
        address_line=address_line or base.address_line,
        phone=phone or base.phone,
        mobile=mobile or base.mobile,
        email=email or base.email,
        site=base.site,
    )


async def resolve_client(quote: QuoteRead, settings: Settings | None = None) -> QuotePdfClient:
    """Cliente do orçamento: TiFlux id → addresses/contacts; senão dados locais."""
    base = client_from_quote(quote)
    s = settings or get_settings()
    client_id = quote.tiflux_client_id
    if not client_id or not s.tiflux_api_token:
        return base

    tiflux = TifluxClient(s)
    try:
        loaded = await _load_tiflux_party(tiflux, int(client_id))
        if not loaded:
            return base
        detail, addresses, contacts = loaded
    except (TifluxApiError, OSError, ValueError, TypeError) as exc:
        logger.warning("PDF cliente TiFlux indisponível; usando quote local. (%s)", exc)
        return base

    addr = addresses[0] if addresses else {}
    phone, _mobile = _pick_phones(contacts)
    email = _pick_email(contacts, base.email)
    cnpj_digits = normalize_cnpj(str(detail.get("social_revenue") or quote.cnpj))
    legal = str(detail.get("social") or detail.get("name") or "").strip() or base.legal_name
    cep_raw = str(addr.get("cep") or "").strip()
    return QuotePdfClient(
        legal_name=legal,
        cnpj=format_cnpj(cnpj_digits) or base.cnpj,
        email=email or base.email,
        phone=phone or base.phone,
        street=str(addr.get("street") or "").strip(),
        number=str(addr.get("number") or "").strip(),
        complement=str(addr.get("complement") or "").strip(),
        district=str(addr.get("neighborhood") or "").strip(),
        zip_code=format_cep(cep_raw) if cep_raw else "",
        city=str(addr.get("city") or "").strip(),
        state=str(addr.get("state") or "").strip(),
        estadual_registration=str(detail.get("estadual_registration") or "").strip(),
    )


async def resolve_pdf_parties(
    quote: QuoteRead,
    settings: Settings | None = None,
) -> tuple[QuotePdfIssuer, QuotePdfClient]:
    s = settings or get_settings()
    issuer = await resolve_issuer(s)
    client = await resolve_client(quote, s)
    return issuer, client
