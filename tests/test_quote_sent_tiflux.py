"""Aplicação direta do quote.sent no TiFlux."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.config import Settings
from src.integrations.tiflux_client import TifluxApiError
from src.quotes.schemas import QuoteMarkSentBody, QuoteRead
from src.quotes.sent_message import message_text_for
from src.quotes.sent_tiflux import (
    apply_quote_sent_to_tiflux,
    clear_quote_sent_caches,
    find_id_by_name,
    message_to_html,
    simulate_quote_sent_tiflux,
)

DESK = {
    "id": 36089,
    "stages": [
        {"id": 1, "name": "Triagem"},
        {"id": 7, "name": "Orçamento enviado"},
    ],
    "statuses": [{"id": 3, "name": "Aguardando o cliente"}],
}


def _quote(**overrides: object) -> QuoteRead:
    data: dict[str, object] = {
        "id": 1,
        "cnpj": "11222333000181",
        "client_name": "AVS",
        "contact_name": "Ana",
        "tiflux_ticket_number": "55",
        "pdf_path": None,
        "status": "sent",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    data.update(overrides)
    return QuoteRead.model_construct(**data)


def test_find_stage_and_status_by_name() -> None:
    assert find_id_by_name([DESK], ("stages", "stage"), "Orçamento enviado") == 7
    assert find_id_by_name([DESK], ("statuses", "status"), "Aguardando o cliente") == 3
    assert find_id_by_name([DESK], ("stages", "stage"), "Inexistente") is None


def test_answer_html_and_base64_file(tmp_path: Path) -> None:
    clear_quote_sent_caches()
    pdf_name = "12345678-1234-1234-1234-123456789abc.pdf"
    (tmp_path / pdf_name).write_bytes(b"%PDF-1")
    quote = _quote(pdf_path=pdf_name)
    body = QuoteMarkSentBody(free_message="Linha <extra>")
    settings = Settings(
        hub_pdf_dir=str(tmp_path),
        tiflux_quote_sent_responsible_id=9,
        tiflux_desk_comercial_id=36089,
        tiflux_min_request_interval_ms=0,
    )
    seen: dict[str, object] = {}

    class _Fake:
        async def get_ticket_by_number(self, number: str, **_kwargs: object) -> dict:
            return {"id": 15, "ticket_number": number, "desk": DESK}

        async def get_desk(self, _desk_id: int) -> dict:
            raise AssertionError("catálogo já veio no ticket")

        async def find_user_id_by_name(self, _name: str) -> int:
            raise AssertionError("id configurado não busca usuário")

        async def update_ticket(self, ticket_id: int, **kwargs: object) -> dict:
            seen["update"] = (ticket_id, kwargs)
            return {}

        async def create_ticket_answer(self, ticket_number: str, **kwargs: object) -> dict:
            seen["answer"] = (ticket_number, kwargs)
            return {}

    result = asyncio.run(
        apply_quote_sent_to_tiflux(quote, body, settings, client=_Fake())  # type: ignore[arg-type]
    )
    assert result["stage_ok"] is True
    assert result["status_ok"] is True
    assert result["responsible_ok"] is True
    assert result["attachment_ok"] is True
    _number, answer_kwargs = seen["answer"]
    assert isinstance(answer_kwargs, dict)
    html = str(answer_kwargs["answer"])
    assert html == message_to_html(message_text_for(quote, body))
    assert "Linha &lt;extra&gt;" in html
    assert "<br>" in html
    files = answer_kwargs["files_base64"]
    assert isinstance(files, list)
    assert files[0]["filename"] == pdf_name
    assert files[0]["base64"]


def test_partial_failure_keeps_answer(tmp_path: Path) -> None:
    clear_quote_sent_caches()
    quote = _quote()
    settings = Settings(
        hub_pdf_dir=str(tmp_path),
        tiflux_quote_sent_responsible_id=0,
        tiflux_desk_comercial_id=36089,
        tiflux_min_request_interval_ms=0,
    )

    class _Fake:
        async def get_ticket_by_number(self, number: str, **_kwargs: object) -> dict:
            return {"id": 15, "ticket_number": number, "desk_id": 36089}

        async def get_desk(self, _desk_id: int) -> dict:
            return DESK

        async def find_user_id_by_name(self, name: str) -> None:
            assert name == "André"
            return None

        async def update_ticket(self, _ticket_id: int, **_kwargs: object) -> dict:
            raise TifluxApiError("Erro ao atualizar chamado: 500.", 500)

        async def create_ticket_answer(self, _ticket_number: str, **kwargs: object) -> dict:
            assert kwargs["files_base64"] is None
            return {}

    result = asyncio.run(
        apply_quote_sent_to_tiflux(
            quote,
            QuoteMarkSentBody(),
            settings,
            client=_Fake(),  # type: ignore[arg-type]
        )
    )
    assert result["dry_run"] is False
    assert result["stage_ok"] is False
    assert result["status_ok"] is False
    assert result["responsible_ok"] is False
    assert result["answer_ok"] is True
    assert result["attachment_ok"] is False
    assert result["followers_ok"] is True
    joined = " ".join(result["errors"])
    assert "atualizar" in joined
    assert "André" in joined
    assert "PDF" in joined


def test_dry_run_does_not_need_client() -> None:
    quote = _quote(tiflux_ticket_number=None)
    result = simulate_quote_sent_tiflux(quote, QuoteMarkSentBody(), Settings())
    assert result["dry_run"] is True
    assert result["stage_ok"] is False
    assert any("não vinculado" in item for item in result["errors"])
