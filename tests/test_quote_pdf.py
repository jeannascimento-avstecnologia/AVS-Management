"""PDF de orçamento — layout SPEC_PDF_ORCAMENTO + labor só em mensalidade."""

from __future__ import annotations

import json
import re
import zlib
from pathlib import Path
from unittest.mock import MagicMock

from src.quotes.pdf import (
    _BAND_H,
    _GAP,
    _ROW_H,
    _ensure_space,
    _estimate_payment_summary_height,
    _estimate_section_height,
    quote_display_id,
    render_quote_pdf,
)
from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer
from src.quotes.schemas import QuoteItemRead, QuoteModule, QuoteRead
from src.quotes.totals import format_payment_plan_label


def _pdf_text(path: Path) -> str:
    data = path.read_bytes()
    chunks: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1)
        try:
            decoded = zlib.decompress(raw)
        except zlib.error:
            continue
        for lit in re.findall(rb"\((?:\\.|[^\\)])*\)", decoded):
            s = lit[1:-1].decode("latin-1", errors="replace")
            s = (
                s.replace(r"\n", "\n")
                .replace(r"\(", "(")
                .replace(r"\)", ")")
                .replace(r"\\", "\\")
            )
            if s.strip():
                chunks.append(s)
    return "\n".join(chunks)


def _issuer() -> QuotePdfIssuer:
    return QuotePdfIssuer(
        name="AVS TECNOLOGIA",
        cnpj="08.354.533/0001-83",
        address_line="Rua Teste, 70 Parque - Campinas - SP CEP: 13.087-240",
        phone="(19) 3243-9559",
        mobile="(19) 99656-6524",
        email="comercial@avstecnologia.cloud",
        site="https://avstecnologia.cloud/",
        ie="795.275.950.117",
    )


def _client() -> QuotePdfClient:
    return QuotePdfClient(
        legal_name="Cliente PDF LTDA",
        cnpj="11.222.333/0001-81",
        email="cliente@example.com",
        phone="(19) 99999-0000",
        street="Rua Cliente",
        number="10",
        complement="",
        district="Centro",
        zip_code="13000-000",
        city="Campinas",
        state="SP",
    )


def _sample_quote(*, quote_id: int = 2353) -> QuoteRead:
    return QuoteRead(
        id=quote_id,
        cnpj="11222333000181",
        client_name="Cliente PDF LTDA",
        tiflux_client_id=None,
        vhsys_client_id=None,
        status="draft",
        lead_temperature=None,
        billed_by_type="distribuidor",
        billed_by_name="Parceiro X",
        implant_payment_plan="a_vista",
        implant_discount_pct=None,
        implant_discount_value=None,
        implant_labor_hours=10.0,
        implant_labor_hourly_rate=100.0,
        monthly_payment_plan="parcelado_3x",
        monthly_discount_pct=None,
        monthly_discount_value=None,
        monthly_labor_hours=2.0,
        monthly_labor_hourly_rate=80.0,
        client_email="cliente@example.com",
        extra_recipients=[],
        notes="Forma de Pagamento Servicos: Boleto / Forma de Pagamento Produtos: Boleto Mensal",
        tiflux_ticket_number=None,
        vhsys_os_id=None,
        pdf_path=None,
        created_by=1,
        created_at="2026-07-20T12:00:00+00:00",
        updated_at="2026-07-20T12:00:00+00:00",
        submitted_at=None,
        sent_at=None,
        approved_at=None,
        modules=[
            QuoteModule(
                id="implantacao",
                title="Implantação",
                legacy_kind="implantacao",
                show_labor=False,
                payment_plan="a_vista",
                notes="Condicao implant",
                billed_by_name="Fornecedor Modulo",
                billed_by_cnpj="08354533000183",
                sort_order=0,
            ),
            QuoteModule(
                id="mensalidade",
                title="Mensalidade",
                legacy_kind="mensalidade",
                show_labor=True,
                payment_plan="recorrente_anual",
                labor_hours=2.0,
                labor_hourly_rate=80.0,
                sort_order=1,
            ),
        ],
        items=[
            QuoteItemRead(
                id=1,
                quote_id=quote_id,
                section="implantacao",
                name="Setup implant",
                qty=1,
                unit_value=1500.0,
                total_value=1500.0,
                sort_order=0,
            ),
            QuoteItemRead(
                id=2,
                quote_id=quote_id,
                section="mensalidade",
                name="Plano mensal",
                qty=1,
                unit_value=299.9,
                total_value=299.9,
                sort_order=0,
            ),
        ],
    )


