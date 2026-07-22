"""Busca local hub.db + enriquecimento opcional TiFlux/VHSYS."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from src.cnpj.validator import normalize_cnpj
from src.config import Settings, get_settings
from src.documents.schemas import (
    DocumentBillingHit,
    DocumentPdfHit,
    DocumentQuoteHit,
    DocumentsEnrichment,
    DocumentsSearchResponse,
)
from src.hub.models import HubDatabase
from src.integrations.tiflux_client import TifluxApiError, TifluxClient
from src.integrations.vhsys_client import VhsysApiError, VhsysClient
from src.quotes.totals import apply_section_discount, labor_total, round_money

_M_ID_RE = re.compile(r"^M(\d+)$", re.IGNORECASE)
_OS_RE = re.compile(r"^(?:OS|VHSYS)[:\s#\-]*(\d+)$", re.IGNORECASE)
_PURE_INT_RE = re.compile(r"^\d{1,12}$")

_QUOTE_COLS = (
    "id, cnpj, client_name, status, lead_temperature, billed_by_type, billed_by_name, "
    "vhsys_os_id, tiflux_ticket_number, tiflux_client_id, pdf_path, "
    "implant_discount_pct, implant_discount_value, "
    "monthly_discount_pct, monthly_discount_value, "
    "monthly_labor_hours, monthly_labor_hourly_rate, "
    "created_at, updated_at"
)

_BILLING_COLS = (
    "id, cnpj, client_name, competence, status, net_total, gross_total, due_date, "
    "payment_method, vhsys_nf_id, vhsys_cr_id, tiflux_ticket_number, tiflux_client_id, "
    "created_at, updated_at"
)


@dataclass
class _ParsedQuery:
    raw: str
    quote_id: int | None = None
    os_id: str | None = None
    cnpj: str | None = None
    numeric_id: int | None = None
    name_term: str | None = None


@dataclass
class _ExtraKeys:
    cnpjs: set[str] = field(default_factory=set)
    tiflux_ids: set[int] = field(default_factory=set)
    vhsys_os_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class _QuoteNets:
    implant_net: float
    monthly_net: float
    value_total: float


def parse_documents_query(q: str) -> _ParsedQuery:
    raw = (q or "").strip()
    parsed = _ParsedQuery(raw=raw)
    if not raw:
        return parsed

    m_match = _M_ID_RE.match(raw)
    if m_match:
        parsed.quote_id = int(m_match.group(1))
        return parsed

    os_match = _OS_RE.match(raw)
    if os_match:
        parsed.os_id = os_match.group(1)
        return parsed

    digits = normalize_cnpj(raw)
    if len(digits) == 14 and digits.isdigit():
        parsed.cnpj = digits
        return parsed

    if _PURE_INT_RE.match(raw):
        parsed.numeric_id = int(raw)
        parsed.os_id = raw
        return parsed

    parsed.name_term = raw
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _section_sums(
    conn: sqlite3.Connection, quote_ids: list[int]
) -> dict[int, dict[str, float]]:
    """Soma total_value por quote_id × section."""
    out: dict[int, dict[str, float]] = {qid: {} for qid in quote_ids}
    if not quote_ids:
        return out
    placeholders = ",".join("?" for _ in quote_ids)
    rows = conn.execute(
        f"SELECT quote_id, section, SUM(total_value) AS section_sum "
        f"FROM quote_items WHERE quote_id IN ({placeholders}) "
        f"GROUP BY quote_id, section",
        quote_ids,
    ).fetchall()
    for row in rows:
        qid = int(row["quote_id"])
        section = str(row["section"])
        out.setdefault(qid, {})[section] = float(row["section_sum"] or 0.0)
    return out


def _nets_for_quote(row: sqlite3.Row, section_sums: dict[str, float]) -> _QuoteNets:
    implant_sub = round_money(float(section_sums.get("implantacao", 0.0)))
    _, implant_net = apply_section_discount(
        implant_sub,
        _optional_float(row["implant_discount_pct"]),
        _optional_float(row["implant_discount_value"]),
    )
    monthly_items = float(section_sums.get("mensalidade", 0.0))
    monthly_labor = labor_total(
        _optional_float(row["monthly_labor_hours"]),
        _optional_float(row["monthly_labor_hourly_rate"]),
    )
    monthly_sub = round_money(monthly_items + monthly_labor)
    _, monthly_net = apply_section_discount(
        monthly_sub,
        _optional_float(row["monthly_discount_pct"]),
        _optional_float(row["monthly_discount_value"]),
    )
    return _QuoteNets(
        implant_net=implant_net,
        monthly_net=monthly_net,
        value_total=round_money(implant_net + monthly_net),
    )


def _quote_hit(row: sqlite3.Row, nets: _QuoteNets) -> DocumentQuoteHit:
    quote_id = int(row["id"])
    pdf_path = row["pdf_path"]
    return DocumentQuoteHit(
        id=quote_id,
        display_id=f"M{quote_id}",
        doc_type="orcamento",
        cnpj=str(row["cnpj"]),
        client_name=row["client_name"],
        status=str(row["status"]),
        lead_temperature=_optional_str(row["lead_temperature"]),
        billed_by_type=_optional_str(row["billed_by_type"]),
        billed_by_name=_optional_str(row["billed_by_name"]),
        vhsys_os_id=row["vhsys_os_id"],
        tiflux_ticket_number=row["tiflux_ticket_number"],
        tiflux_client_id=_optional_int(row["tiflux_client_id"]),
        has_pdf=bool(pdf_path),
        implant_net=nets.implant_net,
        monthly_net=nets.monthly_net,
        value_total=nets.value_total,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _pdf_hit(row: sqlite3.Row, nets: _QuoteNets) -> DocumentPdfHit | None:
    pdf_path = row["pdf_path"]
    if not pdf_path:
        return None
    quote_id = int(row["id"])
    return DocumentPdfHit(
        quote_id=quote_id,
        display_id=f"M{quote_id}",
        doc_type="pdf",
        client_name=row["client_name"],
        cnpj=str(row["cnpj"]),
        status=str(row["status"]),
        lead_temperature=_optional_str(row["lead_temperature"]),
        billed_by_type=_optional_str(row["billed_by_type"]),
        billed_by_name=_optional_str(row["billed_by_name"]),
        vhsys_os_id=row["vhsys_os_id"],
        tiflux_ticket_number=row["tiflux_ticket_number"],
        has_pdf=True,
        value_total=nets.value_total,
        pdf_path=str(pdf_path),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _billing_hit(row: sqlite3.Row) -> DocumentBillingHit:
    return DocumentBillingHit(
        id=int(row["id"]),
        doc_type="faturamento",
        cnpj=str(row["cnpj"]),
        client_name=row["client_name"],
        competence=str(row["competence"]),
        status=str(row["status"]),
        net_total=_optional_float(row["net_total"]),
        gross_total=_optional_float(row["gross_total"]),
        due_date=_optional_str(row["due_date"]),
        payment_method=_optional_str(row["payment_method"]),
        vhsys_nf_id=row["vhsys_nf_id"],
        vhsys_cr_id=row["vhsys_cr_id"],
        tiflux_ticket_number=row["tiflux_ticket_number"],
        tiflux_client_id=_optional_int(row["tiflux_client_id"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _dedupe_quotes(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[int] = set()
    out: list[sqlite3.Row] = []
    for row in rows:
        qid = int(row["id"])
        if qid in seen:
            continue
        seen.add(qid)
        out.append(row)
    return out


def _dedupe_billing(rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
    seen: set[int] = set()
    out: list[sqlite3.Row] = []
    for row in rows:
        rid = int(row["id"])
        if rid in seen:
            continue
        seen.add(rid)
        out.append(row)
    return out


class DocumentsService:
    def __init__(self, db: HubDatabase, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()

    def _hits_from_rows(
        self,
        conn: sqlite3.Connection,
        quote_rows: list[sqlite3.Row],
        billing_rows: list[sqlite3.Row],
        *,
        limit: int,
    ) -> tuple[list[DocumentQuoteHit], list[DocumentPdfHit], list[DocumentBillingHit]]:
        quote_slice = quote_rows[:limit]
        quote_ids = [int(r["id"]) for r in quote_slice]
        sums = _section_sums(conn, quote_ids)
        quotes: list[DocumentQuoteHit] = []
        pdfs: list[DocumentPdfHit] = []
        for row in quote_slice:
            nets = _nets_for_quote(row, sums.get(int(row["id"]), {}))
            quotes.append(_quote_hit(row, nets))
            pdf = _pdf_hit(row, nets)
            if pdf is not None:
                pdfs.append(pdf)
        billing = [_billing_hit(r) for r in billing_rows[:limit]]
        return quotes, pdfs, billing

    def search_local(
        self,
        parsed: _ParsedQuery,
        *,
        include_quotes: bool,
        include_billing: bool,
        limit: int,
        extra: _ExtraKeys | None = None,
    ) -> tuple[list[DocumentQuoteHit], list[DocumentPdfHit], list[DocumentBillingHit]]:
        limit = max(1, min(limit, 100))
        extra = extra or _ExtraKeys()
        quote_rows: list[sqlite3.Row] = []
        billing_rows: list[sqlite3.Row] = []

        with self._db.connect() as conn:
            if include_quotes:
                quote_rows = self._search_quotes(conn, parsed, limit=limit, extra=extra)
            if include_billing:
                billing_rows = self._search_billing(conn, parsed, limit=limit, extra=extra)
            return self._hits_from_rows(conn, quote_rows, billing_rows, limit=limit)

    def list_recent(
        self,
        *,
        include_quotes: bool,
        include_billing: bool,
        limit: int = 50,
    ) -> DocumentsSearchResponse:
        limit = max(1, min(limit, 100))
        quote_rows: list[sqlite3.Row] = []
        billing_rows: list[sqlite3.Row] = []

        with self._db.connect() as conn:
            if include_quotes:
                quote_rows = list(
                    conn.execute(
                        f"SELECT {_QUOTE_COLS} FROM quotes "
                        f"ORDER BY updated_at DESC, id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                )
            if include_billing:
                billing_rows = list(
                    conn.execute(
                        f"SELECT {_BILLING_COLS} FROM billing_runs "
                        f"ORDER BY updated_at DESC, id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                )
            quotes, pdfs, billing = self._hits_from_rows(
                conn, quote_rows, billing_rows, limit=limit
            )

        return DocumentsSearchResponse(
            query="",
            quotes=quotes if include_quotes else [],
            pdfs=pdfs if include_quotes else [],
            billing_runs=billing if include_billing else [],
            enrichment=DocumentsEnrichment(),
        )

    def _search_quotes(
        self,
        conn: sqlite3.Connection,
        parsed: _ParsedQuery,
        *,
        limit: int,
        extra: _ExtraKeys,
    ) -> list[sqlite3.Row]:
        cols = _QUOTE_COLS
        rows: list[sqlite3.Row] = []

        if parsed.quote_id is not None:
            row = conn.execute(
                f"SELECT {cols} FROM quotes WHERE id = ?",
                (parsed.quote_id,),
            ).fetchone()
            return [row] if row else []

        clauses: list[str] = []
        params: list[Any] = []

        if parsed.cnpj:
            clauses.append("cnpj = ?")
            params.append(parsed.cnpj)

        if parsed.os_id:
            clauses.append("vhsys_os_id = ?")
            params.append(parsed.os_id)

        if parsed.numeric_id is not None:
            clauses.append("id = ?")
            params.append(parsed.numeric_id)
            clauses.append("tiflux_ticket_number = ?")
            params.append(str(parsed.numeric_id))
            clauses.append("CAST(tiflux_client_id AS TEXT) = ?")
            params.append(str(parsed.numeric_id))

        if parsed.name_term:
            clauses.append("client_name LIKE ? COLLATE NOCASE")
            params.append(f"%{parsed.name_term}%")

        for cnpj in extra.cnpjs:
            clauses.append("cnpj = ?")
            params.append(cnpj)
        for tid in extra.tiflux_ids:
            clauses.append("tiflux_client_id = ?")
            params.append(tid)
        for os_id in extra.vhsys_os_ids:
            clauses.append("vhsys_os_id = ?")
            params.append(os_id)

        if not clauses:
            return []

        sql = (
            f"SELECT {cols} FROM quotes WHERE ({' OR '.join(clauses)}) "
            f"ORDER BY updated_at DESC, id DESC LIMIT ?"
        )
        params.append(limit)
        rows = list(conn.execute(sql, params).fetchall())
        return _dedupe_quotes(rows)

    def _search_billing(
        self,
        conn: sqlite3.Connection,
        parsed: _ParsedQuery,
        *,
        limit: int,
        extra: _ExtraKeys,
    ) -> list[sqlite3.Row]:
        cols = _BILLING_COLS

        # M{id} é exclusivo de orçamento
        if parsed.quote_id is not None:
            return []

        clauses: list[str] = []
        params: list[Any] = []

        if parsed.cnpj:
            clauses.append("cnpj = ?")
            params.append(parsed.cnpj)

        if parsed.numeric_id is not None:
            clauses.append("id = ?")
            params.append(parsed.numeric_id)
            clauses.append("tiflux_ticket_number = ?")
            params.append(str(parsed.numeric_id))
            clauses.append("CAST(tiflux_client_id AS TEXT) = ?")
            params.append(str(parsed.numeric_id))
            clauses.append("vhsys_nf_id = ?")
            params.append(str(parsed.numeric_id))
            clauses.append("vhsys_cr_id = ?")
            params.append(str(parsed.numeric_id))

        if parsed.name_term:
            clauses.append("client_name LIKE ? COLLATE NOCASE")
            params.append(f"%{parsed.name_term}%")

        for cnpj in extra.cnpjs:
            clauses.append("cnpj = ?")
            params.append(cnpj)
        for tid in extra.tiflux_ids:
            clauses.append("tiflux_client_id = ?")
            params.append(tid)

        if not clauses:
            return []

        sql = (
            f"SELECT {cols} FROM billing_runs WHERE ({' OR '.join(clauses)}) "
            f"ORDER BY competence DESC, updated_at DESC, id DESC LIMIT ?"
        )
        params.append(limit)
        rows = list(conn.execute(sql, params).fetchall())
        return _dedupe_billing(rows)

    async def enrich_keys(self, parsed: _ParsedQuery) -> tuple[_ExtraKeys, DocumentsEnrichment]:
        """Expande busca via TiFlux (nome/CNPJ) e VHSYS (OS). Degrada gracioso."""
        extra = _ExtraKeys()
        enrichment = DocumentsEnrichment()
        details: list[str] = []

        settings = self._settings
        want_tiflux = bool(parsed.cnpj or parsed.name_term)
        want_vhsys = bool(parsed.os_id) and parsed.quote_id is None

        if want_tiflux:
            if not settings.tiflux_api_token:
                enrichment.tiflux = "skipped"
            else:
                try:
                    client = TifluxClient(settings)
                    if parsed.cnpj:
                        raw = await client.find_matches_by_cnpj(parsed.cnpj, limit=10)
                    else:
                        assert parsed.name_term is not None
                        raw = await client.find_by_name(parsed.name_term, limit=10)
                    for row in raw:
                        raw_id = row.get("id")
                        try:
                            extra.tiflux_ids.add(int(raw_id))
                        except (TypeError, ValueError):
                            pass
                        cnpj_digits = normalize_cnpj(str(row.get("social_revenue") or ""))
                        if len(cnpj_digits) == 14:
                            extra.cnpjs.add(cnpj_digits)
                    enrichment.tiflux = "ok"
                except TifluxApiError as exc:
                    enrichment.tiflux = "error"
                    details.append(f"tiflux: {exc}")
                except Exception as exc:  # noqa: BLE001 — degradação
                    enrichment.tiflux = "error"
                    details.append(f"tiflux: {exc}")
        else:
            enrichment.tiflux = "skipped"

        if want_vhsys:
            if not settings.vhsys_access_token or not settings.vhsys_secret_access_token:
                enrichment.vhsys = "skipped"
            else:
                try:
                    vhsys = VhsysClient(settings)
                    orders = await vhsys.list_service_orders(
                        {"limit": 20, "id_pedido": parsed.os_id}
                    )
                    for order in orders:
                        oid = order.get("id_pedido") or order.get("id") or order.get("numero")
                        if oid is not None:
                            extra.vhsys_os_ids.add(str(oid))
                        cnpj_digits = normalize_cnpj(
                            str(order.get("cnpj") or order.get("cliente_cnpj") or "")
                        )
                        if len(cnpj_digits) == 14:
                            extra.cnpjs.add(cnpj_digits)
                    enrichment.vhsys = "ok"
                except VhsysApiError as exc:
                    enrichment.vhsys = "error"
                    details.append(f"vhsys: {exc}")
                except Exception as exc:  # noqa: BLE001
                    enrichment.vhsys = "error"
                    details.append(f"vhsys: {exc}")
        else:
            enrichment.vhsys = "skipped"

        if details:
            enrichment.detail = "; ".join(details)[:500]
        return extra, enrichment

    async def search(
        self,
        q: str,
        *,
        include_quotes: bool,
        include_billing: bool,
        limit: int = 50,
        enrich: bool = True,
    ) -> DocumentsSearchResponse:
        parsed = parse_documents_query(q)
        if not parsed.raw:
            return DocumentsSearchResponse(query="")

        enrichment = DocumentsEnrichment()
        extra = _ExtraKeys()
        if enrich and (include_quotes or include_billing):
            extra, enrichment = await self.enrich_keys(parsed)

        quotes, pdfs, billing = self.search_local(
            parsed,
            include_quotes=include_quotes,
            include_billing=include_billing,
            limit=limit,
            extra=extra,
        )
        return DocumentsSearchResponse(
            query=parsed.raw,
            quotes=quotes if include_quotes else [],
            pdfs=pdfs if include_quotes else [],
            billing_runs=billing if include_billing else [],
            enrichment=enrichment,
        )
