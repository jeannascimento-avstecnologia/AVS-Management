"""P&L interno do orçamento (passo 3). Não entra no PDF."""

from __future__ import annotations

import json
from typing import Any, Literal

from src.quotes.schemas import (
    QuoteMarginLine,
    QuoteMarginModule,
    QuoteMarginRead,
    QuoteMarginRecurring,
    QuoteMarginTotals,
    QuoteModule,
    QuoteMonthlyDraftWrite,
    QuoteRead,
)
from src.quotes.totals import apply_section_discount, labor_total, round_money

MarginKind = Literal["implantacao", "licenca", "produto"]

_LICENSE_NEEDLES = ("licen", "m365", "microsoft 365", "backup")


def effective_analyst_hourly_cost(
    stored: float | None,
    default: float,
) -> float:
    """null usa default; 0 persistido é override válido."""
    if stored is None:
        return round_money(max(0.0, float(default)))
    return round_money(max(0.0, float(stored)))


def infer_margin_kind(
    *,
    tipo_produto: str | None,
    name: str,
) -> MarginKind | None:
    tipo = (tipo_produto or "").strip().casefold()
    if tipo in {"servico", "serviço", "service"}:
        return "implantacao"
    if tipo in {"produto", "product"}:
        needle = (name or "").casefold()
        if any(token in needle for token in _LICENSE_NEEDLES):
            return "licenca"
        return "produto"
    return None


def infer_margin_kind_from_product(
    product: dict[str, Any] | None,
    *,
    fallback_name: str,
) -> MarginKind | None:
    if not product:
        return None
    tipo = product.get("tipo_produto")
    if tipo is None and product.get("kind") == "servico":
        tipo = "Servico"
    elif tipo is None and product.get("kind") == "produto":
        tipo = "Produto"
    name = str(product.get("name") or fallback_name)
    return infer_margin_kind(tipo_produto=str(tipo) if tipo else None, name=name)


def _module_title(modules: list[QuoteModule], section: str) -> str:
    for mod in modules:
        if mod.id == section:
            return mod.title
    return section.replace("_", " ").title()