def _multi_module_quote(*, extra_modules: int = 4, items_per: int = 5) -> QuoteRead:
    """Orçamento com vários módulos/itens — força 2ª página e stress no bloco pagamento."""
    base = _sample_quote()
    modules = list(base.modules)
    items = list(base.items)
    next_id = 3
    for i in range(extra_modules):
        mid = f"extra_{i}"
        modules.append(
            QuoteModule(
                id=mid,
                title=f"Extra Modulo {i + 1}",
                legacy_kind=None,
                show_labor=False,
                payment_plan="a_vista",
                sort_order=10 + i,
            )
        )
        for j in range(items_per):
            items.append(
                QuoteItemRead(
                    id=next_id,
                    quote_id=base.id,
                    section=mid,
                    name=f"Item extra {i + 1}-{j + 1}",
                    qty=1,
                    unit_value=50.0 + j,
                    total_value=50.0 + j,
                    sort_order=j,
                )
            )
            next_id += 1
    return base.model_copy(update={"modules": modules, "items": items, "notes": "Obs multi"})


def test_quote_display_id_prefix_m() -> None:
    assert quote_display_id(2353) == "M2353"
    assert quote_display_id(1) == "M1"


def test_format_payment_plan_label_recorrente_anual() -> None:
    assert format_payment_plan_label("recorrente_anual") == "Anual - Recorrente Mensal"
    assert format_payment_plan_label("recorrente_12x") == "Anual - Recorrente Mensal 12x"
    assert format_payment_plan_label("a_vista") == "À vista"
    assert format_payment_plan_label("12x") == "Parcelado 12x"
    assert format_payment_plan_label(None) == ""
    assert format_payment_plan_label("") == ""


def test_estimate_section_height_scales_with_items() -> None:
    empty = _estimate_section_height(
        [],
        discount_pct=None,
        discount_value=None,
        labor_hours=None,
        labor_rate=None,
        include_labor=False,
    )
    one = _estimate_section_height(
        [
            QuoteItemRead(
                id=1,
                quote_id=1,
                section="x",
                name="A",
                qty=1,
                unit_value=10,
                total_value=10,
                sort_order=0,
            )
        ],
        discount_pct=None,
        discount_value=None,
        labor_hours=None,
        labor_rate=None,
        include_labor=False,
    )
    # empty usa 1 row placeholder; one item = mesma altura base
    assert empty == one
    many_items = [
        QuoteItemRead(
            id=i,
            quote_id=1,
            section="x",
            name=f"I{i}",
            qty=1,
            unit_value=10,
            total_value=10,
            sort_order=i,
        )
        for i in range(5)
    ]
    many = _estimate_section_height(
        many_items,
        discount_pct=None,
        discount_value=None,
        labor_hours=None,
        labor_rate=None,
        include_labor=False,
    )
    assert abs(many - (one + 4 * _ROW_H)) < 1e-9
    assert many > _BAND_H + 5 * _ROW_H
    with_meta = _estimate_section_height(
        [],
        discount_pct=None,
        discount_value=None,
        labor_hours=None,
        labor_rate=None,
        include_labor=False,
        notes="Obs bloco",
        billed_by_name="Parceiro",
    )
    assert with_meta > empty


