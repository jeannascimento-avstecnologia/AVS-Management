"""Geração local de PDF de orçamento — layout espelhando OS VHSYS (SPEC_PDF_ORCAMENTO).

Acabamento visual Aurora (textura, barras, tabelas) sem alterar estrutura/organização.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
import unicodedata

from fpdf import FPDF

from src.cnpj.validator import format_cnpj
from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer, client_from_quote, issuer_from_settings
from src.quotes.schemas import QuoteItemRead, QuoteModule, QuoteRead
from src.quotes.totals import (
    apply_section_discount,
    format_payment_plan_label,
    labor_total,
    round_money,
)


def _agent_dbg(hypothesis_id: str, location: str, message: str, data: dict[str, Any]) -> None:
    # #region agent log
    try:
        import time

        payload = {
            "sessionId": "ae8776",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        p = Path("/Users/jean.nascimento/Projetos/avs-management/.cursor/debug-ae8776.log")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

# Aurora / AVS (RGB) — azul + vermelho da logo (sem roxo; P&B: fills escuros → cinza legível)
_NAVY = (12, 30, 58)
_BLUE = (26, 79, 140)
_ACCENT = (43, 143, 217)
_BRAND_RED = (220, 38, 38)  # logo A / aurora-brand-red #dc2626
_BRAND_RED_DARK = (185, 28, 28)  # fills de seção (melhor em grayscale)
_INK = (30, 41, 59)
_MUTED = (100, 116, 139)
_RULE = (148, 163, 184)
_BOX_BORDER = (148, 163, 184)
_ROW_ALT = (248, 250, 252)
_PANEL = (255, 255, 255)
_PAGE = (255, 255, 255)
_WHITE = (255, 255, 255)
_HEADER_FILL = (241, 245, 249)
_BOX_LINE = 0.3

_LOGO_PATH = Path(__file__).resolve().parents[1] / "cropped-AVS-SemArco-Colorido_2024.png"
_ICON_DIR = Path(__file__).resolve().parent / "pdf_icons"
_ICON_PHONE = _ICON_DIR / "phone.png"
_ICON_MAIL = _ICON_DIR / "mail.png"
_ICON_GLOBE = _ICON_DIR / "globe.png"
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
_COL_ITEM = 104.0
_COL_QTY = 22.0
_COL_UNIT = 31.0
_COL_TOTAL = 31.0  # 104+22+31+31 = 188
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


_FOOTER_MARGIN = 24.0


def _safe(text: str | None) -> str:
    if not text:
        return "-"
    cleaned = (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2022", "-")
        .replace("\u00b7", "|")
        .replace("\u2026", "...")
    )
    return cleaned.encode("latin-1", errors="replace").decode("latin-1")


def _dash(text: str | None) -> str:
    cleaned = (text or "").strip()
    return _safe(cleaned) if cleaned else "-"


def _wrap_text_lines(pdf: FPDF, text: str, width: float) -> list[str]:
    """Quebra palavras para caber na largura (usa métricas do font atual)."""
    cleaned = (text or "").replace("\n", " ").strip()
    if not cleaned:
        return ["-"]
    words = cleaned.split()
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        test = f"{current} {w}"
        if pdf.get_string_width(test) <= width:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


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
    return []


class _QuotePdf(FPDF):
    """A4 comercial — fundo branco, sem barras de marca."""

    def __init__(self, *args, issuer: QuotePdfIssuer | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._issuer = issuer

    def header(self) -> None:
        self.set_fill_color(*_PAGE)
        self.set_draw_color(0, 0, 0)
        self.set_text_color(*_INK)
        self.set_xy(self.l_margin, self.t_margin)

    def footer(self) -> None:
        self.set_y(-_FOOTER_MARGIN + 2.0)
        y = self.get_y()
        self.set_draw_color(*_RULE)
        self.set_line_width(0.2)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        _write_issuer_footer(self, self._issuer, y + 1.2)


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


def _module_meta_height(
    notes: str | None,
    billed_by_name: str | None,
    billed_by_cnpj: str | None = None,
) -> float:
    """Altura extra de observações / faturado por no módulo (só se preenchidos)."""
    h = 0.0
    notes_clean = (notes or "").strip()
    billed_clean = (billed_by_name or "").strip()
    if notes_clean:
        lines = max(1, (len(notes_clean) + 89) // 90)
        h += _GAP + _ROW_H + lines * 4.0
    if billed_clean or (billed_by_cnpj or "").strip():
        h += _GAP + _ROW_H
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
    billed_by_cnpj: str | None = None,
    simplified: bool = False,
) -> float:
    """Altura estimada de `_write_section` (banda → total líquido + gap final)."""
    h = _BAND_H + _GAP  # section band
    h += _ROW_H  # header ITEM/QTDE/...
    if simplified:
        h += _ROW_H  # display_name row
    else:
        if not items:
            h += _ROW_H  # rows or "(sem itens)"
        else:
            # Aproxima quantas linhas o item tende a quebrar na largura _COL_ITEM.
            line_h = 2.6
            for item in items:
                name_len = max(1, len((item.name or "").strip()))
                est_lines = (name_len + 53) // 54  # baseline ~54 chars por linha
                est_lines = max(1, min(3, est_lines))
                h += max(_ROW_H, est_lines * line_h)

    labor = 0.0
    if include_labor:
        labor = labor_total(labor_hours, labor_rate)
        if labor > 0:
            h += _GAP + 3.6 + _ROW_H  # "Mao de obra" label + row

    items_total = sum(float(i.total_value) for i in items)
    section_subtotal = round_money(items_total + labor)
    discount, _net = apply_section_discount(section_subtotal, discount_pct, discount_value)

    if discount > 0:
        h += _GAP + 3.6 + _ROW_H  # Desconto / Pagamento
        h += _GAP + _ROW_H  # subtotal
        h += _ROW_H  # Desconto (linha extra)
    else:
        h += _GAP + 3.6 + _ROW_H  # Pagamento (se houver) + subtotal
        h += _GAP + _ROW_H
    h += (_ROW_H + 0.6) + _GAP  # TOTAL LIQUIDO + ln
    h += _module_meta_height(notes, billed_by_name, billed_by_cnpj)
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
    max_lines = 12
    clipped = "\n".join(lines[:max_lines])
    if len(lines) > max_lines and len(clipped) > 480:
        clipped = clipped[:477] + "..."
    line_h = 3.6
    n_lines = max(1, clipped.count("\n") + 1)
    box_h = max(_ROW_H * 2, n_lines * line_h + 2.4)
    return _BAND_H + _GAP + box_h + _GAP


def _notes_with_disclaimer_and_ticket(quote: QuoteRead) -> str:
    """Garante que disclaimer+ticket aparecem em OBSERVACOES (sem duplicar)."""
    notes = (quote.notes or "").strip()
    has_disclaimer = "Os valores podem sofrer alteracao" in notes
    has_ticket = "Ticket no." in notes
    ticket = (quote.tiflux_ticket_number or "").strip()

    extras: list[str] = []
    if not has_disclaimer:
        extras.append("Os valores podem sofrer alteracao sem previo aviso.")
    if not has_ticket:
        extras.append(f"Ticket no.: {ticket}" if ticket else "Ticket no.:")

    if not extras:
        return notes or "-"
    if notes:
        return "\n".join([notes, *extras])
    return "\n".join(extras)


def _estimate_signatures_height() -> float:
    """Altura do bloco de assinaturas (espaço em branco + linhas)."""
    return 8.0 + 22.0 + 3.0 + 5.0 + 6.0


def _estimate_disclaimer_signatures_height() -> float:
    return 8.0 + 5.0 + 5.0 + 20.0


def render_quote_pdf(
    quote: QuoteRead,
    dest: Path,
    *,
    issuer: QuotePdfIssuer | None = None,
    client: QuotePdfClient | None = None,
    version_number: int | None = None,
    monthly_draft_json: str | None = None,
) -> None:
    """Grava PDF do orçamento em `dest` (arquivo já resolvido sob HUB_PDF_DIR)."""
    issuer = issuer or issuer_from_settings()
    _ = client or client_from_quote(quote)
    monthly_exclude_total = 0.0
    monthly_rows: list[dict[str, Any]] = []
    if monthly_draft_json:
        try:
            draft = json.loads(str(monthly_draft_json))
        except (ValueError, TypeError):
            draft = {}
        allocs = draft.get("allocations") or []
        license_ids: set[int] = set()
        if isinstance(allocs, list) and allocs:
            by_item = {int(i.id): i for i in quote.items}
            for a in allocs:
                if not isinstance(a, dict):
                    continue
                try:
                    iid = int(a.get("item_id"))
                except (TypeError, ValueError):
                    continue
                license_ids.add(iid)
                item = by_item.get(iid)
                product = (item.name if item else "") or f"Item {iid}"
                line_total = float(item.total_value) if item else 0.0
                monthly_rows.append({"role": "product", "name": product, "amount": line_total})
                monthly_rows.append(
                    {
                        "role": "split",
                        "name": str(a.get("fornecedor_name") or "Fornecedor"),
                        "amount": float(a.get("fornecedor_amount") or 0.0),
                    }
                )
                monthly_rows.append(
                    {
                        "role": "split",
                        "name": str(a.get("intermediador_name") or "Intermediador"),
                        "amount": float(a.get("intermediador_amount") or 0.0),
                    }
                )
        else:
            license_item_ids = draft.get("license_item_ids") or []
            try:
                license_ids = {int(i) for i in license_item_ids}
            except (TypeError, ValueError):
                license_ids = set()
            charges = draft.get("charges") or []
            if isinstance(charges, list):
                monthly_rows = [
                    {"role": "split", "name": str(c.get("name") or "-"), "amount": float(c.get("amount") or 0)}
                    for c in charges
                    if isinstance(c, dict)
                ]
        if license_ids:
            monthly_exclude_total = round_money(
                sum(float(i.total_value) for i in quote.items if i.id in license_ids)
            )

    pdf = _QuotePdf(format="A4", issuer=issuer)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=_FOOTER_MARGIN)
    pdf.set_margins(11, 9, 11)
    pdf.add_page()

    _write_header(pdf, quote, issuer, version_number=version_number)

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
            billed_by_cnpj=mod.billed_by_cnpj,
            simplified=bool(mod.simplified),
        )
        if idx > 0:
            section_h += _divider_height()
        _ensure_space(pdf, section_h)
        if idx > 0:
            _write_divider(pdf)
        _write_section(
            pdf,
            title=_module_band_title(mod),
            accent=_INK,
            items=mod_items,
            payment_plan=mod.payment_plan,
            discount_pct=mod.discount_pct,
            discount_value=mod.discount_value,
            labor_hours=mod.labor_hours if include_labor else None,
            labor_rate=mod.labor_hourly_rate if include_labor else None,
            include_labor=include_labor,
            notes=mod.notes,
            billed_by_name=mod.billed_by_name,
            billed_by_cnpj=mod.billed_by_cnpj,
            simplified=bool(mod.simplified),
            display_name=mod.display_name,
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
    _write_payment_summary(pdf, module_nets=module_nets, exclude_total=monthly_exclude_total)

    if monthly_rows:
        _ensure_space(pdf, _estimate_monthly_charges_height(monthly_rows))
        _write_monthly_charges_section(pdf, rows=monthly_rows)

    notes_for_pdf = _notes_with_disclaimer_and_ticket(quote)
    _ensure_space(pdf, _estimate_observations_height(notes_for_pdf))
    _write_observations(pdf, notes_for_pdf)

    _ensure_space(pdf, _estimate_signatures_height())
    _write_signatures(pdf)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(dest))


def _draw_contact_line(pdf: _QuotePdf, issuer: QuotePdfIssuer, x: float, y: float) -> None:
    """Telefone | e-mail | site com ícones, a partir de (x, y)."""
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "", _FS_SMALL)
    icon_h = 3.2
    cursor = x

    def _contact_item(icon: Path, label: str) -> None:
        nonlocal cursor
        if icon.is_file():
            pdf.image(str(icon), x=cursor, y=y + 0.1, h=icon_h)
            cursor += icon_h + 1.0
        pdf.set_xy(cursor, y)
        pdf.cell(pdf.get_string_width(label) + 1.2, 3.4, label)
        cursor += pdf.get_string_width(label) + 1.2

    items: list[tuple[Path, str]] = []
    if issuer.phone:
        items.append((_ICON_PHONE, _safe(issuer.phone)))
    if issuer.email:
        items.append((_ICON_MAIL, _safe(issuer.email)))
    if issuer.site:
        items.append((_ICON_GLOBE, _safe(issuer.site)))
    for i, (icon, label) in enumerate(items):
        _contact_item(icon, label)
        if i < len(items) - 1:
            pdf.set_xy(cursor, y)
            pdf.cell(3.5, 3.4, "|")
            cursor += 3.5
    page_label = f"Pagina {pdf.page_no()}/{{nb}}"
    pdf.set_font("Helvetica", "I", _FS_MUTED)
    pdf.set_text_color(*_MUTED)
    pdf.set_xy(pdf.l_margin, y)
    pdf.cell(0, 3.4, page_label, align="R")
    pdf.set_text_color(*_INK)


def _write_issuer_footer(pdf: _QuotePdf, issuer: QuotePdfIssuer | None, y: float) -> None:
    issuer = issuer or issuer_from_settings()
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("Helvetica", "", _FS_SMALL)
    pdf.set_text_color(*_MUTED)
    address = (issuer.address_line or "").strip()
    if address:
        pdf.multi_cell(_CONTENT_W, 3.4, _safe(address))
        contact_y = pdf.get_y()
    else:
        contact_y = y
    _draw_contact_line(pdf, issuer, pdf.l_margin, contact_y)
    pdf.set_y(contact_y + 3.8)


def _write_header(
    pdf: _QuotePdf,
    quote: QuoteRead,
    issuer: QuotePdfIssuer,
    *,
    version_number: int | None = None,
) -> None:
    top_y = pdf.get_y()
    logo_w = 24.0
    logo_h = 17.0
    text_x = pdf.l_margin + logo_w + 3.0

    if _LOGO_PATH.is_file():
        pdf.image(str(_LOGO_PATH), x=pdf.l_margin, y=top_y, w=logo_w)
    else:
        text_x = pdf.l_margin

    usable = pdf.w - pdf.r_margin - text_x
    main_title = _safe(f"Orcamento : {quote_display_id(quote.id)}")
    ver_label = f"v{int(version_number)}" if version_number is not None else ""
    date_s = f"Data: {_fmt_date(quote.updated_at or quote.created_at)}"
    pdf.set_xy(text_x, top_y)
    pdf.set_font("Helvetica", "B", _FS_TITLE)
    pdf.set_text_color(*_INK)
    if ver_label:
        main_w = pdf.get_string_width(main_title)
        pdf.cell(main_w, 5.8, main_title)
        pdf.set_x(text_x + main_w + 1.5)
        pdf.set_font("Helvetica", "B", _FS_TITLE * 0.75)
        pdf.cell(pdf.get_string_width(ver_label) + 1.5, 5.8, ver_label)
        pdf.set_font("Helvetica", "B", _FS_BODY)
    else:
        pdf.cell(usable, 5.8, main_title)
    pdf.set_xy(text_x, top_y)
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.cell(usable, 5.8, _safe(date_s), align="R", new_x="LMARGIN", new_y="NEXT")

    ie = (issuer.ie or "").strip()
    line1 = f"{issuer.name} - CNPJ: {issuer.cnpj}"
    if ie:
        line1 = f"{line1} | Insc Estadual: {ie}"
    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(pdf.w - pdf.r_margin - text_x, 4.0, _safe(line1))

    pdf.set_text_color(*_INK)
    content_y = max(pdf.get_y(), top_y + logo_h)
    pdf.set_y(content_y + _GAP)
    _rule(pdf, color=_RULE, width=0.35)


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
    pdf.set_y(panel_top)

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
    pdf.set_xy(pdf.l_margin, y)
    pdf.set_font("Helvetica", "B", _FS_SECTION)
    pdf.set_text_color(*_INK)
    pdf.cell(0, _BAND_H - 1.1, _safe(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(_GAP)
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(0, 0, 0)



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
    billed_by_cnpj: str | None = None,
    simplified: bool = False,
    display_name: str | None = None,
) -> None:
    _section_band(pdf, title, accent)

    pdf.set_fill_color(*_HEADER_FILL)
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "B", _FS_SMALL)
    _set_box_stroke(pdf)

    items_total = sum(float(i.total_value) for i in items)
    pdf.cell(_COL_ITEM, _ROW_H, "ITEM", fill=True)
    qty_header = "QTDE"
    # #region agent log
    _agent_dbg("E", "pdf.py:_write_section", "qty column header", {"qty_header": qty_header})
    # #endregion
    pdf.cell(_COL_QTY, _ROW_H, qty_header, align="C", fill=True)
    pdf.cell(_COL_UNIT, _ROW_H, "V. UNIT.", align="R", fill=True)
    pdf.cell(_COL_TOTAL, _ROW_H, "V. TOTAL", align="R", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.25)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "", _FS_BODY)

    if simplified:
        label = (display_name or title or "").strip() or title
        pdf.set_fill_color(*_PAGE)
        pdf.cell(_COL_ITEM, _ROW_H, _safe(label)[:54], fill=True)
        pdf.cell(_COL_QTY, _ROW_H, "1", align="C", fill=True)
        pdf.cell(_COL_UNIT, _ROW_H, _brl(items_total), align="R", fill=True)
        pdf.cell(
            _COL_TOTAL,
            _ROW_H,
            _brl(items_total),
            align="R",
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
    elif not items:
        pdf.cell(_CONTENT_W, _ROW_H, "(sem itens)", new_x="LMARGIN", new_y="NEXT")
    else:
        for idx, item in enumerate(items):
            pdf.set_fill_color(*(_ROW_ALT if idx % 2 == 1 else _PAGE))
            x_name = pdf.l_margin
            x_qty = x_name + _COL_ITEM
            x_unit = x_qty + _COL_QTY
            x_total = x_unit + _COL_UNIT
            y0 = pdf.get_y()

            line_h = 2.6
            name = _safe(item.name).replace("\n", " ").strip()
            lines = _wrap_text_lines(pdf, name, _COL_ITEM)
            row_h = max(_ROW_H, len(lines) * line_h)

            # Fundo completo da célula ITEM
            pdf.rect(x_name, y0, _COL_ITEM, row_h, style="F")

            pdf.set_xy(x_name, y0)
            pdf.multi_cell(
                _COL_ITEM,
                line_h,
                "\n".join(lines),
                align="L",
            )

            pdf.set_xy(x_qty, y0)
            pdf.cell(_COL_QTY, row_h, f"{item.qty:g}", align="C", fill=True)
            pdf.set_xy(x_unit, y0)
            pdf.cell(_COL_UNIT, row_h, _brl(float(item.unit_value)), align="R", fill=True)
            pdf.set_xy(x_total, y0)
            pdf.cell(_COL_TOTAL, row_h, _brl(float(item.total_value)), align="R", fill=True)

            pdf.set_xy(pdf.l_margin, y0 + row_h)

    pdf.set_text_color(*_INK)
    _set_box_stroke(pdf)
    pdf.set_font("Helvetica", "", _FS_BODY)

    labor = 0.0
    if include_labor:
        hours = float(labor_hours or 0.0)
        rate = float(labor_rate or 0.0)
        labor = labor_total(hours, rate)
        if labor > 0:
            pdf.ln(_GAP)
            pdf.set_font("Helvetica", "B", _FS_BODY)
            pdf.set_text_color(*_INK)
            pdf.cell(0, 3.6, "Mao de obra", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_INK)
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.cell(0, _ROW_H, f"Horas: {hours:g}    Valor hora: {_brl(rate)}    Total: {_brl(labor)}", new_x="LMARGIN", new_y="NEXT")

    section_subtotal = round_money(items_total + labor)
    discount, net = apply_section_discount(section_subtotal, discount_pct, discount_value)

    pay = _safe(format_payment_plan_label(payment_plan)).strip()
    pdf.ln(_GAP)
    if discount > 0:
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 3.6, "Desconto / Pagamento", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)
        pdf.set_font("Helvetica", "", _FS_BODY)
        pct_label = f"{float(discount_pct or 0):g}%" if discount_pct is not None else "0%"
        val_label = _brl(float(discount_value or 0.0))
        discount_bits = [
            f"Desconto {pct_label} ({val_label})",
            f"Aplicado {_brl(discount)}",
        ]
        if pay and pay != "-":
            discount_bits.append(pay)
        pdf.cell(0, _ROW_H, " | ".join(discount_bits), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(_GAP)
    elif pay and pay != "-":
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 3.6, "Pagamento", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.cell(0, _ROW_H, pay, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(_GAP)

    pdf.set_font("Helvetica", "", _FS_BODY)
    subtotal_label = "Subtotal (itens + mao de obra)" if include_labor and labor > 0 else "Subtotal (itens)"
    pdf.cell(_LABEL_W, _ROW_H, subtotal_label, align="R")
    pdf.cell(_COL_TOTAL, _ROW_H, _brl(section_subtotal), align="R", new_x="LMARGIN", new_y="NEXT")
    if discount > 0:
        pdf.cell(_LABEL_W, _ROW_H, "Desconto", align="R")
        pdf.cell(_COL_TOTAL, _ROW_H, f"- {_brl(discount)}", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.cell(_LABEL_W, _ROW_H + 0.6, "TOTAL LIQUIDO", align="R")
    pdf.cell(_COL_TOTAL, _ROW_H + 0.6, _brl(net), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_draw_color(0, 0, 0)

    notes_clean = (notes or "").strip()
    billed_clean = (billed_by_name or "").strip()
    cnpj_clean = (billed_by_cnpj or "").strip()
    if notes_clean:
        pdf.ln(_GAP)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.cell(0, _ROW_H, "Observacoes", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.multi_cell(_CONTENT_W, 4.0, _safe(notes_clean))
    if billed_clean or cnpj_clean:
        billed_label = billed_clean
        if cnpj_clean:
            pretty = format_cnpj(cnpj_clean) or cnpj_clean
            billed_label = f"{billed_clean} | CNPJ {pretty}" if billed_clean else f"CNPJ {pretty}"
        pdf.ln(_GAP)
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.cell(0, _ROW_H, f"Faturado por: {_safe(billed_label)[:90]}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(_GAP)


def _write_payment_summary(
    pdf: _QuotePdf,
    *,
    module_nets: list[tuple[QuoteModule, float, float]],
    exclude_total: float = 0.0,
) -> None:
    """Resumo por módulo presente + rótulos OS VHSYS se legacy implant/mensal existirem."""
    quote_total = round_money(max(0.0, sum(net for _m, _q, net in module_nets) - float(exclude_total)))
    half = _CONTENT_W / 2.0
    lab_w = round(half * 0.64, 2)
    val_w = half - lab_w

    pdf.ln(_GAP)
    _section_band(pdf, "DADOS DE PAGAMENTO", _NAVY)

    def _pair(left_label: str, left_val: str, right_label: str, right_val: str) -> None:
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(left_label))
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, left_val, align="R")
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(right_label))
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, right_val, align="R", new_x="LMARGIN", new_y="NEXT")

    def _full_row(label: str, qty: float, net: float) -> None:
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(f"QTDE {label}")[:40])
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, _qty(qty), align="R")
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(lab_w, _ROW_H, _safe(f"TOTAL {label}")[:40])
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(val_w, _ROW_H, _brl(net), align="R", new_x="LMARGIN", new_y="NEXT")

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

    pdf.set_font("Helvetica", "B", _FS_SECTION)
    pdf.cell(_LABEL_W, _ROW_H + 0.8, "VALOR TOTAL DO ORCAMENTO", align="R")
    pdf.cell(_COL_TOTAL, _ROW_H + 0.8, _brl(quote_total), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.35)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.set_text_color(*_INK)
    pdf.set_draw_color(0, 0, 0)
    pdf.ln(_GAP)


def _estimate_monthly_charges_height(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return _GAP + _BAND_H + (_ROW_H * (len(rows) + 1)) + _GAP


def _write_monthly_charges_section(
    pdf: _QuotePdf,
    *,
    rows: list[dict[str, Any]],
) -> float:
    """Renderiza seção 'MENSALIDADES' (produto + fornecedor/intermediador)."""
    if not rows:
        return 0.0
    # #region agent log
    _agent_dbg(
        "D",
        "pdf.py:_write_monthly_charges_section",
        "monthly section rows",
        {
            "roles": [str(r.get("role")) for r in rows],
            "names": [str(r.get("name") or "")[:40] for r in rows],
        },
    )
    # #endregion
    _section_band(pdf, "MENSALIDADES", _NAVY)
    total = 0.0
    pdf.set_text_color(*_INK)
    for r in rows:
        role = str(r.get("role") or "split")
        name = (str(r.get("name") or "")).strip() or "-"
        amount = float(r.get("amount") or 0.0)
        if role == "product":
            pdf.set_font("Helvetica", "B", _FS_BODY)
            pdf.cell(_LABEL_W, _ROW_H, _safe(name)[:60], align="L")
            pdf.cell(_COL_TOTAL, _ROW_H, _brl(amount), align="R", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.cell(_LABEL_W, _ROW_H, _safe(f"  {name}")[:60], align="L")
            pdf.cell(_COL_TOTAL, _ROW_H, _brl(amount), align="R", new_x="LMARGIN", new_y="NEXT")
            total += amount
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.cell(_LABEL_W, _ROW_H, "TOTAL MENSALIDADES", align="L")
    pdf.cell(_COL_TOTAL, _ROW_H, _brl(round_money(total)), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(_GAP)
    return 0.0


def _write_observations(pdf: _QuotePdf, notes: str | None) -> None:
    _section_band(pdf, "OBSERVACOES", _BLUE)
    text = (notes or "").strip() or "-"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    max_lines = 12
    clipped = "\n".join(lines[:max_lines])
    if len(lines) > max_lines and len(clipped) > 480:
        clipped = clipped[:477] + "..."

    line_h = 3.6
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(_CONTENT_W, line_h, _safe(clipped))
    pdf.ln(_GAP)


def _write_disclaimer_and_ticket(pdf: _QuotePdf, quote: QuoteRead) -> None:
    pdf.ln(_GAP)
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(
        _CONTENT_W,
        4.0,
        _safe("Os valores podem sofrer alteracao sem previo aviso."),
    )
    ticket = (quote.tiflux_ticket_number or "").strip()
    line = f"Ticket no.: {ticket}" if ticket else "Ticket no.:"
    pdf.set_x(pdf.l_margin)
    pdf.cell(_CONTENT_W, 4.5, _safe(line), align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(_GAP)


def _write_signatures(pdf: _QuotePdf) -> None:
    pdf.ln(8.0)
    _rule(pdf, color=_RULE, width=0.35, gap_after=4.0)
    col_w = _CONTENT_W / 3.0
    blank = 22.0
    y_start = pdf.get_y()
    y_line = y_start + blank
    pdf.set_draw_color(*_NAVY)
    pdf.set_line_width(0.3)
    for i in range(3):
        x0 = pdf.l_margin + i * col_w + 4
        x1 = pdf.l_margin + (i + 1) * col_w - 4
        pdf.line(x0, y_line, x1, y_line)

    pdf.set_y(y_line + 3.0)
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
    pdf.ln(6.0)
