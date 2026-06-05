import re
from dataclasses import dataclass, field
from typing import Any

from src.cnpj.validator import format_cnpj, normalize_cnpj


@dataclass
class Address:
    street: str = ""
    number: str = ""
    complement: str = ""
    district: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""


@dataclass
class CompanyPayload:
    cnpj_digits: str
    cnpj_formatted: str
    legal_name: str
    trade_name: str
    address: Address = field(default_factory=Address)
    phone: str = ""
    email: str = ""
    status_active: bool = True
    registration_status: str = ""
    cnae_fiscal: int | None = None
    cnae_description: str = ""


def format_cep(digits: str) -> str:
    d = re.sub(r"\D", "", digits or "")
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return digits or ""


SITUACAO_CADASTRAL_LABELS: dict[int, str] = {
    1: "NULA",
    2: "ATIVA",
    3: "SUSPENSA",
    4: "INAPTA",
    8: "BAIXADA",
}


def extract_registration_status(data: dict) -> str:
    desc = (data.get("descricao_situacao_cadastral") or "").strip().upper()
    if desc:
        return desc

    code = data.get("situacao_cadastral")
    if code is not None:
        try:
            return SITUACAO_CADASTRAL_LABELS.get(int(code), f"CÓDIGO {int(code)}")
        except (TypeError, ValueError):
            pass
    return ""


def format_phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return raw or ""


def from_brasilapi(data: dict) -> CompanyPayload:
    cnpj_digits = normalize_cnpj(data.get("cnpj", ""))
    legal_name = (data.get("razao_social") or "").strip()
    trade_name = (data.get("nome_fantasia") or "").strip() or legal_name
    situacao = extract_registration_status(data)

    return CompanyPayload(
        cnpj_digits=cnpj_digits,
        cnpj_formatted=format_cnpj(cnpj_digits),
        legal_name=legal_name,
        trade_name=trade_name,
        address=Address(
            street=(data.get("logradouro") or "").strip(),
            number=(data.get("numero") or "").strip(),
            complement=(data.get("complemento") or "").strip(),
            district=(data.get("bairro") or "").strip(),
            city=(data.get("municipio") or "").strip(),
            state=(data.get("uf") or "").strip(),
            zip_code=format_cep(data.get("cep") or ""),
        ),
        phone=format_phone(data.get("ddd_telefone_1") or ""),
        email=(data.get("email") or "").strip() if data.get("email") else "",
        status_active=situacao == "ATIVA",
        registration_status=situacao,
        cnae_fiscal=data.get("cnae_fiscal"),
        cnae_description=(data.get("cnae_fiscal_descricao") or "").strip(),
    )


def company_to_dict(company: CompanyPayload) -> dict[str, Any]:
    return {
        "cnpj_digits": company.cnpj_digits,
        "cnpj_formatted": company.cnpj_formatted,
        "legal_name": company.legal_name,
        "trade_name": company.trade_name,
        "address": {
            "street": company.address.street,
            "number": company.address.number,
            "complement": company.address.complement,
            "district": company.address.district,
            "city": company.address.city,
            "state": company.address.state,
            "zip_code": company.address.zip_code,
        },
        "phone": company.phone,
        "email": company.email,
        "status_active": company.status_active,
        "registration_status": company.registration_status,
        "cnae_fiscal": company.cnae_fiscal,
        "cnae_description": company.cnae_description,
    }


def company_from_dict(data: dict[str, Any]) -> CompanyPayload:
    digits = normalize_cnpj(str(data.get("cnpj_digits") or data.get("cnpj") or ""))
    addr = data.get("address") or {}
    if not isinstance(addr, dict):
        addr = {}

    status = data.get("status_active", True)
    if isinstance(status, str):
        status = status.lower() in ("true", "1", "on", "yes", "ativo")

    return CompanyPayload(
        cnpj_digits=digits,
        cnpj_formatted=format_cnpj(digits) if digits else str(data.get("cnpj_formatted") or ""),
        legal_name=str(data.get("legal_name") or "").strip(),
        trade_name=str(data.get("trade_name") or "").strip(),
        address=Address(
            street=str(addr.get("street") or "").strip(),
            number=str(addr.get("number") or "").strip(),
            complement=str(addr.get("complement") or "").strip(),
            district=str(addr.get("district") or "").strip(),
            city=str(addr.get("city") or "").strip(),
            state=str(addr.get("state") or "").strip(),
            zip_code=str(addr.get("zip_code") or "").strip(),
        ),
        phone=str(data.get("phone") or "").strip(),
        email=str(data.get("email") or "").strip(),
        status_active=bool(status),
        registration_status=str(data.get("registration_status") or "").strip().upper(),
        cnae_fiscal=data.get("cnae_fiscal"),
        cnae_description=str(data.get("cnae_description") or "").strip(),
    )