def test_estimate_payment_summary_height_grows_with_modules() -> None:
    implant = QuoteModule(
        id="implantacao",
        title="Implantação",
        legacy_kind="implantacao",
        show_labor=False,
        sort_order=0,
    )
    monthly = QuoteModule(
        id="mensalidade",
        title="Mensalidade",
        legacy_kind="mensalidade",
        show_labor=True,
        sort_order=1,
    )
    custom = QuoteModule(
        id="licencas",
        title="Licenças",
        legacy_kind=None,
        show_labor=False,
        sort_order=2,
    )
    two = _estimate_payment_summary_height([(implant, 1.0, 100.0), (monthly, 1.0, 200.0)])
    three = _estimate_payment_summary_height(
        [(implant, 1.0, 100.0), (monthly, 1.0, 200.0), (custom, 1.0, 50.0)]
    )
    assert three == two + _ROW_H
    assert two > _GAP + _BAND_H


def test_ensure_space_adds_page_near_bottom() -> None:
    pdf = MagicMock()
    pdf.h = 297.0
    pdf.t_margin = 9.0
    pdf.b_margin = 16.0
    pdf.get_y.return_value = 270.0  # perto do limiar 281
    assert _ensure_space(pdf, 20.0) is True
    pdf.add_page.assert_called_once()


def test_ensure_space_noop_when_fits() -> None:
    pdf = MagicMock()
    pdf.h = 297.0
    pdf.t_margin = 9.0
    pdf.b_margin = 16.0
    pdf.get_y.return_value = 100.0
    assert _ensure_space(pdf, 50.0) is False
    pdf.add_page.assert_not_called()


def test_ensure_space_allows_oversized_block() -> None:
    """Bloco > página útil: não pré-quebra (último recurso = split interno)."""
    pdf = MagicMock()
    pdf.h = 297.0
    pdf.t_margin = 9.0
    pdf.b_margin = 16.0
    pdf.get_y.return_value = 50.0
    usable = 297.0 - 9.0 - 16.0
    assert _ensure_space(pdf, usable + 10.0) is False
    pdf.add_page.assert_not_called()


def test_render_quote_pdf_layout_and_labor_rules(tmp_path: Path) -> None:
    dest = tmp_path / "quote.pdf"
    render_quote_pdf(_sample_quote(), dest, issuer=_issuer(), client=_client())
    assert dest.is_file()
    assert dest.read_bytes()[:4] == b"%PDF"

    text = _pdf_text(dest)
    assert "Orcamento : M2353" in text
    assert "Data:" in text
    assert "Ordem de servi" not in text.lower()
    assert "AVS TECNOLOGIA" in text
    assert "08.354.533/0001-83" in text
    assert "DADOS DO CLIENTE" not in text
    assert "Os valores podem sofrer alteracao sem previo aviso" in text
    assert "Ticket no." in text
    assert "comercial@avstecnologia.cloud" in text
    assert "Rua Teste, 70 Parque" in text
    assert " |?" not in text
    assert "?|" not in text
    assert "avstecnologia.cloud" in text
    assert "795.275.950.117" in text
    assert "IMPLANTACAO" in text
    assert "MENSALIDADE" in text
    assert "Assinatura do Prestador" in text
    assert "Assinatura do Sacado" in text
    assert "Data do aceite" in text
    # Mão de obra mensalidade (2h × 80 = 160)
    assert "Horas: 2" in text
    assert "160,00" in text or "R$ 160,00" in text
    # Implantação NÃO deve refletir 10h × 100 (mesmo com campos preenchidos no model)
    assert "Horas: 10" not in text
    assert "1.000,00" not in text and "1000,00" not in text
    # Dados de pagamento (qtde + valores) + observações
    assert "TOTAL DE HORAS/QTDE DE SERVICOS" in text
    assert "VALOR TOTAL DOS SERVICOS" in text
    assert "TOTAL DE PRODUTOS" in text
    assert "VALOR TOTAL DOS PRODUTOS" in text
    assert "VALOR TOTAL DO ORCAMENTO" in text
    assert "OBSERVACOES" in text
    assert "QTDE" in text
    assert "QTDADE" not in text
    assert "Desconto 0%" not in text
    assert "Forma de Pagamento Servicos" in text
    assert "Observacoes" in text
    assert "Condicao implant" in text
    assert "Anual - Recorrente Mensal" in text
    assert "Faturado por" in text
    assert "Fornecedor Modulo" in text
    assert "Parceiro X" not in text
    assert "1.500,00" in text or "1500,00" in text
    assert "459,90" in text
    assert "1.959,90" in text or "1959,90" in text

    from pypdf import PdfReader

    assert len(PdfReader(str(dest)).pages) == 1


