"""Geração local de PDF de orçamento — layout espelhando OS VHSYS (SPEC_PDF_ORCAMENTO).

Acabamento visual Aurora (textura, barras, tabelas) sem alterar estrutura/organização.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
import unicodedata

from fpdf import FPDF

from src.cnpj.validator import format_cnpj
from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer, client_from_quote, issuer_from_settings
from src.quotes.schemas import DEFAULT_QUOTE_NOTES, QuoteItemRead, QuoteModule, QuoteRead
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
_ICON_WHATSAPP = _ICON_DIR / "whatsapp.png"
_ICON_MAIL = _ICON_DIR / "mail.png"
_ICON_GLOBE = _ICON_DIR / "globe.png"
_VEIVO_LOGO_PATH = _ICON_DIR / "veivo-powered-by.png"
# Grade tipográfica / geometria (tudo alinhado à mesma largura útil)
_CONTENT_W = 188.0
_FS_TITLE = 16.0
_FS_SECTION = 9.0
_FS_BODY = 8.0
_FS_SMALL = 7.5
_FS_MUTED = 7.0
_ROW_H = 5.8
_BAND_H = 6.2
_GAP = 1.4
_LINE_H = 4.2
_CELL_PAD = 1.5
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


_FOOTER_MARGIN = 12.0


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


def _digits_only(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def _whatsapp_href(phone: str) -> str | None:
    digits = _digits_only(phone)
    if len(digits) < 10:
        return None
    if digits.startswith("55") and len(digits) >= 12:
        e164 = digits
    elif len(digits) in {10, 11}:
        e164 = f"55{digits}"
    else:
        return None
    return f"https://wa.me/{e164}"


_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _mailto_href(email: str) -> str | None:
    cleaned = (email or "").strip().rstrip("|")
    if not cleaned or any(ch.isspace() for ch in cleaned):
        return None
    if cleaned.lower().startswith("mailto:"):
        cleaned = cleaned[7:]
    if not _EMAIL_RE.fullmatch(cleaned):
        return None
    return f"mailto:{cleaned}"


def _site_href(site: str) -> str | None:
    cleaned = (site or "").strip().rstrip("/").rstrip("|")
    if not cleaned:
        return None
    lower = cleaned.lower()
    if lower.startswith(("javascript:", "data:", "file:", "vbscript:")):
        return None
    if not lower.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
        lower = cleaned.lower()
    if not lower.startswith("https://"):
        return None
    host = cleaned.split("://", 1)[1].split("/", 1)[0]
    if not host or "." not in host or any(ch.isspace() for ch in host):
        return None
    return cleaned


def _wrap_text_lines(pdf: FPDF, text: str, width: float) -> list[str]:
    """Quebra palavras para caber na largura (usa métricas do font atual)."""
    cleaned = (text or "").replace("\n", " ").strip()
    if not cleaned:
        return ["-"]

    def _chunks(s: str) -> list[str]:
        if pdf.get_string_width(s) <= width:
            return [s]
        out: list[str] = []
        buf = ""
        for ch in s:
            trial = buf + ch
            if buf and pdf.get_string_width(trial) > width:
                out.append(buf)
                buf = ch
            else:
                buf = trial
        if buf:
            out.append(buf)
        return out or ["-"]

    words = cleaned.split()
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        test = f"{current} {w}"
        if pdf.get_string_width(test) <= width:
            current = test
        else:
            lines.extend(_chunks(current))
            current = w
    lines.extend(_chunks(current))
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
        _write_page_number(self, y + 1.2)
        # Logo VEIVO discreta no canto inferior direito
        exists = _VEIVO_LOGO_PATH.is_file()
        veivo_h = 8.0  # mm — lockup 3 linhas (POWERED BY / VEIVO / SISTEMAS)
        veivo_w = veivo_h * (2000 / 617)
        veivo_x = self.w - self.r_margin - veivo_w
        veivo_y = self.h - _FOOTER_MARGIN + 3.5
        if exists:
            try:
                self.image(
                    str(_VEIVO_LOGO_PATH),
                    x=veivo_x,
                    y=veivo_y,
                    w=veivo_w,
                    h=veivo_h,
                )
            except Exception:
                pass


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
    """Espaço entre módulos (sem regra extra — a banda já desenha a linha)."""
    return _GAP * 2


def _module_meta_height(
    notes: str | None,
    billed_by_name: str | None,
    billed_by_cnpj: str | None = None,
) -> float:
    """Altura extra de observações no módulo (Faturado por fica só na banda)."""
    _ = billed_by_name, billed_by_cnpj
    h = 0.0
    notes_clean = (notes or "").strip()
    if notes_clean:
        lines = max(1, (len(notes_clean) + 89) // 90)
        h += _GAP + _ROW_H + lines * 4.0
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
    payment_plan: str | None = None,
    installments: list[dict[str, Any]] | None = None,
) -> float:
    """Altura estimada de `_write_section` (banda → TOTAL + gap final)."""
    h = _BAND_H + _GAP  # section band
    h += _ROW_H  # header ITEM/QTDE/...
    if simplified:
        h += _ROW_H  # display_name row
    else:
        if not items:
            h += _ROW_H + 2.0  # "(sem itens)" com o mesmo respiro das linhas
        else:
            # Aproxima quantas linhas o item tende a quebrar na largura _COL_ITEM.
            line_h = _LINE_H
            for item in items:
                name_len = max(1, len((item.name or "").strip()))
                est_lines = (name_len + 53) // 54  # baseline ~54 chars por linha
                est_lines = max(1, min(3, est_lines))
                h += max(_ROW_H + 2.0, est_lines * line_h + 2.0)

    labor = 0.0
    if include_labor:
        labor = labor_total(labor_hours, labor_rate)
        if labor > 0:
            h += _GAP + 3.6 + _ROW_H  # "Mao de obra" label + row

    items_total = sum(float(i.total_value) for i in items)
    section_subtotal = round_money(items_total + labor)
    discount, _net = apply_section_discount(section_subtotal, discount_pct, discount_value)

    notes_clean_est = (notes or "").strip()
    n_right = 1 + (1 if discount > 0 else 0)  # TOTAL [+ desconto]
    pay_est = _safe(format_payment_plan_label(payment_plan)).strip()
    n_right += (1 if pay_est and pay_est != "-" else 0) + (1 if notes_clean_est else 0)
    _ = billed_by_name, billed_by_cnpj
    n_left = len(installments or [])
    n_pair_est = max(n_left, n_right)
    h += _GAP * 0.5 + n_pair_est * _ROW_H + _GAP * 0.5
    return h


def _payment_summary_row_count(module_nets: list[tuple[QuoteModule, float, float]]) -> int:
    """DADOS DE PAGAMENTO só imprime o box de total — 0 linhas por módulo."""
    _ = module_nets
    return 0


def _estimate_payment_summary_height(
    module_nets: list[tuple[QuoteModule, float, float]],
    monthly_section_ids: set[str] | None = None,
) -> float:
    """Altura: linhas TOTAL dos módulos de mensalidade + box VALOR TOTAL."""
    ids = monthly_section_ids or set()
    n_rows = sum(1 for m, _q, _n in module_nets if m.id in ids)
    return (
        _BAND_H
        + _GAP * 2
        + n_rows * (_ROW_H + 0.5)
        + _GAP * 2
        + _ROW_H
        + 5.0
        + _GAP * 4
    )


def _estimate_observations_height(notes: str | None) -> float:
    text = (notes or "").strip() or "-"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    max_lines = 12
    clipped = "\n".join(lines[:max_lines])
    if len(lines) > max_lines and len(clipped) > 480:
        clipped = clipped[:477] + "..."
    line_h = _LINE_H
    n_lines = max(1, clipped.count("\n") + 1)
    box_h = max(_ROW_H * 2, n_lines * line_h + 2.4)
    return _BAND_H + _GAP + box_h + _GAP


def _notes_with_disclaimer_and_ticket(quote: QuoteRead) -> str:
    """Retorna apenas as observações do orçamento, sem disclaimer hardcoded."""
    notes = (quote.notes or "").strip()
    # Seed do wizard não é observação do cliente
    if notes == DEFAULT_QUOTE_NOTES.strip():
        notes = ""
    return notes or "-"


def _estimate_signatures_height() -> float:
    """Assinaturas removidas do PDF — altura zero para keep-together."""
    return 0.0


def render_quote_pdf(
    quote: QuoteRead,
    dest: Path,
    *,
    issuer: QuotePdfIssuer | None = None,
    client: QuotePdfClient | None = None,
    version_number: int | None = None,
    monthly_draft_json: str | None = None,
    technician_name: str | None = None,
) -> None:
    """Grava PDF do orçamento em `dest` (arquivo já resolvido sob HUB_PDF_DIR)."""
    issuer = issuer or issuer_from_settings()
    client = client or client_from_quote(quote)
    monthly_exclude_total = 0.0
    monthly_rows: list[dict[str, Any]] = []
    license_ids: set[int] = set()
    if monthly_draft_json:
        try:
            draft = json.loads(str(monthly_draft_json))
        except (ValueError, TypeError):
            draft = {}
        allocs = draft.get("allocations") or []
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
                monthly_rows.append({"role": "product", "name": product, "amount": line_total, "item_id": iid})
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
                    if isinstance(c, dict) and round_money(float(c.get("amount") or 0)) > 0
                ]
        if license_ids:
            monthly_exclude_total = round_money(
                sum(float(i.total_value) for i in quote.items if i.id in license_ids)
            )

    monthly_section_ids: set[str] = set()
    items_by_id = {int(i.id): i for i in quote.items}
    for iid in license_ids:
        item = items_by_id.get(int(iid))
        if item:
            monthly_section_ids.add(item.section)
    for r in monthly_rows:
        if r.get("role") != "product":
            continue
        try:
            iid = int(r.get("item_id"))
        except (TypeError, ValueError):
            continue
        item = items_by_id.get(iid)
        if item:
            monthly_section_ids.add(item.section)

    pdf = _QuotePdf(format="A4", issuer=issuer)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=_FOOTER_MARGIN)
    pdf.set_margins(11, 9, 11)
    pdf.add_page()

    _write_header(pdf, quote, issuer, version_number=version_number)
    client_name = (client.legal_name or quote.client_name or "").strip() or "-"
    _ensure_space(pdf, _estimate_client_block_height(name=client_name))
    _write_client_block(pdf, quote, client, technician_name=technician_name)

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
            payment_plan=mod.payment_plan,
            installments=[
                i.model_dump() if hasattr(i, "model_dump") else i
                for i in (mod.installments_json or [])
            ]
            if getattr(mod, "installments_json", None)
            else None,
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
            installments=[
                i.model_dump() if hasattr(i, "model_dump") else i
                for i in (mod.installments_json or [])
            ]
            if getattr(mod, "installments_json", None)
            else None,
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

    modules_by_id: dict[str, QuoteModule] = {m.id: m for m in modules}

    _ensure_space(pdf, _estimate_payment_summary_height(module_nets, monthly_section_ids))
    _write_payment_summary(
        pdf,
        module_nets=module_nets,
        exclude_total=monthly_exclude_total,
        monthly_section_ids=monthly_section_ids,
    )

    if monthly_rows:
        _ensure_space(
            pdf,
            _estimate_monthly_charges_height(monthly_rows, modules_by_id, quote.items, issuer.name),
        )
        _write_monthly_charges_section(
            pdf,
            rows=monthly_rows,
            modules_by_id=modules_by_id,
            items=quote.items,
            issuer_name=issuer.name,
        )

    notes_for_pdf = _notes_with_disclaimer_and_ticket(quote)
    _ensure_space(pdf, _estimate_observations_height(notes_for_pdf))
    _write_observations(pdf, notes_for_pdf)

    dest.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(dest))
    # region agent log
    try:
        import fpdf as _fpdf_mod
        import json as _json
        import time as _t

        raw = dest.read_bytes() if dest.is_file() else b""
        with open(
            "/Users/jean.nascimento/Projetos/avs-management/.cursor/debug-718b43.log",
            "a",
            encoding="utf-8",
        ) as _fh:
            _fh.write(
                _json.dumps(
                    {
                        "sessionId": "718b43",
                        "runId": "post-fix",
                        "hypothesisId": "H1-H2",
                        "location": "pdf.py:render_quote_pdf",
                        "message": "pdf written",
                        "data": {
                            "fpdfVersion": getattr(_fpdf_mod, "__version__", "?"),
                            "fpdfMod": getattr(_fpdf_mod, "__file__", "?")[-80:],
                            "uriCount": raw.count(b"/URI"),
                            "hasWame": b"wa.me" in raw,
                            "hasMailto": b"mailto:" in raw,
                            "hasAnnots": b"/Annots" in raw,
                        },
                        "timestamp": int(_t.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # endregion


def _draw_contact_line(
    pdf: _QuotePdf,
    issuer: QuotePdfIssuer,
    x: float,
    y: float,
    *,
    show_page: bool = True,
) -> None:
    """WhatsApp | e-mail | site com ícones, a partir de (x, y). Sem `|` no último item."""
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "", _FS_SMALL)
    icon_h = 3.2
    cursor = x

    def _contact_item(icon: Path, label: str, href: str | None = None) -> None:
        nonlocal cursor
        x0 = cursor
        if icon.is_file():
            pdf.image(str(icon), x=cursor, y=y + 0.1, h=icon_h)
            cursor += icon_h + 1.0
        if href:
            pdf.set_text_color(*_BLUE)
        pdf.set_xy(cursor, y)
        text_w = pdf.get_string_width(label) + 1.2
        pdf.cell(text_w, 3.4, label)
        if href:
            pdf.set_text_color(*_INK)
            pdf.link(x0, y, (cursor + text_w) - x0, 3.4, href)
        cursor += text_w

    items: list[tuple[Path, str, str | None]] = []
    if issuer.phone:
        label = _safe(issuer.phone).rstrip("|").strip()
        items.append((_ICON_WHATSAPP, label, _whatsapp_href(label)))
    if issuer.email:
        label = _safe(issuer.email).rstrip("|").strip()
        items.append((_ICON_MAIL, label, _mailto_href(label)))
    if issuer.site:
        label = _safe(issuer.site).rstrip("/").rstrip("|").strip()
        items.append((_ICON_GLOBE, label, _site_href(label)))
    # region agent log
    try:
        import json as _json
        import time as _t

        with open(
            "/Users/jean.nascimento/Projetos/avs-management/.cursor/debug-718b43.log",
            "a",
            encoding="utf-8",
        ) as _fh:
            _fh.write(
                _json.dumps(
                    {
                        "sessionId": "718b43",
                        "runId": "post-fix",
                        "hypothesisId": "H3-H5",
                        "location": "pdf.py:_draw_contact_line",
                        "message": "contact hrefs",
                        "data": {
                            "phoneDigits": _digits_only(issuer.phone)[-4:] if issuer.phone else "",
                            "phoneLen": len(_digits_only(issuer.phone)),
                            "waHref": bool(_whatsapp_href(_safe(issuer.phone).rstrip("|").strip()) if issuer.phone else None),
                            "mailHref": bool(items[1][2] if len(items) > 1 else None),
                            "siteHref": bool(items[-1][2] if items else None),
                            "iconWa": _ICON_WHATSAPP.is_file(),
                            "nItems": len(items),
                            "hrefs": [bool(h) for _, _, h in items],
                        },
                        "timestamp": int(_t.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # endregion
    for i, (icon, label, href) in enumerate(items):
        _contact_item(icon, label, href)
        if i < len(items) - 1:
            pdf.set_xy(cursor, y)
            pdf.cell(3.5, 3.4, "|")
            cursor += 3.5
    if show_page:
        _write_page_number(pdf, y)
    pdf.set_text_color(*_INK)


def _write_page_number(pdf: _QuotePdf, y: float) -> None:
    page_label = f"Pagina {pdf.page_no()}/{{nb}}"
    pdf.set_font("Helvetica", "I", _FS_MUTED)
    pdf.set_text_color(*_MUTED)
    pdf.set_xy(pdf.l_margin, y)
    pdf.cell(0, 3.4, page_label, align="L")
    pdf.set_text_color(*_INK)


def _write_header(
    pdf: _QuotePdf,
    quote: QuoteRead,
    issuer: QuotePdfIssuer,
    *,
    version_number: int | None = None,
) -> None:
    top_y = pdf.get_y()
    logo_h = 17.0
    logo_w = round(logo_h * 2.63, 1)  # 1965×746 → 44.7 mm
    has_logo = _LOGO_PATH.is_file()
    text_x = pdf.l_margin + (logo_w + 3.0 if has_logo else 0.0)

    usable = pdf.w - pdf.r_margin - text_x
    main_title = _safe(f"Orcamento : {quote_display_id(quote.id)}")
    ver_label = f"v{int(version_number)}" if version_number is not None else ""
    date_s = f"Data: {_fmt_date(quote.updated_at or quote.created_at)}"
    title_font_height = 5.8
    pdf.set_xy(text_x, top_y)
    pdf.set_font("Helvetica", "B", _FS_TITLE)
    pdf.set_text_color(*_INK)
    if ver_label:
        main_w = pdf.get_string_width(main_title)
        pdf.cell(main_w, title_font_height, main_title)
        pdf.set_x(text_x + main_w + 1.5)
        pdf.set_font("Helvetica", "B", _FS_TITLE * 0.75)
        pdf.cell(pdf.get_string_width(ver_label) + 1.5, title_font_height, ver_label)
        pdf.set_font("Helvetica", "B", _FS_BODY)
    else:
        pdf.cell(usable, title_font_height, main_title)
    pdf.set_xy(text_x, top_y)
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.cell(usable, title_font_height, _safe(date_s), align="R", new_x="LMARGIN", new_y="NEXT")

    ie = (issuer.ie or "").strip()
    line1 = f"{issuer.name} - CNPJ: {issuer.cnpj}"
    if ie:
        line1 = f"{line1} | Insc Estadual: {ie}"
    pdf.set_x(text_x)
    pdf.set_font("Helvetica", "B", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(pdf.w - pdf.r_margin - text_x, 4.0, _safe(line1))

    address = (issuer.address_line or "").strip()
    if address:
        pdf.set_x(text_x)
        pdf.set_font("Helvetica", "", _FS_SMALL)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(pdf.w - pdf.r_margin - text_x, 3.6, _safe(address))
    contact_y = pdf.get_y()
    _draw_contact_line(pdf, issuer, text_x, contact_y, show_page=False)
    pdf.set_y(contact_y + 4.2)

    text_bottom = pdf.get_y()
    text_h = text_bottom - top_y
    logo_y = top_y + max(0.0, (text_h - logo_h) / 2.0)
    if has_logo:
        pdf.image(str(_LOGO_PATH), x=pdf.l_margin, y=logo_y, w=logo_w, h=logo_h)

    pdf.set_text_color(*_INK)
    content_y = max(text_bottom, logo_y + logo_h if has_logo else text_bottom)
    pdf.set_y(content_y + _GAP)
    _rule(pdf, color=_RULE, width=0.35)


def _estimate_client_block_height(name: str | None = None) -> float:
    cleaned = (name or "").strip()
    n_lines = max(1, min(4, (len(cleaned) + 39) // 40)) if cleaned else 1
    name_h = max(_ROW_H, n_lines * _LINE_H)
    return _BAND_H + name_h + (_ROW_H * 2) + _GAP * 2


def _write_client_block(
    pdf: _QuotePdf,
    quote: QuoteRead,
    client: QuotePdfClient,
    *,
    technician_name: str | None = None,
) -> None:
    _section_band(pdf, "DADOS DO CLIENTE", _NAVY)
    name = (client.legal_name or quote.client_name or "").strip() or "-"
    cnpj = client.cnpj or format_cnpj(quote.cnpj) or quote.cnpj
    tech = (technician_name or "").strip() or "-"
    label_w = 25.0
    left_w = _CONTENT_W * 0.50
    value_w = left_w - label_w
    y_start = pdf.get_y()

    pdf.set_font("Helvetica", "", _FS_BODY)
    name_lines = _wrap_text_lines(pdf, _dash(name), value_w)
    name_h = max(_ROW_H, len(name_lines) * _LINE_H)
    y_name = pdf.get_y()
    pdf.set_font("Helvetica", "B", _FS_SMALL)
    pdf.set_text_color(*_BLUE)
    pdf.cell(label_w, name_h, _safe("Cliente:"))
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.set_xy(pdf.l_margin + label_w, y_name)
    pdf.multi_cell(value_w, _LINE_H, "\n".join(name_lines))
    pdf.set_xy(pdf.l_margin, y_name + name_h)

    for label, value in (("CNPJ:", cnpj), ("Vendedor:", tech)):
        pdf.set_font("Helvetica", "B", _FS_SMALL)
        pdf.set_text_color(*_BLUE)
        pdf.cell(label_w, _ROW_H, _safe(label))
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(left_w - label_w, _ROW_H, _dash(value), new_x="LMARGIN", new_y="NEXT")
    y_after_left = pdf.get_y()

    contact_name = getattr(quote, "contact_name", None) or ""
    contact_email = (client.email or "").strip()
    contact_phone = (client.phone or "").strip()
    right_rows: list[tuple[str, str]] = []
    if contact_name:
        right_rows.append(("Contato:", str(contact_name)))
    if contact_email:
        right_rows.append(("E-mail:", contact_email))
    if contact_phone:
        right_rows.append(("Telefone:", contact_phone))

    if right_rows:
        right_x = pdf.l_margin + left_w
        right_label_w = 18.0
        for i, (lbl, val) in enumerate(right_rows):
            y_row = y_start + i * (_ROW_H + 0.8)
            pdf.set_xy(right_x, y_row)
            pdf.set_font("Helvetica", "B", _FS_SMALL)
            pdf.set_text_color(*_BLUE)
            pdf.cell(right_label_w, _ROW_H, _safe(lbl))
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.set_text_color(*_INK)
            pdf.cell(_CONTENT_W - left_w - right_label_w, _ROW_H, _safe(val)[:60])
        y_after_right = y_start + len(right_rows) * (_ROW_H + 0.8)
        pdf.set_y(max(y_after_left, y_after_right))
    else:
        pdf.set_y(y_after_left)
    pdf.ln(_GAP)


def _write_divider(pdf: _QuotePdf) -> None:
    pdf.ln(_GAP * 2)


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
    right: str | None = None,
) -> None:
    _ = color  # retrocompat: todas as seções usam _BLUE
    y = pdf.get_y()
    # Barra vertical fina à esquerda (1.2mm) — mesma altura da linha
    pdf.set_fill_color(*_BLUE)
    pdf.rect(pdf.l_margin, y, 1.2, _BAND_H, style="F")
    pdf.set_xy(pdf.l_margin + 3.0, y)
    pdf.set_font("Helvetica", "B", _FS_SECTION)
    pdf.set_text_color(*_BLUE)
    right_txt = _safe((right or "").strip())
    if right_txt:
        title_w = round(_CONTENT_W * 0.46, 2)
        rest_w = _CONTENT_W - 3.0 - title_w
        pdf.cell(title_w, _BAND_H, _safe(title))
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.cell(rest_w, _BAND_H, right_txt[:78], align="R", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, _BAND_H, _safe(title), new_x="LMARGIN", new_y="NEXT")
    # Linha na base da barra (não acima do demarcador)
    rule_y = y + _BAND_H
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, rule_y, pdf.w - pdf.r_margin, rule_y)
    pdf.set_y(rule_y)
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
    installments: list[dict[str, Any]] | None = None,
) -> None:
    billed_clean = (billed_by_name or "").strip()
    cnpj_clean = (billed_by_cnpj or "").strip()
    billed_label = billed_clean
    if cnpj_clean:
        pretty = format_cnpj(cnpj_clean) or cnpj_clean
        billed_label = f"{billed_clean} | CNPJ {pretty}" if billed_clean else f"CNPJ {pretty}"
    billed_right = (
        f"Faturado por: {_safe(billed_label)[:78]}" if (billed_clean or cnpj_clean) else None
    )
    _section_band(pdf, title, accent, right=billed_right)

    original_c_margin = pdf.c_margin
    pdf.c_margin = _CELL_PAD

    pdf.set_fill_color(*_HEADER_FILL)
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "B", _FS_SMALL)
    _set_box_stroke(pdf)

    items_total = sum(float(i.total_value) for i in items)
    pdf.cell(_COL_ITEM, _ROW_H, "ITEM", fill=True)
    pdf.cell(_COL_QTY, _ROW_H, "QTDE", align="C", fill=True)
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
        pdf.cell(_COL_UNIT, _ROW_H, _brl(items_total) + " ", align="R", fill=True)
        pdf.cell(
            _COL_TOTAL,
            _ROW_H,
            _brl(items_total) + " ",
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

            line_h = _LINE_H
            name_w = _COL_ITEM - _CELL_PAD
            name = _safe(item.name).replace("\n", " ").strip()
            lines = _wrap_text_lines(pdf, name, name_w)
            row_h = max(_ROW_H + 2.0, len(lines) * line_h + 2.0)

            # Fundo completo da célula ITEM
            pdf.rect(x_name, y0, _COL_ITEM, row_h, style="F")

            pdf.set_xy(x_name + _CELL_PAD, y0 + 1.4)
            pdf.multi_cell(
                name_w,
                line_h,
                "\n".join(lines),
                align="L",
            )

            pdf.set_xy(x_qty, y0)
            pdf.cell(_COL_QTY, row_h, f"{item.qty:g}", align="C", fill=True)
            pdf.set_xy(x_unit, y0)
            pdf.cell(_COL_UNIT, row_h, _brl(float(item.unit_value)) + " ", align="R", fill=True)
            pdf.set_xy(x_total, y0)
            pdf.cell(_COL_TOTAL, row_h, _brl(float(item.total_value)) + " ", align="R", fill=True)

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
    notes_clean = (notes or "").strip()
    installment_rows = installments or []
    lefts: list[str] = []
    for idx_inst, line in enumerate(installment_rows):
        due = str(line.get("due_date", "") if isinstance(line, dict) else "")
        amt = float(line.get("amount", 0) if isinstance(line, dict) else 0)
        due_fmt = due
        if due and len(due) == 10:
            try:
                parts = due.split("-")
                due_fmt = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except (IndexError, ValueError):
                pass
        lefts.append(f"Parcela {idx_inst + 1} ({due_fmt}) {_brl(amt)}")
    rights: list[tuple[str, str, str]] = []
    if discount > 0:
        rights.append(("Desconto", f"- {_brl(discount)} ", "body"))
    rights.append(("TOTAL", _brl(net) + " ", "bold"))
    _pay_compact = bool(pay and pay != "-")
    if _pay_compact:
        rights.append((f"Pagamento: {pay}", "", "muted"))
    if notes_clean:
        rights.append((f"Obs: {_safe(notes_clean)[:90]}", "", "muted"))
    pdf.ln(_GAP * 0.5)
    meta_w = round(_LABEL_W * 0.55, 2)
    tot_lab_w = round(_LABEL_W - meta_w, 2)
    n_pair = max(len(lefts), len(rights))
    for i in range(n_pair):
        left_txt = lefts[i] if i < len(lefts) else ""
        rlab, rval, style = rights[i] if i < len(rights) else ("", "", "body")
        if style == "bold":
            row_h = _ROW_H + 0.6
        elif style == "muted":
            row_h = _ROW_H - 1.0
        else:
            row_h = _ROW_H
        if style == "muted":
            pdf.set_font("Helvetica", "", _FS_MUTED)
            pdf.set_text_color(*_MUTED)
            pdf.cell(meta_w, row_h, left_txt, align="L")
            pdf.cell(tot_lab_w + _COL_TOTAL, row_h, rlab + " ", align="R", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(*_INK)
            continue
        pdf.set_font("Helvetica", "", _FS_MUTED)
        pdf.set_text_color(*_MUTED)
        pdf.cell(meta_w, row_h, left_txt, align="L")
        if style == "bold":
            pdf.set_font("Helvetica", "B", _FS_BODY)
            pdf.set_text_color(*_INK)
        else:
            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.set_text_color(*_INK)
        pdf.cell(tot_lab_w, row_h, rlab, align="R")
        pdf.cell(_COL_TOTAL, row_h, rval, align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)
    pdf.ln(_GAP * 0.5)
    pdf.c_margin = original_c_margin


def _write_payment_summary(
    pdf: _QuotePdf,
    *,
    module_nets: list[tuple[QuoteModule, float, float]],
    exclude_total: float = 0.0,
    monthly_section_ids: set[str] | None = None,
) -> None:
    """DADOS DE PAGAMENTO: TOTAL dos módulos de mensalidade + VALOR TOTAL DO ORCAMENTO."""
    monthly_section_ids = monthly_section_ids or set()
    quote_total = round_money(max(0.0, sum(net for _m, _q, net in module_nets) - float(exclude_total)))

    pdf.ln(_GAP)
    _section_band(pdf, "DADOS DE PAGAMENTO", _NAVY)
    original_c_margin = pdf.c_margin
    pdf.c_margin = _CELL_PAD

    def _amount_row(label: str, value: float) -> None:
        pdf.set_font("Helvetica", "", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(_LABEL_W, _ROW_H, _safe(label)[:60])
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.cell(_COL_TOTAL, _ROW_H, _brl(value) + " ", align="R", new_x="LMARGIN", new_y="NEXT")

    for mod, _qty, net in module_nets:
        if mod.id not in monthly_section_ids:
            continue
        _amount_row(f"TOTAL {_module_band_title(mod)}", net)

    pdf.ln(_GAP * 2)
    y_box = pdf.get_y()
    box_h = _ROW_H + 4.0
    pdf.set_fill_color(*_NAVY)
    pdf.rect(pdf.l_margin, y_box, _CONTENT_W, box_h, style="F")
    pdf.set_font("Helvetica", "B", _FS_SECTION + 2)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(pdf.l_margin + 3.0, y_box + 1.0)
    pdf.cell(_LABEL_W - 3.0, box_h - 2.0, "VALOR TOTAL DO ORCAMENTO", align="R")
    pdf.cell(_COL_TOTAL, box_h - 2.0, _brl(quote_total), align="R")
    pdf.set_xy(pdf.l_margin, y_box + box_h)
    pdf.set_text_color(*_INK)
    pdf.ln(_GAP * 2)
    pdf.c_margin = original_c_margin


def _estimate_monthly_charges_height(
    rows: list[dict[str, Any]],
    modules_by_id: dict[str, Any] | None = None,
    items: list[Any] | None = None,
    issuer_name: str = "AVS TECNOLOGIA",
) -> float:
    if not rows:
        return 0.0
    # Estimar número de grupos (fornecedores distintos)
    n_suppliers = 1  # mínimo 1 grupo
    if modules_by_id and items:
        items_by_id = {int(i.id): i for i in items}
        suppliers_seen: set[str] = set()
        for r in rows:
            if r.get("role") == "product" and r.get("item_id"):
                item = items_by_id.get(int(r["item_id"]))
                if item:
                    mod = modules_by_id.get(item.section)
                    billed = (mod.billed_by_name or "").strip() if mod and hasattr(mod, "billed_by_name") else ""
                    suppliers_seen.add(billed or issuer_name)
        if suppliers_seen:
            n_suppliers = len(suppliers_seen)

    n_products = sum(1 for r in rows if r.get("role") == "product")
    extra = sum(max(0, len(str(r.get("name") or "")) // 50) for r in rows)
    # Cada grupo: header (BAND_H) + itens + gap (sem subtotal por grupo)
    per_group = _BAND_H + _GAP * 2
    return (_GAP + _BAND_H +  # section band "MENSALIDADES"
            n_suppliers * per_group +  # group headers
            (n_products + extra) * _ROW_H +  # item rows
            _ROW_H + (_ROW_H + 5.0) +  # total row + box
            _GAP * 4)


def _write_monthly_charges_section(
    pdf: _QuotePdf,
    *,
    rows: list[dict[str, Any]],
    modules_by_id: dict[str, Any] | None = None,
    items: list[Any] | None = None,
    issuer_name: str = "AVS TECNOLOGIA",
) -> float:
    """Renderiza seção 'MENSALIDADES' agrupada por fornecedor (billed_by_name)."""
    if not rows:
        return 0.0

    modules_by_id = modules_by_id or {}
    items_by_id: dict[int, Any] = {}
    if items:
        items_by_id = {int(i.id): i for i in items}

    # ── Passo 1: Extrair product rows com seus item_ids ──
    # Cada product row corresponde a um item de licença.
    # Precisamos mapear: product → item.section → module.billed_by_name → supplier
    product_entries: list[dict[str, Any]] = []
    for r in rows:
        if r.get("role") == "product":
            product_entries.append({
                "name": str(r.get("name") or "-"),
                "amount": float(r.get("amount") or 0.0),
                "item_id": r.get("item_id"),  # pode não existir em dados legados
            })

    # ── Passo 2: Agrupar por fornecedor ──
    supplier_groups: dict[str, dict[str, Any]] = {}
    supplier_order: list[str] = []  # manter ordem de aparição

    for entry in product_entries:
        # Determinar o fornecedor
        supplier = issuer_name  # fallback: AVS
        item_id = entry.get("item_id")
        if item_id is not None and items_by_id:
            item = items_by_id.get(int(item_id))
            if item:
                mod = modules_by_id.get(item.section)
                if mod and hasattr(mod, "billed_by_name"):
                    billed = (mod.billed_by_name or "").strip()
                    if billed:
                        supplier = billed

        if supplier not in supplier_groups:
            supplier_groups[supplier] = {"items": [], "total": 0.0}
            supplier_order.append(supplier)
        supplier_groups[supplier]["items"].append(entry)
        supplier_groups[supplier]["total"] = round_money(
            supplier_groups[supplier]["total"] + entry["amount"]
        )

    # Se não conseguiu agrupar (dados legados sem item_id), fallback para layout flat
    if not product_entries:
        # Fallback: itens sem role=product (formato charges legado)
        total = 0.0
        for r in rows:
            amount = float(r.get("amount") or 0.0)
            total += amount
        supplier_groups = {issuer_name: {
            "items": [{"name": str(r.get("name") or "-"), "amount": float(r.get("amount") or 0.0)} for r in rows],
            "total": round_money(total),
        }}
        supplier_order = [issuer_name]

    # ── Passo 3: Renderizar ──
    _section_band(pdf, "MENSALIDADES", _NAVY)
    original_c_margin = pdf.c_margin
    pdf.c_margin = _CELL_PAD
    grand_total = 0.0

    for supplier in supplier_order:
        data = supplier_groups[supplier]
        grand_total += data["total"]

        # Sub-header com fundo cinza
        pdf.ln(_GAP)
        y_hdr = pdf.get_y()
        pdf.set_fill_color(*_HEADER_FILL)
        pdf.rect(pdf.l_margin, y_hdr, _CONTENT_W, _ROW_H + 1.0, style="F")
        pdf.set_draw_color(*_RULE)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, y_hdr + _ROW_H + 1.0, pdf.l_margin + _CONTENT_W, y_hdr + _ROW_H + 1.0)
        pdf.set_xy(pdf.l_margin + _CELL_PAD, y_hdr + 0.4)
        pdf.set_font("Helvetica", "B", _FS_BODY)
        pdf.set_text_color(*_INK)
        pdf.cell(_CONTENT_W - _CELL_PAD, _ROW_H, _safe(supplier))
        pdf.set_xy(pdf.l_margin, y_hdr + _ROW_H + 1.0)
        pdf.ln(0.5)

        # Itens com zebra
        for idx, entry in enumerate(data["items"]):
            y0 = pdf.get_y()
            name = _safe(str(entry["name"]).replace("\n", " ").strip() or "-")
            amount = float(entry["amount"])

            # Zebra
            if idx % 2 == 1:
                pdf.set_fill_color(*_ROW_ALT)
                pdf.rect(pdf.l_margin, y0, _CONTENT_W, _ROW_H + 0.6, style="F")

            pdf.set_font("Helvetica", "", _FS_BODY)
            pdf.set_text_color(*_INK)
            name_w = _LABEL_W - _CELL_PAD * 2
            wrapped = _wrap_text_lines(pdf, name, name_w)
            row_h = max(_ROW_H + 0.6, len(wrapped) * _LINE_H + 0.6)

            pdf.set_xy(pdf.l_margin + _CELL_PAD * 2, y0 + 0.3)
            pdf.multi_cell(name_w, _LINE_H, "\n".join(wrapped))
            pdf.set_xy(pdf.l_margin + _LABEL_W, y0)
            pdf.cell(_COL_TOTAL, row_h, _brl(amount) + " ", align="R")
            pdf.set_xy(pdf.l_margin, y0 + row_h)

        pdf.ln(_GAP)

    # ── Grand total ──
    grand_total = round_money(grand_total)

    pdf.ln(_GAP)
    y_box = pdf.get_y()
    box_h = _ROW_H + 4.0
    pdf.set_fill_color(*_NAVY)
    pdf.rect(pdf.l_margin, y_box, _CONTENT_W, box_h, style="F")
    pdf.set_font("Helvetica", "B", _FS_SECTION + 2)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(pdf.l_margin + 3.0, y_box + 1.0)
    pdf.cell(_LABEL_W - 3.0, box_h - 2.0, "TOTAL MENSALIDADES", align="R")
    pdf.cell(_COL_TOTAL, box_h - 2.0, _brl(grand_total), align="R")
    pdf.set_xy(pdf.l_margin, y_box + box_h)
    pdf.set_text_color(*_INK)
    pdf.ln(_GAP)

    pdf.c_margin = original_c_margin
    return 0.0


def _write_observations(pdf: _QuotePdf, notes: str | None) -> None:
    _section_band(pdf, "OBSERVACOES", _BLUE)
    text = (notes or "").strip() or "-"
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    max_lines = 12
    clipped = "\n".join(lines[:max_lines])
    if len(lines) > max_lines and len(clipped) > 480:
        clipped = clipped[:477] + "..."

    line_h = _LINE_H
    pdf.set_font("Helvetica", "", _FS_BODY)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(_CONTENT_W, line_h, _safe(clipped))
    pdf.ln(_GAP)

