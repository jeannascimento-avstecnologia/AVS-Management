"""Cálculo de subtotal / desconto de seções do orçamento."""

from __future__ import annotations


def round_money(value: float) -> float:
    return round(value, 2)


def labor_total(hours: float | None, hourly_rate: float | None) -> float:
    h = max(0.0, float(hours or 0.0))
    rate = max(0.0, float(hourly_rate or 0.0))
    return round_money(h * rate)


def apply_section_discount(
    subtotal: float,
    discount_pct: float | None = None,
    discount_value: float | None = None,
) -> tuple[float, float]:
    """Retorna (desconto_total, líquido).

    Orçamento: % e R$ são espelhos do mesmo desconto (não soma).
    Preferência: R$ se > 0; senão aplica %.
    """
    base = max(0.0, float(subtotal))
    pct = max(0.0, float(discount_pct or 0.0))
    fixed = max(0.0, float(discount_value or 0.0))
    if fixed > 0:
        discount = round_money(min(fixed, base))
    elif pct > 0:
        discount = round_money(base * (min(pct, 100.0) / 100.0))
    else:
        discount = 0.0
    net = round_money(max(0.0, base - discount))
    return discount, net


def apply_stacked_discount(
    subtotal: float,
    discount_pct: float | None = None,
    discount_value: float | None = None,
) -> tuple[float, float]:
    """Faturamento: aplica % sobre o subtotal e depois R$ fixo."""
    base = max(0.0, float(subtotal))
    pct = max(0.0, float(discount_pct or 0.0))
    fixed = max(0.0, float(discount_value or 0.0))
    from_pct = base * (min(pct, 100.0) / 100.0)
    discount = round_money(from_pct + fixed)
    net = round_money(max(0.0, base - discount))
    return discount, net


def format_brl(value: float) -> str:
    formatted = f"{round_money(value):,.2f}"
    return f"R$ {formatted.replace(',', 'X').replace('.', ',').replace('X', '.')}"


def parcel_count_from_plan(value: str | None) -> int | None:
    """N de parcelas se o plano for parcelado; None para à vista / recorrente / vazio."""
    raw = (value or "").strip().lower()
    if not raw:
        return None
    if raw in {"a_vista", "avista", "à vista"}:
        return None
    if raw in {"recorrente_anual", "recorrente-anual", "anual"} or raw.startswith("recorrente_"):
        return None
    if raw.startswith("parcelado_"):
        raw = raw.removeprefix("parcelado_")
    if raw.endswith("_sem_juros"):
        raw = raw[: -len("_sem_juros")]
    if raw.endswith("x") and raw[:-1].isdigit():
        n = int(raw[:-1])
        return n if n >= 1 else None
    return None


def format_payment_plan_label(
    value: str | None,
    module_net: float | None = None,
) -> str:
    """Rótulo legível do plano (PDF / UI).

    Parcelado + `module_net`: `Parcelado em Nx de R$ …` (líquido / N, round 2).
    Sem `module_net`: rótulo curto legado (`Parcelado 12x`).
    """
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    if raw in {"a_vista", "avista", "à vista"}:
        return "À vista"
    if raw in {"recorrente_anual", "recorrente-anual", "anual"}:
        return "Recorrente"
    if raw.startswith("recorrente_") and raw.endswith("x"):
        n = raw.removeprefix("recorrente_")[:-1]
        if n.isdigit():
            return f"Recorrente {n}x"
    n_parcels = parcel_count_from_plan(value)
    if n_parcels is not None and module_net is not None:
        per = round_money(float(module_net) / n_parcels) if n_parcels else 0.0
        return f"Parcelado em {n_parcels}x de {format_brl(per)}"
    if raw in {"3x_sem_juros", "3x"}:
        return "Parcelado 3x"
    if raw in {"6x_sem_juros", "6x"}:
        return "Parcelado 6x"
    if raw.endswith("x") and raw[:-1].isdigit():
        return f"Parcelado {raw}"
    if raw.startswith("parcelado_"):
        n = raw.removeprefix("parcelado_")
        if n.endswith("x") and n[:-1].isdigit():
            return f"Parcelado {n}"
    return (value or "").strip()
