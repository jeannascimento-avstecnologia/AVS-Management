from src.mapping.canonical import CompanyPayload


def to_tiflux_payload(
    company: CompanyPayload,
    *,
    desk_ids: list[int] | None = None,
    technical_group_ids: list[int] | None = None,
) -> dict:
    payload: dict = {
        "name": company.trade_name,
        "social": company.legal_name,
        "social_revenue": company.cnpj_digits,
        "status": company.status_active,
    }
    if desk_ids:
        payload["desk_ids"] = desk_ids
    if technical_group_ids:
        payload["technical_group_ids"] = technical_group_ids
    return payload

