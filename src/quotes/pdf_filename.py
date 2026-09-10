from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from src.quotes.schemas import is_template_placeholder_cnpj

_UNSAFE = re.compile(r'[\\/:*?"<>|]+')
_SPACES = re.compile(r"\s+")
_MAX_STEM = 180


@dataclass(frozen=True)
class PdfDownloadName:
    utf8: str
    ascii_fallback: str

    def content_disposition(self) -> str:
        ascii_safe = self.ascii_fallback.replace('"', "")
        return (
            f'attachment; filename="{ascii_safe}"; '
            f"filename*=UTF-8''{quote(self.utf8, safe='')}"
        )


def _clean_segment(value: str | None) -> str:
    if not value:
        return ""
    cleaned = _UNSAFE.sub(" ", value)
    cleaned = _SPACES.sub(" ", cleaned).strip(" .-")
    return cleaned


def quote_pdf_download_name(
    *,
    quote_id: int,
    client_name: str | None,
    title: str | None,
    cnpj: str | None = None,
    version_number: int | None = None,
) -> PdfDownloadName:
    parts = [f"Orçamento M{quote_id}"]
    if not is_template_placeholder_cnpj(cnpj):
        client = _clean_segment(client_name)
        if client:
            parts.append(client)
    ref = _clean_segment(title)
    if ref:
        parts.append(ref)
    if version_number is not None and version_number >= 2:
        parts.append(f"v{version_number}")
    stem = " - ".join(parts)
    if len(stem) > _MAX_STEM:
        stem = stem[:_MAX_STEM].rstrip(" -")
    return PdfDownloadName(utf8=f"{stem}.pdf", ascii_fallback=f"Orcamento-M{quote_id}.pdf")


def quote_pdf_download_name_from_quote(
    quote: Any,
    version_number: int | None = None,
) -> PdfDownloadName:
    vn = (
        version_number
        if version_number is not None
        else getattr(quote, "current_version_number", None)
    )
    return quote_pdf_download_name(
        quote_id=int(quote.id),
        client_name=getattr(quote, "client_name", None),
        title=getattr(quote, "title", None),
        cnpj=getattr(quote, "cnpj", None),
        version_number=vn,
    )