def _parse_monthly_ids(raw: str | None) -> set[int]:
    if not raw or not str(raw).strip():
        return set()
    try:
        data = QuoteMonthlyDraftWrite.model_validate(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return set()
    return {a.item_id for a in data.allocations}


def _parse_monthly_draft(raw: str | None) -> QuoteMonthlyDraftWrite:
    if not raw or not str(raw).strip():
        return QuoteMonthlyDraftWrite(allocations=[])
    try:
        return QuoteMonthlyDraftWrite.model_validate(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return QuoteMonthlyDraftWrite(allocations=[])


def _margin_pct(profit: float, revenue: float) -> float | None:
    if revenue <= 0:
        return None
    return round_money((profit / revenue) * 100.0)


def _module_hours_and_rate(
    mod: QuoteModule,
    quote: QuoteRead,
    *,
    show_implant_labor: bool,
    default_rate: float,
) -> tuple[float | None, float | None, float, float]:
    hours = mod.internal_labor_hours
    rate_stored = mod.internal_hourly_cost
    if show_implant_labor and hours is None and rate_stored is None:
        hours = quote.implementation_hours
        rate_stored = quote.analyst_hourly_cost
    effective = effective_analyst_hourly_cost(rate_stored, default_rate)
    hours_val = max(0.0, float(hours or 0.0)) if show_implant_labor else 0.0
    labor_cost = round_money(hours_val * effective) if show_implant_labor else 0.0
    return hours, rate_stored, labor_cost, effective


def compute_quote_margin(
    quote: QuoteRead,
    *,
    default_analyst_hourly_cost: float,
) -> QuoteMarginRead:
    recurring_ids = _parse_monthly_ids(quote.monthly_draft_json)
    draft = _parse_monthly_draft(quote.monthly_draft_json)
    by_section: dict[str, list[Any]] = {}
    for item in quote.items:
        by_section.setdefault(item.section, []).append(item)

    incomplete = False
    lines: list[QuoteMarginLine] = []
    modules_out: list[QuoteMarginModule] = []
    canvas_labor = 0.0
    tot_rev = 0.0
    tot_cogs = 0.0
    tot_labor = 0.0
    tot_hours = 0.0

    default_rate = round_money(max(0.0, float(default_analyst_hourly_cost)))

    for mod in quote.modules:
        items = by_section.get(mod.id, [])
        items_total = round_money(sum(float(i.total_value) for i in items))
        labor = (
            labor_total(mod.labor_hours, mod.labor_hourly_rate) if mod.show_labor else 0.0
        )
        if mod.show_labor:
            canvas_labor = round_money(canvas_labor + max(0.0, float(mod.labor_hours or 0.0)))
        subtotal = round_money(items_total + labor)
        _discount, net = apply_section_discount(
            subtotal, mod.discount_pct, mod.discount_value
        )
        labor_net = 0.0
        if subtotal > 0 and labor > 0:
            labor_net = round_money(net * (labor / subtotal))

        show_implant = mod.legacy_kind == "implantacao" or any(
            getattr(i, "margin_kind", None) == "implantacao" for i in items
        )
        hours, rate_stored, labor_cost, effective = _module_hours_and_rate(
            mod, quote, show_implant_labor=show_implant, default_rate=default_rate
        )

        mod_rev = 0.0
        mod_cogs = 0.0
        if mod.id != "mensalidade":
            mod_rev = round_money(mod_rev + labor_net)

        mod_lines: list[QuoteMarginLine] = []
        for item in items:
            item_rev = 0.0
            if subtotal > 0:
                item_rev = round_money(net * (float(item.total_value) / subtotal))
            cost_missing = item.unit_cost is None
            cost = 0.0 if cost_missing else round_money(float(item.unit_cost) * float(item.qty))
            bucket: Literal["oneshot", "recurring"] = (
                "recurring" if item.id in recurring_ids else "oneshot"
            )
            if bucket == "oneshot":
                mod_rev = round_money(mod_rev + item_rev)
                mod_cogs = round_money(mod_cogs + cost)
                if cost_missing and item.margin_kind != "implantacao":
                    incomplete = True
            line = QuoteMarginLine(
                item_id=item.id,
                section=item.section,
                section_title=mod.title,
                name=item.name,
                bucket=bucket,
                qty=float(item.qty),
                revenue=item_rev,
                cost=cost,
                profit=round_money(item_rev - cost),
                cost_missing=cost_missing,
                margin_kind=item.margin_kind,
                unit_value=float(item.unit_value),
                unit_cost=item.unit_cost,
            )
            mod_lines.append(line)
            lines.append(line)

        if show_implant:
            tot_hours = round_money(tot_hours + max(0.0, float(hours or 0.0)))
        mod_profit = round_money(mod_rev - mod_cogs - labor_cost)
        tot_rev = round_money(tot_rev + mod_rev)
        tot_cogs = round_money(tot_cogs + mod_cogs)
        tot_labor = round_money(tot_labor + labor_cost)
        modules_out.append(
            QuoteMarginModule(
                id=mod.id,
                title=mod.title,
                legacy_kind=mod.legacy_kind,
                show_implant_labor=show_implant,
                revenue=mod_rev,
                cogs=mod_cogs,
                labor_cost=labor_cost,
                profit=mod_profit,
                hours=hours if show_implant else None,
                rate=rate_stored if show_implant else None,
                effective_rate=effective if show_implant else default_rate,
                items=mod_lines,
            )
        )

    oneshot_profit = round_money(tot_rev - tot_cogs - tot_labor)
    rec_revenue = round_money(
        sum(a.fornecedor_amount + a.intermediador_amount for a in draft.allocations)
    )
    rec_forn = round_money(sum(a.fornecedor_amount for a in draft.allocations))
    rec_inter = round_money(sum(a.intermediador_amount for a in draft.allocations))

    quote_rate = effective_analyst_hourly_cost(quote.analyst_hourly_cost, default_rate)

    return QuoteMarginRead(
        quote_id=quote.id,
        incomplete=incomplete,
        default_analyst_hourly_cost=default_rate,
        analyst_hourly_cost=quote.analyst_hourly_cost,
        effective_analyst_hourly_cost=quote_rate,
        implementation_hours=quote.implementation_hours,
        canvas_labor_hours=canvas_labor,
        oneshot=QuoteMarginTotals(
            revenue=tot_rev,
            cogs=tot_cogs,
            labor_cost=tot_labor,
            profit=oneshot_profit,
            hours=tot_hours,
            margin_pct=_margin_pct(oneshot_profit, tot_rev),
        ),
        recurring=QuoteMarginRecurring(
            revenue=rec_revenue,
            fornecedor=rec_forn,
            intermediador=rec_inter,
        ),
        modules=modules_out,
        lines=lines,
    )


def unit_cost_from_product(product: dict[str, Any] | None) -> float | None:
    if not product:
        return None
    raw = product.get("cost_value")
    if raw is None:
        return None
    try:
        return round_money(max(0.0, float(raw)))
    except (TypeError, ValueError):
        return None
