"""Geração local de PDF de orçamento — layout espelhando OS VHSYS (SPEC_PDF_ORCAMENTO).

Acabamento visual Aurora (textura, barras, tabelas) sem alterar estrutura/organização.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import unicodedata

from fpdf import FPDF

from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer, client_from_quote, issuer_from_settings
from src.quotes.schemas import QuoteItemRead, QuoteModule, QuoteRead
from src.quotes.totals import (
    apply_section_discount,
    format_payment_plan_label,
    labor_total,
    round_money,
)

# Aurora / AVS (RGB) — azul + vermelho da logo (sem roxo; P&B: fills escuros → cinza legível)
_NAVY = (12, 30, 58)
_BLUE = (26, 79, 140)
_ACCENT = (43, 143, 217)
_BRAND_RED = (220, 38, 38)  # logo A / aurora-brand-red #dc2626
_BRAND_RED_DARK = (185, 28, 28)  # fills de seção (melhor em grayscale)
_INK = (30, 41, 59)
_MUTED = (100, 116, 139)
_RULE = (148, 163, 184)  # divisores
_BOX_BORDER = (71, 85, 105)  # slate-600 — bordas de caixas
_ROW_ALT = (241, 245, 249)
_PANEL = (255, 255, 255)  # branco sólido — destaca do fundo
_PAGE = (252, 253, 255)
_WHITE = (255, 255, 255)
_BOX_LINE = 0.4

_LOGO_PATH = Path(__file__).resolve().parents[1] / "cropped-AVS-SemArco-Colorido_2024.png"
# Grade tipográfica / geometria (tudo alinhado à mesma largura útil)
_CONTENT_W = 188.0
_FS_TITLE = 13.0
_FS_SECTION = 9.0
_FS_BODY = 8.0
_FS_SMALL = 7.5
_FS_MUTED = 7.0
_ROW_H = 5.0
_BAND_H = 5.6
_GAP = 0.7
_COL_ITEM = 98.0
_COL_QTY = 24.0
_COL_UNIT = 33.0
_COL_TOTAL = 33.0  # 98+24+33+33 = 188
_LABEL_W = _CONTENT_W - _COL_TOTAL


def quote_display_id(quote_id: int) -> str:
    """ID impresso: prefixo M + quotes.id (ex. M2353)."""
    return f"M{int(quote_id)}"


def _brl(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def _qty(value: float) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(text: str | None) -> str:
    if not text:
        return "-"
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _dash(text: str | None) -> str:
    cleaned = (text or "").strip()
    return _safe(cleaned) if cleaned else "-"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "-"
    raw = iso.strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return f"{raw[8:10]}/{raw[5:7]}/{raw[0:4]}"
        return _safe(raw[:10])


def _set_box_stroke(pdf: FPDF) -> None:
    """Borda evidente para células/painéis."""
    pdf.set_draw_color(*_BOX_BORDER)
    pdf.set_line_width(_BOX_LINE)


def _section_accent(module: QuoteModule, index: int) -> tuple[int, int, int]:
    """Mensalidade (legacy) = vermelho; demais alternam azul / vermelho escuro."""
    if module.legacy_kind == "mensalidade" or module.id == "mensalidade":
        return _BRAND_RED_DARK
    if module.legacy_kind == "implantacao" or module.id == "implantacao":
        return _BLUE
    return _BRAND_RED_DARK if index % 2 == 1 else _BLUE


def _module_band_title(module: QuoteModule) -> str:
    title = (module.title or module.id).strip()
    # ASCII-safe for Helvetica/latin-1 (ç→c, ã→a, …)
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_title = ascii_title.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_title.upper() or module.id.upper()


def _ordered_modules(quote: QuoteRead) -> list[QuoteModule]:
    if quote.modules:
        return sorted(quote.modules, key=lambda m: (m.sort_order, m.id))
    # Legado sem modules: sintetiza a partir das colunas flat
    from src.quotes.schemas import seed_default_modules

    seeded = seed_default_modules()
    out: list[QuoteModule] = []
    for mod in seeded:
        if mod.legacy_kind == "implantacao":
            out.append(
                mod.model_copy(
                    update={
                        "payment_plan": quote.implant_payment_plan,
                        "discount_pct": quote.implant_discount_pct,
                        "discount_value": quote.implant_discount_value,
                    }
                )
            )
        elif mod.legacy_kind == "mensalidade":
            out.append(
                mod.model_copy(
                    update={
                        "payment_plan": quote.monthly_payment_plan,
                        "discount_pct": quote.monthly_discount_pct,
                        "discount_value": quote.monthly_discount_value,
                        "labor_hours": quote.monthly_labor_hours,
                        "labor_hourly_rate": quote.monthly_labor_hourly_rate,
                    }
                )
            )
    return out


class _QuotePdf(FPDF):
    """A4 com fundo liso, barras de marca e rodapé tipográfico."""

    def header(self) -> None:
        # Fundo suave (papel)
        self.set_fill_color(*_PAGE)
        self.rect(0, 0, self.w, self.h, style="F")

        # Barra superior marca (navy + accent)
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, self.w, 3.2, style="F")
        self.set_fill_color(*_ACCENT)
        self.rect(0, 3.2, self.w, 1.1, style="F")

        # Faixa lateral sutil
        self.set_fill_color(*_ACCENT)
        self.rect(0, 0, 1.4, self.h, style="F")

        self.set_draw_color(0, 0, 0)
        self.set_text_color(*_INK)
        self.set_xy(self.l_margin, self.t_margin)

    def footer(self) -> None:
        self.set_y(-12)
        y = self.get_y()
        self.set_draw_color(*_RULE)
        self.set_line_width(0.25)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.set_y(y + 1.0)
        self.set_font("Helvetica", "I", _FS_MUTED)
        self.set_text_color(*_MUTED)
        self.cell(0, 4.5, f"Pagina {self.page_no()}/{{nb}}  ·  AVS Tecnologia", align="C")
        self.set_text_color(*_INK)


def _section_net_total(
    items: list[QuoteItemRead],
    *,
    discount_pct: float | None,
    discount_value: float | None,
    labor_hours: float | None = None,
    labor_rate: float | None = None,
    include_labor: bool = False,
) -> float:
    """Total líquido da seção (itens + mão de obra opcional − desconto)."""
    items_total = sum(float(i.total_value) for i in items)
    labor = labor_total(labor_hours, labor_rate) if include_labor else 0.0
    subtotal = round_money(items_total + labor)
    _, net = apply_section_discount(subtotal, discount_pct, discount_value)
    return net


def _section_qty_total(items: list[QuoteItemRead]) -> float:
    return round(sum(float(i.qty) for i in items), 2)


def _page_break_y(pdf: FPDF) -> float:
    """Y a partir do qual o fpdf dispara auto page-break (h − b_margin)."""
    return float(pdf.h) - float(pdf.b_margin)


def _usable_page_height(pdf: FPDF) -> float:
    """Área útil vertical de uma página (entre top e bottom margin)."""
    return float(pdf.h) - float(pdf.t_margin) - float(pdf.b_margin)


def _ensure_space(pdf: FPDF, needed: float) -> bool:
    """Garante espaço para um bloco inteiro; retorna True se adicionou página.

    Preferência: keep-together. Se o bloco for maior que uma página útil,
    não pré-quebra (auto_page_break interno como último recurso).
    """
    if needed <= 0:
        return False
    usable = _usable_page_height(pdf)
    if needed > usable:
        return False
    if pdf.get_y() + needed > _page_break_y(pdf):
        pdf.add_page()
        return True
    return False


def _divider_height() -> float:
    """Altura de `_write_divider` (ln + rule + gap_after)."""
    return _GAP + (_GAP * 2)


def _module_meta_height(notes: str | None, billed_by_name: str | None) -> float:
    """Altura extra de observações / faturado por no módulo (só se preenchidos)."""
    h = 0.0
    notes_clean = (notes or "").strip()
    billed_clean = (billed_by_name or "").strip()
    if notes_clean:
        lines = max(1, (len(notes_clean) + 89) // 90)
        h += _GAP + 3.6 + lines * 4.0
    if billed_clean:
        h += _GAP + 4.0
    return h


def _estimate_section_height(
    items: list[QuoteItemRead],
    *,
    discount_pct: float | None,
    discount_value: float | None,
    labor_hours: float | None,
    labor_rate: float | None,
    include_labor: bool,
    notes: str | None = None,
    billed_by_name: str | None = None,
) -> float:
    """Altura estimada de `_write_section` (banda → total líquido + gap final)."""
    h = _BAND_H + _GAP  # section band
    h += _ROW_H  # header ITEM/QTDE/...
    h += max(1, len(items)) * _ROW_H  # rows or "(sem itens)"

    labor = 0.0
    if include_labor:
        labor = labor_total(labor_hours, labor_rate)
        if labor > 0:
            h += _GAP + 3.6 + _ROW_H  # "Mao de obra" label + row

    items_total = sum(float(i.total_value) for i in items)
    section_subtotal = round_money(items_total + labor)
    discount, _net = apply_section_discount(section_subtotal, discount_pct, discount_value)

    h += _GAP + 3.6 + _ROW_H  # Desconto / Pagamento
    h += _GAP + _ROW_H  # subtotal
    if discount > 0:
        h += _ROW_H
    h += (_ROW_H + 0.6) + _GAP  # TOTAL LIQUIDO + ln
    h += _module_meta_height(notes, billed_by_name)
    return h


def _payment_summary_row_count(module_nets: list[tuple[QuoteModule, float, float]]) -> int:
    implant = any(m.legacy_kind == "implantacao" for m, _q, _n in module_nets)
    monthly = any(m.legacy_kind == "mensalidade" for m, _q, _n in module_nets)
    customs = sum(
        1 for m, _q, _n in module_nets if m.legacy_kind not in ("implantacao", "mensalidade")
    )
    if implant and monthly:
        return 2 + customs
    if implant:
        return 1 + (len(module_nets) - 1)  # implant pair + demais
    if monthly:
        return 1 + (len(module_nets) - 1)
    return len(module_nets)


def _estimate_payment_summary_height(
    module_nets: list[tuple[QuoteModule, float, float]],
) -> float:
    """Altura estimada de `_write_payment_summary`."""
    h = _GAP + _BAND_H + _GAP
    h += _payment_summary_row_count(module_nets) * _ROW_H
    h += (_ROW_H + 0.8) + _GAP  # VALOR TOTAL + ln
    return h


def _estimate_observations_height(notes: str | None) -> float:
    text = (notes or "").strip() or "-"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    clipped = "\n".join(lines[:4])
    if len(clipped) > 480:
        clipped = clipped[:477] + "..."
    line_h = 3.6
    n_lines = max(1, clipped.count("\n") + 1)
    box_h = max(_ROW_H * 2, n_lines * line_h + 2.4)
    return _BAND_H + _GAP + box_h + _GAP


def _estimate_signatures_height() -> float:
    """Altura do bloco de assinaturas (sem empurrar para o rodapé)."""
    return _GAP + 5.0 + 1.5 + 4.0 + 3.0  # ln + rule gap + offset + labels + ln


def render_quote_pdf(
    quote: QuoteRead,
    dest: Path,
    *,
    issuer: QuotePdfIssuer | None = None,
    client: QuotePdfClient | None = None,
) -> None:
    """Grava PDF do orçamento em `dest` (arquivo já resolvido sob HUB_PDF_DIR)."""
    issuer = issuer or issuer_from_settings()
    client = client or client_from_quote(quote)

    pdf = _QuotePdf(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(11, 9, 11)
    pdf.add_page()

    _write_header(pdf, quote, issuer)
    _write_client_block(pdf, quote, client)

    modules = _ordered_modules(quote)
    module_nets: list[tuple[QuoteModule, float, float]] = []  # mod, qty, net

    for idx, mod in enumerate(modules):
        mod_items = [i for i in quote.items if i.section == mod.id]
        include_labor = bool(mod.show_labor)
        section_h = _estimate_section_height(
            mod_items,
            discount_pct=mod.discount_pct,
            discount_value=mod.discount_value,
            labor_hours=mod.labor_hours if include_labor else None,
            labor_rate=mod.labor_hourly_rate if include_labor else None,
            include_labor=include_labor,
            notes=mod.notes,
            billed_by_name=mod.billed_by_name,
        )
        if idx > 0:
            section_h += _divider_height()
        _ensure_space(pdf, section_h)
        if idx > 0:
            _write_divider(pdf)
        _write_section(
            pdf,
            title=_module_band_title(mod),
            accent=_section_accent(mod, idx),
            items=mod_items,
            payment_plan=mod.payment_plan,
            discount_pct=mod.discount_pct,
            discount_value=mod.discount_value,
            labor_hours=mod.labor_hours if include_labor else None,
            labor_rate=mod.labor_hourly_rate if include_labor else None,
            include_labor=include_labor,
            notes=mod.notes,
            billed_by_name=mod.billed_by_name,
        )
        net = _section_net_total(
            mod_items,
            discount_pct=mod.discount_pct,
            discount_value=mod.discount_value,
            labor_hours=mod.labor_hours,
            labor_rate=mod.labor_hourly_rate,
            include_labor=include_labor,
        )
        module_nets.append((mod, _section_qty_total(mod_items), net))

    _ensure_space(pdf, _estimate_payment_summary_height(module_nets))
    _write_payment_summary(pdf, module_nets=module_nets)

    _ensure_space(pdf, _estimate_observations_height(quote.notes))
    _write_observations(pdf, quote.notes)

    if quote.billed_by_type or quote.billed_by_name:
        billed_h = _GAP + 4.0
        _ensure_space(pdf, billed_h + _estimate_signatures_height())
        pdf.ln(_GAP)
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.set_text_color(*_MUTED)
        billed = f"{_dash(quote.billed_by_type)} - {_dash(quote.billed_by_name)}"
        pdf.cell(0, 4, f"Faturado por: {_safe(billed)}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)
    else:
        _ensure_space(pdf, _estimate_signatures_height())

    _write_signatures(pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(dest))


def _write_header(pdf: _QuotePdf, quote: QuoteRead, issuer: QuotePdfIssuer) -> None:
    top_y = pdf.get_y()
    logo_w = 24.0
    logo_h = 17.0
    text_x = pdf.l_margin + logo_w + 3.0

    if _LOGO_PATH.is_file():
        pdf.image(str(_LOGO_PATH), x=pdf.l_margin, y=top_y, w=logo_w)
    else:
        text_x = pdf.l_margin

    pdf.set_xy(text_x, top_y)
    pdf.set_font("Helvetica", "B", _FS_TITLE)
    pdf.set_text_color(*_NAVY)
    pdf.cell(
        0,
        5.8,
        _safe(f"Orcamento : {quote_display_id(quote.id)}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.set_text_color(*_BLUE)
    pdf.cell(
        0,
        4.0,
        _safe(f"{issuer.name} - {issuer.cnpj}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_font("Helvetica", "", _FS_SMALL)
    pdf.set_text_color(*_MUTED)
    if issuer.address_line:
        pdf.set_x(text_x)
        pdf.multi_cell(pdf.w - pdf.r_margin - text_x, 3.4, _safe(issuer.address_line))

    contact_bits = [
        f"Telefone: {_safe(issuer.phone)}" if issuer.phone else "",
        f"Celular: {_safe(issuer.mobile)}" if issuer.mobile else "",
        f"E-mail: {_safe(issuer.email)}" if issuer.email else "",
        f"Site: {_safe(issuer.site)}" if issuer.site else "",
    ]
    contact_line = "  |  ".join(b for b in contact_bits if b)
    if contact_line:
        pdf.set_x(text_x)
        pdf.multi_cell(pdf.w - pdf.r_margin - text_x, 3.4, contact_line)

    pdf.set_text_color(*_INK)
    content_y = max(pdf.get_y(), top_y + logo_h)
    pdf.set_y(content_y + _GAP)
    _rule(pdf, color=_ACCENT, width=0.45)


def _write_client_block(pdf: _QuotePdf, quote: QuoteRead, client: QuotePdfClient) -> None:
    _section_band(pdf, "DADOS DO CLIENTE", _NAVY)
    pdf.set_font("Helvetica", "", _FS_MUTED)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        3.6,
        f"DATA: {_fmt_date(quote.updated_at or quote.created_at)}",
        align="R",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(*_INK)

    panel_top = pdf.get_y()
    left_w = _CONTENT_W / 2.0
    right_w = _CONTENT_W - left_w
    label_l, label_r = 28.0, 22.0
    rows: list[tuple[str, str, str, str]] = [
        ("Razao Social:", client.legal_name, "CNPJ:", client.cnpj),
        ("E-mail:", client.email or "-", "Telefone:", client.phone or "-"),
        ("Endereco:", client.street or "-", "N.:", client.number or "-"),
        ("Bairro:", client.district or "-", "CEP:", client.zip_code or "-"),
        ("Cidade:", client.city or "-", "UF:", client.state or "-"),
    ]
    if client.estadual_registration:
        rows.insert(1, ("Insc. Estadual:", client.estadual_registration, "Complemento:", client.complement or "-"))
    elif client.complement:
        rows.append(("Complemento:", client.complement, "", ""))

    panel_h = len(rows) * _ROW_H + 2.0
    pdf.set_fill_color(*_PANEL)
    _set_box_stroke(pdf)
    pdf.rect(pdf.l_margin, panel_top, _CONTENT_W, panel_h, style="DF")
    pdf.set_y(panel_top + 1.0)

    for left_label, left_val, right_label, right_val in rows:
        y0 = pdf.get_y()
        pdf.set_font("Helvetica", "B", _FS_SMALL)
        pdf.set_text_color(*_BLUE)
        pdf.cell(label_l, _ROW_H, _safe(left_label))
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(left_w - label_l, _ROW_H, _dash(left_val)[:42])
        if right_label:
            pdf.set_xy(pdf.l_margin + left_w, y0)
            pdf.set_font("Helvetica", "B", _FS_SMALL)
            pdf.set_text_color(*_BLUE)
            pdf.cell(label_r, _ROW_H, _safe(right_label))
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.set_text_color(*_INK)
            pdf.cell(right_w - label_r, _ROW_H, _dash(right_val)[:28], new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.ln(_ROW_H)

    pdf.set_y(panel_top + panel_h + _GAP)
    _rule(pdf)


def _write_divider(pdf: _QuotePdf) -> None:
    pdf.ln(_GAP)
    _rule(pdf, color=_RULE, width=0.3, gap_after=_GAP * 2)


def _rule(
    pdf: _QuotePdf,
    *,
    gap_after: float = _GAP * 2,
    color: tuple[int, int, int] = _RULE,
    width: float = 0.3,
) -> None:
    y = pdf.get_y()
    pdf.set_draw_color(*color)
    pdf.set_line_width(width)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(gap_after)


def _section_band(
    pdf: _QuotePdf,
    title: str,
    color: tuple[int, int, int],
) -> None:
    y = pdf.get_y()
    pdf.set_fill_color(*color)
    pdf.rect(pdf.l_margin, y, _CONTENT_W, _BAND_H, style="F")
    edge = _BRAND_RED if color == _BRAND_RED_DARK else _ACCENT
    pdf.set_fill_color(*edge)
    pdf.rect(pdf.l_margin, y, 1.8, _BAND_H, style="F")
    pdf.set_xy(pdf.l_margin + 3.2, y + 0.55)
    pdf.set_font("Helvetica", "B", _FS_SECTION)
    pdf.set_text_color(*_WHITE)
    pdf.cell(0, _BAND_H - 1.1, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_y(y + _BAND_H + _GAP)



def _write_section(
    pdf: _QuotePdf,
    *,
    title: str,
    accent: tuple[int, int, int],
    items: list[QuoteItemRead],
    payment_plan: str | None,
    discount_pct: float | None,
    discount_value: float | None,
    labor_hours: float | None,
    labor_rate: float | None,
    include_labor: bool,
    notes: str | None = None,
    billed_by_name: str | None = None,
) -> None:
    _section_band(pdf, title, accent)

    pdf.set_fill_color(*_NAVY)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", _FS_SMALL)
    pdf.set_draw_color(*_NAVY)
    pdf.set_line_width(_BOX_LINE)
    pdf.cell(_COL_ITEM, _ROW_H, "ITEM", border=1, fill=True)
    pdf.cell(_COL_QTY, _ROW_H, "QTDE.", border=1, align="C", fill=True)
    pdf.cell(_COL_UNIT, _ROW_H, "V. UNIT.", border=1, align="R", fill=True)
    pdf.cell(_COL_TOTAL, _ROW_H, "V. TOTAL", border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    _set_box_stroke(pdf)

    pdf.set_font("Helvetica", "", _FS_BODY)
    items_total = 0.0
    if not items:
        pdf.set_fill_color(*_PANEL)
        _set_box_stroke(pdf)
        pdf.cell(_CONTENT_W, _ROW_H, "(sem itens)", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
    else:
        for idx, item in enumerate(items):
            items_total += float(item.total_value)
            pdf.set_fill_color(*(_ROW_ALT if idx % 2 == 1 else _PANEL))
            _set_box_stroke(pdf)
            pdf.cell(_COL_ITEM, _ROW_H, _safe(item.name)[:54], border=1, fill=True)
            pdf.cell(_COL_QTY, _ROW_H, f"{item.qty:g}", border=1, align="R", fill=True)
            pdf.cell(_COL_UNIT, _ROW_H, _brl(float(item.unit_value)), border=1, align="R", fill=True)
            pdf.cell(
                _COL_TOTAL,
                _ROW_H,
                _brl(float(item.total_value)),
                border=1,
                align="R",
                fill=True,
                new_x="LMARGIN",
                new_y="NEXT",
            )

    labor = 0.0
    if include_labor:
        hours = float(labor_hours or 0.0)
        rate = float(labor_rate or 0.0)
        labor = labor_total(hours, rate)
        if labor > 0:
            pdf.ln(_GAP)
            pdf.set_font("Helvetica", "B", _FS_BODY)
            pdf.set_text_color(*accent)
            pdf.cell(0, 3.6, "Mao de obra", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_INK)
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.set_fill_color(*_PANEL)
            _set_box_stroke(pdf)
            w_a = round(_CONTENT_W / 3.0, 2)
            w_b = round(_CONTENT_W / 3.0, 2)
            w_c = _CONTENT_W - w_a - w_b
            pdf.cell(w_a, _ROW_H, f"Horas: {hours:g}", border=1, fill=True)
            pdf.cell(w_b, _ROW_H, f"Valor hora: {_brl(rate)}", border=1, fill=True)
            pdf.cell(w_c, _ROW_H, f"Total: {_brl(labor)}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    section_subtotal = round_money(items_total + labor)
    discount, net = apply_section_discount(section_subtotal, discount_pct, discount_value)

    pdf.ln(_GAP)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.set_text_color(*accent)
    pdf.cell(0, 3.6, "Desconto / Pagamento", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "", _FS_BODY)
    pct_label = f"{float(discount_pct or 0):g}%" if discount_pct is not None else "0%"
    val_label = _brl(float(discount_value or 0.0))
    pdf.set_fill_color(*_PANEL)
    _set_box_stroke(pdf)
    w1 = w2 = w3 = round(_CONTENT_W / 4.0, 2)
    w4 = _CONTENT_W - w1 - w2 - w3
    pdf.cell(w1, _ROW_H, f"%: {pct_label}", border=1, fill=True)
    pdf.cell(w2, _ROW_H, f"R$: {val_label}", border=1, fill=True)
    pdf.cell(w3, _ROW_H, f"Aplic.: {_brl(discount)}", border=1, fill=True)
    pdf.cell(
        w4,
        _ROW_H,
        _safe(format_payment_plan_label(payment_plan))[:40],
        border=1,
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(_GAP)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    _set_box_stroke(pdf)
    subtotal_label = "Subtotal (itens + mao de obra)" if include_labor and labor > 0 else "Subtotal (itens)"
    pdf.set_fill_color(*_ROW_ALT)
    pdf.cell(_LABEL_W, _ROW_H, subtotal_label, border=1, align="R", fill=True)
    pdf.cell(_COL_TOTAL, _ROW_H, _brl(section_subtotal), border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    if discount > 0:
        pdf.set_fill_color(*_PANEL)
        _set_box_stroke(pdf)
        pdf.cell(_LABEL_W, _ROW_H, "Desconto", border=1, align="R", fill=True)
        pdf.cell(_COL_TOTAL, _ROW_H, f"- {_brl(discount)}", border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.set_fill_color(*accent)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.set_draw_color(*accent)
    pdf.set_line_width(_BOX_LINE)
    pdf.cell(_LABEL_W, _ROW_H + 0.6, "TOTAL LIQUIDO", border=1, align="R", fill=True)
    pdf.cell(_COL_TOTAL, _ROW_H + 0.6, _brl(net), border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(0, 0, 0)

    notes_clean = (notes or "").strip()
    billed_clean = (billed_by_name or "").strip()
    if notes_clean:
        pdf.ln(_GAP)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.cell(0, 3.6, "Observacoes", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.multi_cell(_CONTENT_W, 4.0, _safe(notes_clean))
    if billed_clean:
        pdf.ln(_GAP if not notes_clean else 0.4)
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 4, f"Faturado por: {_safe(billed_clean)}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)

    pdf.ln(_GAP)


def _write_payment_summary(
    pdf: _QuotePdf,
    *,
    module_nets: list[tuple[QuoteModule, float, float]],
) -> None:
    """Resumo por módulo presente + rótulos OS VHSYS se legacy implant/mensal existirem."""
    quote_total = round_money(sum(net for _m, _q, net in module_nets))
    half = _CONTENT_W / 2.0
    lab_w = round(half * 0.64, 2)
    val_w = half - lab_w

    pdf.ln(_GAP)
    _section_band(pdf, "DADOS DE PAGAMENTO", _NAVY)

    def _pair(left_label: str, left_val: str, right_label: str, right_val: str) -> None:
        pdf.set_fill_color(*_PANEL)
        _set_box_stroke(pdf)
        pdf.set_font("Helvetica", "B", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(left_label), border="LTB", fill=True)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, left_val, border="RTB", align="R", fill=True)
        pdf.set_font("Helvetica", "B", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(right_label), border="LTB", fill=True)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(
            val_w,
            _ROW_H,
            right_val,
            border="RTB",
            align="R",
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

    def _full_row(label: str, qty: float, net: float) -> None:
        pdf.set_fill_color(*_PANEL)
        _set_box_stroke(pdf)
        pdf.set_font("Helvetica", "B", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(f"QTDE {label}")[:40], border="LTB", fill=True)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, _qty(qty), border="RTB", align="R", fill=True)
        pdf.set_font("Helvetica", "B", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(f"TOTAL {label}")[:40], border="LTB", fill=True)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(
            val_w,
            _ROW_H,
            _brl(net),
            border="RTB",
            align="R",
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

    implant = next(
        ((m, q, n) for m, q, n in module_nets if m.legacy_kind == "implantacao"),
        None,
    )
    monthly = next(
        ((m, q, n) for m, q, n in module_nets if m.legacy_kind == "mensalidade"),
        None,
    )

    if implant is not None and monthly is not None:
        _pair(
            "TOTAL DE HORAS/QTDE DE SERVICOS",
            _qty(implant[1]),
            "VALOR TOTAL DOS SERVICOS",
            _brl(implant[2]),
        )
        _pair(
            "TOTAL DE PRODUTOS",
            _qty(monthly[1]),
            "VALOR TOTAL DOS PRODUTOS",
            _brl(monthly[2]),
        )
        for mod, qty, net in module_nets:
            if mod.legacy_kind in ("implantacao", "mensalidade"):
                continue
            _full_row(_module_band_title(mod), qty, net)
    elif implant is not None:
        _pair(
            "TOTAL DE HORAS/QTDE DE SERVICOS",
            _qty(implant[1]),
            "VALOR TOTAL DOS SERVICOS",
            _brl(implant[2]),
        )
        for mod, qty, net in module_nets:
            if mod.legacy_kind == "implantacao":
                continue
            _full_row(_module_band_title(mod), qty, net)
    elif monthly is not None:
        _pair(
            "TOTAL DE PRODUTOS",
            _qty(monthly[1]),
            "VALOR TOTAL DOS PRODUTOS",
            _brl(monthly[2]),
        )
        for mod, qty, net in module_nets:
            if mod.legacy_kind == "mensalidade":
                continue
            _full_row(_module_band_title(mod), qty, net)
    else:
        for mod, qty, net in module_nets:
            _full_row(_module_band_title(mod), qty, net)

    pdf.set_fill_color(*_NAVY)
    pdf.set_draw_color(*_NAVY)
    pdf.set_line_width(_BOX_LINE)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", _FS_SECTION)
    pdf.cell(_LABEL_W, _ROW_H + 0.8, "VALOR TOTAL DO ORCAMENTO", border=1, align="R", fill=True)
    pdf.cell(_COL_TOTAL, _ROW_H + 0.8, _brl(quote_total), border=1, align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(_GAP)


def _write_observations(pdf: _QuotePdf, notes: str | None) -> None:
    _section_band(pdf, "OBSERVACOES", _BLUE)
    text = (notes or "").strip() or "-"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    clipped = "\n".join(lines[:4])
    if len(clipped) > 480:
        clipped = clipped[:477] + "..."

    line_h = 3.6
    n_lines = max(1, clipped.count("\n") + 1)
    box_h = max(_ROW_H * 2, n_lines * line_h + 2.4)
    box_top = pdf.get_y()
    pdf.set_fill_color(*_PANEL)
    _set_box_stroke(pdf)
    pdf.rect(pdf.l_margin, box_top, _CONTENT_W, box_h, style="DF")
    pdf.set_xy(pdf.l_margin + 2, box_top + 1.2)
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(_CONTENT_W - 4, line_h, _safe(clipped))
    pdf.set_y(box_top + box_h + _GAP)


def _write_signatures(pdf: _QuotePdf) -> None:
    needed = 20.0
    if pdf.get_y() + needed < pdf.h - pdf.b_margin - 6:
        pdf.set_y(pdf.h - pdf.b_margin - needed)

    pdf.ln(_GAP)
    _rule(pdf, color=_ACCENT, width=0.4, gap_after=5.0)
    col_w = _CONTENT_W / 3.0
    y_line = pdf.get_y()
    pdf.set_draw_color(*_NAVY)
    pdf.set_line_width(0.3)
    for i in range(3):
        x0 = pdf.l_margin + i * col_w + 4
        x1 = pdf.l_margin + (i + 1) * col_w - 4
        pdf.line(x0, y_line, x1, y_line)

    pdf.set_y(y_line + 1.5)
    pdf.set_font("Helvetica", "", _FS_SMALL)
    pdf.set_text_color(*_MUTED)
    labels = (
        "EM ___/___/___ Data do aceite",
        "Assinatura do Prestador",
        "Assinatura do Sacado",
    )
    for i, label in enumerate(labels):
        pdf.set_x(pdf.l_margin + i * col_w)
        pdf.cell(col_w, 4.0, _safe(label), align="C")
    pdf.set_text_color(*_INK)
    pdf.ln(3.0)
