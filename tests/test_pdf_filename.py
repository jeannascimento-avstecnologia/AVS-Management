from __future__ import annotations

from urllib.parse import unquote

from src.quotes.pdf_filename import quote_pdf_download_name
from src.quotes.schemas import QUOTE_TEMPLATE_PLACEHOLDER_CNPJ, QUOTE_TEMPLATE_PLACEHOLDER_NAME


def test_download_name_omits_empty_and_v1() -> None:
    name = quote_pdf_download_name(
        quote_id=12,
        client_name="AVS Teste LTDA",
        title=None,
        version_number=1,
    )
    assert name.utf8 == "Orçamento M12 - AVS Teste LTDA.pdf"
    assert name.ascii_fallback == "Orcamento-M12.pdf"
    cd = name.content_disposition()
    assert 'filename="Orcamento-M12.pdf"' in cd
    assert "filename*=UTF-8''" in cd
    encoded = cd.split("filename*=UTF-8''", 1)[1]
    assert unquote(encoded) == name.utf8


def test_download_name_includes_v2_and_title() -> None:
    name = quote_pdf_download_name(
        quote_id=3,
        client_name="Cliente / SA",
        title="Proposta Alpha",
        version_number=2,
    )
    assert name.utf8 == "Orçamento M3 - Cliente SA - Proposta Alpha - v2.pdf"


def test_download_name_skips_template_placeholder_client() -> None:
    name = quote_pdf_download_name(
        quote_id=9,
        client_name=QUOTE_TEMPLATE_PLACEHOLDER_NAME,
        title="Pacote M365",
        cnpj=QUOTE_TEMPLATE_PLACEHOLDER_CNPJ,
        version_number=None,
    )
    assert name.utf8 == "Orçamento M9 - Pacote M365.pdf"
