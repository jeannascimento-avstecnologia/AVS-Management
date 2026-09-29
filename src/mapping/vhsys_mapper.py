from src.cnpj.validator import format_cnpj, format_cpf
from src.mapping.canonical import CompanyPayload


def to_vhsys_payload(company: CompanyPayload) -> dict:
    person = "PF" if str(company.person_type or "PJ").upper() == "PF" else "PJ"
    document = company.cnpj_formatted
    if not document and company.cnpj_digits:
        document = format_cpf(company.cnpj_digits) if person == "PF" else format_cnpj(company.cnpj_digits)
    payload: dict = {
        "razao_cliente": company.legal_name,
        "tipo_pessoa": person,
        "tipo_cadastro": "Cliente",
        "cnpj_cliente": document,
        "fantasia_cliente": company.trade_name,
        "situacao_cliente": "Ativo" if company.status_active else "Inativo",
    }

    addr = company.address
    if addr.street:
        payload["endereco_cliente"] = addr.street
    if addr.number:
        payload["numero_cliente"] = addr.number
    if addr.district:
        payload["bairro_cliente"] = addr.district
    if addr.complement:
        payload["complemento_cliente"] = addr.complement
    if addr.zip_code:
        payload["cep_cliente"] = addr.zip_code
    if addr.city:
        payload["cidade_cliente"] = addr.city
    if addr.state:
        payload["uf_cliente"] = addr.state
    if company.phone:
        payload["fone_cliente"] = company.phone
    if company.email:
        payload["email_cliente"] = company.email

    return payload