def test_pdf_simplified_module_hides_line_names(tmp_path: Path) -> None:
    dest = tmp_path / "simple.pdf"
    quote = _sample_quote().model_copy(
        update={
            "modules": [
                QuoteModule(
                    id="licencas",
                    title="Licenças",
                    simplified=True,
                    display_name="Pacote Office",
                    sort_order=0,
                )
            ]
        }
    )
    quote = quote.model_copy(
        update={
            "items": [
                QuoteItemRead(
                    id=1,
                    quote_id=quote.id,
                    section="licencas",
                    name="Item Secreto XYZ",
                    qty=1,
                    unit_value=100,
                    total_value=100,
                    sort_order=0,
                )
            ]
        }
    )
    render_quote_pdf(quote, dest, issuer=_issuer(), client=_client())
    text = _pdf_text(dest)
    assert "Pacote Office" in text
    assert "Item Secreto XYZ" not in text
    assert "ITEM" in text
    assert "QTDE" in text
    assert "QTDADE" not in text
    assert "V. UNIT." in text
    assert "V. TOTAL" in text


def test_pdf_payment_block_not_split_across_pages(tmp_path: Path) -> None:
    """Com vários módulos, DADOS DE PAGAMENTO começa numa página e fecha nela."""
    dest = tmp_path / "multi.pdf"
    quote = _multi_module_quote(extra_modules=4, items_per=6)
    render_quote_pdf(quote, dest, issuer=_issuer(), client=_client())

    from pypdf import PdfReader

    reader = PdfReader(str(dest))
    assert len(reader.pages) >= 2

    payment_pages = [
        i
        for i, page in enumerate(reader.pages)
        if "DADOS DE PAGAMENTO" in (page.extract_text() or "")
    ]
    total_pages = [
        i
        for i, page in enumerate(reader.pages)
        if "VALOR TOTAL DO ORCAMENTO" in (page.extract_text() or "")
    ]
    assert payment_pages, "banda DADOS DE PAGAMENTO ausente"
    assert total_pages, "VALOR TOTAL DO ORCAMENTO ausente"
    # Bloco inteiro na mesma página (keep-together)
    assert payment_pages[0] == total_pages[0]


def test_pdf_omits_removed_implantacao_and_follows_order(tmp_path: Path) -> None:
    dest = tmp_path / "quote-reorder.pdf"
    quote = _sample_quote()
    quote = quote.model_copy(
        update={
            "modules": [
                QuoteModule(
                    id="mensalidade",
                    title="Mensalidade",
                    legacy_kind="mensalidade",
                    show_labor=True,
                    labor_hours=2.0,
                    labor_hourly_rate=80.0,
                    sort_order=0,
                ),
                QuoteModule(
                    id="licencas",
                    title="Licenças",
                    legacy_kind=None,
                    show_labor=False,
                    payment_plan="a_vista",
                    sort_order=1,
                ),
            ],
            "items": [
                QuoteItemRead(
                    id=2,
                    quote_id=2353,
                    section="mensalidade",
                    name="Plano mensal",
                    qty=1,
                    unit_value=299.9,
                    total_value=299.9,
                    sort_order=0,
                ),
                QuoteItemRead(
                    id=3,
                    quote_id=2353,
                    section="licencas",
                    name="Office",
                    qty=1,
                    unit_value=100.0,
                    total_value=100.0,
                    sort_order=0,
                ),
            ],
            "implant_payment_plan": None,
            "implant_discount_pct": None,
            "implant_discount_value": None,
        }
    )
    render_quote_pdf(quote, dest, issuer=_issuer(), client=_client())
    text = _pdf_text(dest)
    assert "IMPLANTACAO" not in text
    assert "MENSALIDADE" in text
    assert "LICENCAS" in text or "LICENÇAS" in text or "Licenc" in text
    assert "TOTAL DE HORAS/QTDE DE SERVICOS" not in text
    assert "TOTAL DE PRODUTOS" in text
    assert "VALOR TOTAL DO ORCAMENTO" in text


