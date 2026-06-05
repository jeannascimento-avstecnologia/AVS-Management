from src.mapping.canonical import extract_registration_status, from_brasilapi
from src.mapping.tiflux_mapper import to_tiflux_payload
from src.mapping.vhsys_mapper import to_vhsys_payload


BRASILAPI_SAMPLE = {
    "cnpj": "19131243000197",
    "razao_social": "OPEN KNOWLEDGE BRASIL",
    "nome_fantasia": "REDE PELO CONHECIMENTO LIVRE",
    "cep": "01311902",
    "logradouro": "PAULISTA 37",
    "numero": "37",
    "complemento": "ANDAR 4",
    "bairro": "BELA VISTA",
    "municipio": "SAO PAULO",
    "uf": "SP",
    "ddd_telefone_1": "1123851939",
    "email": None,
    "descricao_situacao_cadastral": "ATIVA",
}


def test_extract_registration_status_from_code():
    assert extract_registration_status({"situacao_cadastral": 2}) == "ATIVA"
    assert extract_registration_status({"situacao_cadastral": 8}) == "BAIXADA"


def test_from_brasilapi_active():
    company = from_brasilapi(BRASILAPI_SAMPLE)
    assert company.cnpj_digits == "19131243000197"
    assert company.status_active is True
    assert company.trade_name == "REDE PELO CONHECIMENTO LIVRE"


def test_tiflux_mapper():
    company = from_brasilapi(BRASILAPI_SAMPLE)
    payload = to_tiflux_payload(company)
    assert payload["social_revenue"] == "19131243000197"
    assert payload["social"] == "OPEN KNOWLEDGE BRASIL"
    assert payload["status"] is True


def test_vhsys_mapper():
    company = from_brasilapi(BRASILAPI_SAMPLE)
    payload = to_vhsys_payload(company)
    assert payload["tipo_pessoa"] == "PJ"
    assert payload["razao_cliente"] == "OPEN KNOWLEDGE BRASIL"
    assert payload["cep_cliente"] == "01311-902"
    assert payload["situacao_cliente"] == "Ativo"
