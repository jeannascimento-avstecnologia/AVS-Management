from src.mapping.canonical import CompanyPayload


def to_vhsys_payload(company: CompanyPayload) -> dict:
    payload: dict = {
        "razao_cliente": company.legal_name,
        "tipo_pessoa": "PJ",
        "tipo_cadastro": "Cliente",
        "cnpj_cliente": company.cnpj_formatted,
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