def test_pdf_legacy_without_modules_synthesizes_seed(tmp_path: Path) -> None:
    dest = tmp_path / "legacy.pdf"
    quote = _sample_quote().model_copy(update={"modules": []})
    render_quote_pdf(
        quote,
        dest,
        issuer=QuotePdfIssuer(
            name="AVS TECNOLOGIA",
            cnpj="08.354.533/0001-83",
            address_line="Rua",
            phone="",
            mobile="",
            email="",
            site="",
        ),
        client=QuotePdfClient(
            legal_name="C",
            cnpj="11.222.333/0001-81",
            email="",
            phone="",
            street="",
            number="",
            complement="",
            district="",
            zip_code="",
            city="",
            state="",
        ),
    )
    text = _pdf_text(dest)
    assert "IMPLANTACAO" not in text
    assert "MENSALIDADE" not in text
    assert "Ticket no." in text


def test_pdf_header_version_and_monthly_outside_total(tmp_path: Path) -> None:
    dest = tmp_path / "monthly.pdf"
    quote = _sample_quote()
    draft = {
        "allocations": [
            {
                "item_id": 2,
                "fornecedor_name": "Fornecedor",
                "fornecedor_amount": 200.0,
                "intermediador_name": "Intermediador",
                "intermediador_amount": 99.9,
            }
        ],
    }
    render_quote_pdf(
        quote,
        dest,
        issuer=_issuer(),
        client=_client(),
        version_number=3,
        monthly_draft_json=json.dumps(draft),
    )
    text = _pdf_text(dest)
    assert "v3" in text
    assert "MENSALIDADES" in text
    assert "Plano mensal" in text
    assert "Fornecedor" in text
    assert "Intermediador" in text
    assert "VALOR TOTAL DO ORCAMENTO" in text
    assert "1.660,00" in text or "1660,00" in text
    assert "1.959,90" not in text and "1959,90" not in text


def test_pdf_monthly_omits_zero_party_amount(tmp_path: Path) -> None:
    dest = tmp_path / "monthly-zero.pdf"
    quote = _sample_quote()
    draft = {
        "allocations": [
            {
                "item_id": 2,
                "fornecedor_name": "Fornecedor",
                "fornecedor_amount": 299.9,
                "intermediador_name": "Intermediador",
                "intermediador_amount": 0.0,
            }
        ],
    }
    render_quote_pdf(
        quote,
        dest,
        issuer=_issuer(),
        client=_client(),
        monthly_draft_json=json.dumps(draft),
    )
    text = _pdf_text(dest)
    assert "Plano mensal" in text
    assert "Fornecedor" in text
    assert "Intermediador" not in text


def test_pdf_shows_discount_only_when_applied(tmp_path: Path) -> None:
    dest = tmp_path / "discount.pdf"
    quote = _sample_quote()
    mods = list(quote.modules)
    mods[0] = mods[0].model_copy(update={"discount_pct": 10.0})
    quote = quote.model_copy(update={"modules": mods})
    render_quote_pdf(quote, dest, issuer=_issuer(), client=_client())
    text = _pdf_text(dest)
    assert "Desconto" in text
    assert "Aplicado" in text
