"""Consulta de documentos — GET /documentos (SPEC_CONSULTA_DOCUMENTOS)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.auth.models import AuthDatabase
from src.auth.permissions import PERMISSION_FATURAR, PERMISSION_ORCAMENTOS, empty_permissions
from src.config import clear_settings_cache
from src.documents.service import parse_documents_query
from src.hub.store import reset_hub_db_cache
from tests.auth_helpers import create_test_user, login_and_csrf

CNPJ = "11222333000181"

QUOTE_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "AVS Documentos LTDA",
    "items": [
        {
            "section": "implantacao",
            "name": "Setup",
            "qty": 1,
            "unit_value": 100.0,
            "sort_order": 0,
        }
    ],
}

RUN_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "AVS Documentos LTDA",
    "competence": "2026-07",
    "has_retencao": False,
    "items": [
        {
            "source": "contract",
            "description": "Mensalidade",
            "amount": 200.0,
            "sort_order": 0,
        }
    ],
}


@pytest.fixture()
def docs_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.setenv("TIFLUX_API_TOKEN", "")
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "")
    clear_settings_cache()
    reset_hub_db_cache()
    yield hub_path
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def docs_client(docs_env: Path):
    from src.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def docs_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auth_path = tmp_path / "auth.db"
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("AUTH_PROVIDER", "local")
    monkeypatch.setenv("AUTH_DB_PATH", str(auth_path))
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("SESSION_SECRET", "pytest-only-session-secret-key-32b!!")
    monkeypatch.setenv("APP_BASE_URL", "http://testserver")
    monkeypatch.setenv(
        "ALLOWED_USER_EMAILS",
        "user@avs.com.br,limited@avs.com.br,admin@avs.com.br",
    )
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("TIFLUX_API_TOKEN", "")
    monkeypatch.setenv("VHSYS_ACCESS_TOKEN", "")
    monkeypatch.setenv("VHSYS_SECRET_ACCESS_TOKEN", "")
    clear_settings_cache()
    reset_hub_db_cache()
    from src.auth.store import reset_auth_db_cache

    reset_auth_db_cache()
    yield {"auth": auth_path, "hub": hub_path}
    reset_auth_db_cache()
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def docs_auth_client(docs_auth_env: dict[str, Path]):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_parse_m_id_and_cnpj() -> None:
    m = parse_documents_query("M42")
    assert m.quote_id == 42
    assert m.cnpj is None

    c = parse_documents_query("11.222.333/0001-81")
    assert c.cnpj == CNPJ

    os_q = parse_documents_query("OS 987")
    assert os_q.os_id == "987"

    name = parse_documents_query("AVS Documentos")
    assert name.name_term == "AVS Documentos"


def test_search_by_cnpj_name_and_m_id(docs_client: TestClient) -> None:
    created = docs_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]

    run = docs_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    by_cnpj = docs_client.get("/documentos", params={"q": CNPJ})
    assert by_cnpj.status_code == 200, by_cnpj.text
    body = by_cnpj.json()
    assert body["query"] == CNPJ
    assert any(q["id"] == quote_id for q in body["quotes"])
    assert any(r["id"] == run_id for r in body["billing_runs"])
    assert body["enrichment"]["tiflux"] in ("skipped", "ok", "error")

    by_name = docs_client.get("/documentos", params={"q": "Documentos"})
    assert by_name.status_code == 200
    assert any(q["id"] == quote_id for q in by_name.json()["quotes"])

    by_m = docs_client.get("/documentos", params={"q": f"M{quote_id}"})
    assert by_m.status_code == 200
    mbody = by_m.json()
    assert len(mbody["quotes"]) == 1
    assert mbody["quotes"][0]["display_id"] == f"M{quote_id}"
    assert mbody["billing_runs"] == []


def test_search_by_vhsys_os_id(docs_client: TestClient, docs_env: Path) -> None:
    created = docs_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]

    import sqlite3

    with sqlite3.connect(docs_env) as conn:
        conn.execute(
            "UPDATE quotes SET vhsys_os_id = ? WHERE id = ?",
            ("5555", quote_id),
        )
        conn.commit()

    found = docs_client.get("/documentos", params={"q": "OS5555"})
    assert found.status_code == 200
    ids = {q["id"] for q in found.json()["quotes"]}
    assert quote_id in ids


def test_empty_q_returns_422(docs_client: TestClient) -> None:
    resp = docs_client.get("/documentos", params={"q": "  "})
    assert resp.status_code == 422


def test_recent_lists_newest_first(docs_client: TestClient, docs_env: Path) -> None:
    import sqlite3
    import time

    q1 = docs_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    assert q1.status_code == 201, q1.text
    id1 = q1.json()["id"]
    time.sleep(0.02)
    q2 = docs_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "client_name": "AVS Mais Recente"},
    )
    assert q2.status_code == 201, q2.text
    id2 = q2.json()["id"]

    r1 = docs_client.post("/faturamento/runs", json=RUN_PAYLOAD)
    assert r1.status_code == 201, r1.text
    run1 = r1.json()["id"]
    time.sleep(0.02)
    r2 = docs_client.post(
        "/faturamento/runs",
        json={**RUN_PAYLOAD, "competence": "2026-08", "client_name": "Bill Recente"},
    )
    assert r2.status_code == 201, r2.text
    run2 = r2.json()["id"]

    # Força updated_at para garantir ordem determinística
    with sqlite3.connect(docs_env) as conn:
        conn.execute(
            "UPDATE quotes SET updated_at = ? WHERE id = ?",
            ("2026-07-20T10:00:00", id1),
        )
        conn.execute(
            "UPDATE quotes SET updated_at = ? WHERE id = ?",
            ("2026-07-21T12:00:00", id2),
        )
        conn.execute(
            "UPDATE billing_runs SET updated_at = ? WHERE id = ?",
            ("2026-07-20T10:00:00", run1),
        )
        conn.execute(
            "UPDATE billing_runs SET updated_at = ? WHERE id = ?",
            ("2026-07-21T12:00:00", run2),
        )
        conn.commit()

    resp = docs_client.get("/documentos/recent", params={"limit": 50})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == ""
    assert body["enrichment"]["tiflux"] == "skipped"
    quote_ids = [q["id"] for q in body["quotes"]]
    assert quote_ids.index(id2) < quote_ids.index(id1)
    billing_ids = [r["id"] for r in body["billing_runs"]]
    assert billing_ids.index(run2) < billing_ids.index(run1)

    hit = next(q for q in body["quotes"] if q["id"] == id2)
    assert hit["doc_type"] == "orcamento"
    assert hit["created_at"]
    assert hit["value_total"] == 100.0
    assert hit["implant_net"] == 100.0
    assert "monthly_net" in hit

    bill = next(r for r in body["billing_runs"] if r["id"] == run2)
    assert bill["doc_type"] == "faturamento"
    assert bill["created_at"]
    assert bill["net_total"] is not None
    assert "due_date" in bill
    assert "gross_total" in bill


def test_search_returns_detail_fields(docs_client: TestClient, docs_env: Path) -> None:
    import sqlite3

    created = docs_client.post(
        "/orcamentos",
        json={
            **QUOTE_PAYLOAD,
            "items": [
                {
                    "section": "implantacao",
                    "name": "Setup",
                    "qty": 1,
                    "unit_value": 200.0,
                    "sort_order": 0,
                },
                {
                    "section": "mensalidade",
                    "name": "Plano",
                    "qty": 1,
                    "unit_value": 80.0,
                    "sort_order": 0,
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    quote_id = created.json()["id"]

    with sqlite3.connect(docs_env) as conn:
        conn.execute(
            "UPDATE quotes SET lead_temperature = ?, billed_by_type = ?, "
            "billed_by_name = ?, implant_discount_value = ? WHERE id = ?",
            ("quente", "distribuidor", "Parceiro X", 20.0, quote_id),
        )
        conn.execute(
            "UPDATE quotes SET pdf_path = ? WHERE id = ?",
            ("fake-uuid.pdf", quote_id),
        )
        conn.commit()

    run = docs_client.post(
        "/faturamento/runs",
        json={**RUN_PAYLOAD, "due_date": "2026-07-25"},
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    resp = docs_client.get("/documentos", params={"q": CNPJ})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    quote = next(q for q in body["quotes"] if q["id"] == quote_id)
    assert quote["doc_type"] == "orcamento"
    assert quote["lead_temperature"] == "quente"
    assert quote["billed_by_type"] == "distribuidor"
    assert quote["billed_by_name"] == "Parceiro X"
    assert quote["has_pdf"] is True
    assert quote["implant_net"] == 180.0  # 200 - 20
    assert quote["monthly_net"] == 80.0
    assert quote["value_total"] == 260.0
    assert quote["created_at"]

    pdf = next(p for p in body["pdfs"] if p["quote_id"] == quote_id)
    assert pdf["doc_type"] == "pdf"
    assert pdf["value_total"] == 260.0
    assert pdf["status"] == quote["status"]
    assert pdf["has_pdf"] is True

    bill = next(r for r in body["billing_runs"] if r["id"] == run_id)
    assert bill["doc_type"] == "faturamento"
    assert bill["due_date"] == "2026-07-25"
    assert bill["created_at"]


def test_recent_perm_faturar_only(
    docs_auth_client: TestClient, docs_auth_env: dict[str, Path]
) -> None:
    from src.hub.store import get_hub_db
    from src.quotes.schemas import QuoteItemWrite, QuoteWrite
    from src.quotes.service import QuoteService
    from src.billing.schemas import BillingItemWrite, BillingRunWrite
    from src.billing.service import BillingService

    qs = QuoteService(get_hub_db())
    qs.create(
        QuoteWrite(
            cnpj=CNPJ,
            client_name="Hide Recent Quote",
            items=[QuoteItemWrite(section="implantacao", name="X", qty=1, unit_value=10)],
        ),
        created_by=None,
    )
    bs = BillingService(get_hub_db())
    run = bs.create(
        BillingRunWrite(
            cnpj=CNPJ,
            client_name="Show Recent Bill",
            competence="2026-09",
            items=[BillingItemWrite(source="ticket", description="Z", amount=30)],
        ),
        created_by=None,
    )

    db = AuthDatabase(docs_auth_env["auth"])
    password = "TempPass1!"
    user = create_test_user(
        db, "limited@avs.com.br", "Limited", password, all_permissions=False
    )
    perms = empty_permissions()
    perms[PERMISSION_FATURAR] = True
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(docs_auth_client, "limited@avs.com.br", password)
    resp = docs_auth_client.get("/documentos/recent", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quotes"] == []
    assert body["pdfs"] == []
    assert any(r["id"] == run.id for r in body["billing_runs"])


def test_perm_filter_quotes_only(
    docs_auth_client: TestClient, docs_auth_env: dict[str, Path]
) -> None:
    # seed data with full perms via AUTH_ENABLED=false path is harder; create via hub service
    from src.hub.store import get_hub_db
    from src.quotes.schemas import QuoteItemWrite, QuoteWrite
    from src.quotes.service import QuoteService
    from src.billing.schemas import BillingItemWrite, BillingRunWrite
    from src.billing.service import BillingService

    qs = QuoteService(get_hub_db())
    quote = qs.create(
        QuoteWrite(
            cnpj=CNPJ,
            client_name="Perm Quote",
            items=[QuoteItemWrite(section="implantacao", name="X", qty=1, unit_value=10)],
        ),
        created_by=None,
    )
    bs = BillingService(get_hub_db())
    run = bs.create(
        BillingRunWrite(
            cnpj=CNPJ,
            client_name="Perm Bill",
            competence="2026-07",
            items=[BillingItemWrite(source="contract", description="Y", amount=50)],
        ),
        created_by=None,
    )

    db = AuthDatabase(docs_auth_env["auth"])
    password = "TempPass1!"
    user = create_test_user(
        db, "user@avs.com.br", "User", password, all_permissions=False
    )
    perms = empty_permissions()
    perms[PERMISSION_ORCAMENTOS] = True
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(docs_auth_client, "user@avs.com.br", password)
    resp = docs_auth_client.get("/documentos", params={"q": CNPJ}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert any(q["id"] == quote.id for q in body["quotes"])
    assert body["billing_runs"] == []
    assert run.id > 0


def test_perm_faturar_only_hides_quotes(
    docs_auth_client: TestClient, docs_auth_env: dict[str, Path]
) -> None:
    from src.hub.store import get_hub_db
    from src.quotes.schemas import QuoteItemWrite, QuoteWrite
    from src.quotes.service import QuoteService
    from src.billing.schemas import BillingItemWrite, BillingRunWrite
    from src.billing.service import BillingService

    qs = QuoteService(get_hub_db())
    qs.create(
        QuoteWrite(
            cnpj=CNPJ,
            client_name="Hide Quote",
            items=[QuoteItemWrite(section="implantacao", name="X", qty=1, unit_value=10)],
        ),
        created_by=None,
    )
    bs = BillingService(get_hub_db())
    run = bs.create(
        BillingRunWrite(
            cnpj=CNPJ,
            client_name="Show Bill",
            competence="2026-08",
            items=[BillingItemWrite(source="ticket", description="Z", amount=30)],
        ),
        created_by=None,
    )

    db = AuthDatabase(docs_auth_env["auth"])
    password = "TempPass1!"
    user = create_test_user(
        db, "limited@avs.com.br", "Limited", password, all_permissions=False
    )
    perms = empty_permissions()
    perms[PERMISSION_FATURAR] = True
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(docs_auth_client, "limited@avs.com.br", password)
    resp = docs_auth_client.get("/documentos", params={"q": CNPJ}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["quotes"] == []
    assert body["pdfs"] == []
    assert any(r["id"] == run.id for r in body["billing_runs"])


def test_no_hub_perm_forbidden(
    docs_auth_client: TestClient, docs_auth_env: dict[str, Path]
) -> None:
    db = AuthDatabase(docs_auth_env["auth"])
    password = "TempPass1!"
    user = create_test_user(
        db, "admin@avs.com.br", "Admin", password, all_permissions=False
    )
    db.set_permissions(user.id, empty_permissions())
    headers = login_and_csrf(docs_auth_client, "admin@avs.com.br", password)
    resp = docs_auth_client.get("/documentos", params={"q": "AVS"}, headers=headers)
    assert resp.status_code == 403
