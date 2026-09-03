from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.auth.models import AuthDatabase
from src.auth.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_APROVAR_ORCAMENTO,
    PERMISSION_ORCAMENTOS,
    empty_permissions,
)
from src.config import clear_settings_cache
from src.hub.store import reset_hub_db_cache
from tests.auth_helpers import create_test_user, login_and_csrf

CNPJ = "11222333000181"

QUOTE_PAYLOAD = {
    "cnpj": CNPJ,
    "client_name": "AVS Teste LTDA",
    "billed_by_type": "distribuidor",
    "billed_by_name": "Parceiro X",
    "implant_payment_plan": "3x_sem_juros",
    "items": [
        {
            "section": "implantacao",
            "name": "Setup inicial",
            "qty": 1,
            "unit_value": 1500.0,
            "sort_order": 0,
        },
        {
            "section": "mensalidade",
            "name": "Plano mensal",
            "qty": 1,
            "unit_value": 299.9,
            "sort_order": 0,
        },
    ],
}


@pytest.fixture()
def quotes_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    hub_path = tmp_path / "hub.db"
    pdf_dir = tmp_path / "hub_pdfs"
    monkeypatch.setenv("HUB_DB_PATH", str(hub_path))
    monkeypatch.setenv("HUB_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("HUB_DRY_RUN", "true")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    clear_settings_cache()
    reset_hub_db_cache()
    yield hub_path
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def quotes_client(quotes_env: Path):
    from src.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture()
def quotes_auth_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
    clear_settings_cache()
    reset_hub_db_cache()
    from src.auth.store import reset_auth_db_cache

    reset_auth_db_cache()
    yield {"auth": auth_path, "hub": hub_path, "pdf": pdf_dir}
    reset_auth_db_cache()
    reset_hub_db_cache()
    clear_settings_cache()


@pytest.fixture()
def quotes_auth_client(quotes_auth_env: dict[str, Path]):
    from src.main import app

    with TestClient(app) as client:
        yield client


def test_create_list_get_update_with_items(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] > 0
    assert body["status"] == "draft"
    assert body["cnpj"] == CNPJ
    assert len(body["items"]) == 2
    assert body["items"][0]["total_value"] == 1500.0
    assert body["items"][1]["total_value"] == 299.9
    quote_id = body["id"]

    listed = quotes_client.get("/orcamentos")
    assert listed.status_code == 200
    quotes = listed.json()["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["id"] == quote_id
    assert len(quotes[0]["items"]) == 2

    got = quotes_client.get(f"/orcamentos/{quote_id}")
    assert got.status_code == 200
    assert got.json()["client_name"] == "AVS Teste LTDA"

    updated = quotes_client.put(
        f"/orcamentos/{quote_id}",
        json={
            "client_name": "AVS Atualizado",
            "notes": "Forma de Pagamento: Boleto mensal",
            "items": [
                {
                    "section": "mensalidade",
                    "name": "Plano plus",
                    "qty": 2,
                    "unit_value": 100.0,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    ubody = updated.json()
    assert ubody["client_name"] == "AVS Atualizado"
    assert ubody["notes"] == "Forma de Pagamento: Boleto mensal"
    assert len(ubody["items"]) == 1
    assert ubody["items"][0]["name"] == "Plano plus"
    assert ubody["items"][0]["total_value"] == 200.0


def test_list_filter_by_lead_excludes_approved(quotes_client: TestClient) -> None:
    hot = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "lead_temperature": "quente", "client_name": "Hot"},
    )
    assert hot.status_code == 201, hot.text
    hot_id = hot.json()["id"]

    warm = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "lead_temperature": "morno", "client_name": "Warm"},
    )
    assert warm.status_code == 201, warm.text

    approved = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "lead_temperature": "quente", "client_name": "Approved"},
    )
    assert approved.status_code == 201, approved.text
    approved_id = approved.json()["id"]
    assert quotes_client.post(f"/orcamentos/{approved_id}/approve").status_code == 200

    filtered = quotes_client.get("/orcamentos", params={"lead_temperature": "quente"})
    assert filtered.status_code == 200
    ids = {q["id"] for q in filtered.json()["quotes"]}
    assert ids == {hot_id}

    bad = quotes_client.get("/orcamentos", params={"lead_temperature": "gelado"})
    assert bad.status_code == 422

    bad_status = quotes_client.get("/orcamentos", params={"status": "invalid_status"})
    assert bad_status.status_code == 422


def test_list_search_filters_and_title(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={**QUOTE_PAYLOAD, "client_name": "Cliente Filtro SA", "title": "Proposta Alpha"},
    )
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    assert created.json()["title"] == "Proposta Alpha"

    by_client = quotes_client.get("/orcamentos", params={"client": "Filtro"})
    assert by_client.status_code == 200
    assert {q["id"] for q in by_client.json()["quotes"]} == {qid}

    by_number = quotes_client.get("/orcamentos", params={"number": f"M{qid}"})
    assert by_number.status_code == 200
    assert {q["id"] for q in by_number.json()["quotes"]} == {qid}

    by_q_title = quotes_client.get("/orcamentos", params={"q": "Alpha"})
    assert {q["id"] for q in by_q_title.json()["quotes"]} == {qid}

    by_q_value = quotes_client.get("/orcamentos", params={"q": "1.500,00"})
    assert {q["id"] for q in by_q_value.json()["quotes"]} == {qid}

    miss = quotes_client.get("/orcamentos", params={"q": "zzzz-inexistente"})
    assert miss.json()["quotes"] == []

    patched = quotes_client.put(f"/orcamentos/{qid}", json={"title": "Nome interno"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Nome interno"


def test_list_templates_empty(quotes_client: TestClient) -> None:
    res = quotes_client.get("/orcamentos/templates")
    assert res.status_code == 200
    assert res.json() == {"templates": []}


def test_list_templates_seeded(quotes_env: Path, quotes_client: TestClient) -> None:
    from src.hub.store import get_hub_db

    db = get_hub_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO quote_templates (key, name, section, lines_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "implant_basic",
                "Implantação básica",
                "implantacao",
                '[{"name": "Setup", "qty": 1, "unit_value": 1000, "sort_order": 0}]',
                "2026-07-20T00:00:00+00:00",
            ),
        )
    res = quotes_client.get("/orcamentos/templates")
    assert res.status_code == 200
    templates = res.json()["templates"]
    assert len(templates) == 1
    assert templates[0]["key"] == "implant_basic"
    assert templates[0]["lines"][0]["name"] == "Setup"


def test_create_update_delete_template(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos/templates",
        json={
            "name": "Pacote implantação",
            "section": "implantacao",
            "lines": [
                {"name": "Setup", "qty": 1, "unit_value": 1500, "sort_order": 0},
                {"name": "Treinamento", "qty": 2, "unit_value": 400, "sort_order": 1},
            ],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["key"].startswith("implantacao_pacote_")
    assert body["section"] == "implantacao"
    assert len(body["lines"]) == 2
    template_id = body["id"]

    listed = quotes_client.get("/orcamentos/templates")
    assert listed.status_code == 200
    assert any(t["id"] == template_id for t in listed.json()["templates"])

    updated = quotes_client.put(
        f"/orcamentos/templates/{template_id}",
        json={
            "name": "Pacote implantação v2",
            "section": "mensalidade",
            "lines": [{"name": "Mensalidade base", "qty": 1, "unit_value": 299.9, "sort_order": 0}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Pacote implantação v2"
    assert updated.json()["section"] == "mensalidade"
    assert updated.json()["lines"][0]["name"] == "Mensalidade base"

    conflict = quotes_client.post(
        "/orcamentos/templates",
        json={
            "key": body["key"],
            "name": "Duplicado",
            "section": "implantacao",
            "lines": [{"name": "X", "qty": 1, "unit_value": 1, "sort_order": 0}],
        },
    )
    assert conflict.status_code == 409

    deleted = quotes_client.delete(f"/orcamentos/templates/{template_id}")
    assert deleted.status_code == 204
    assert quotes_client.get("/orcamentos/templates").json()["templates"] == []
    assert quotes_client.delete(f"/orcamentos/templates/{template_id}").status_code == 404


def test_create_template_validation(quotes_client: TestClient) -> None:
    empty_lines = quotes_client.post(
        "/orcamentos/templates",
        json={"name": "Vazio", "section": "implantacao", "lines": []},
    )
    assert empty_lines.status_code == 422

    bad_key = quotes_client.post(
        "/orcamentos/templates",
        json={
            "key": "Bad Key!",
            "name": "Inválido",
            "section": "implantacao",
            "lines": [{"name": "X", "qty": 1, "unit_value": 1, "sort_order": 0}],
        },
    )
    assert bad_key.status_code == 422


def test_list_module_templates_empty(quotes_client: TestClient) -> None:
    res = quotes_client.get("/orcamentos/module-templates")
    assert res.status_code == 200
    assert res.json() == {"templates": []}


def test_create_update_delete_module_template(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos/module-templates",
        json={
            "name": "Licenças",
            "title": "Licenças de software",
            "show_labor": False,
            "lines": [
                {"name": "Licença A", "qty": 2, "unit_value": 100.0, "sort_order": 0},
                {"name": "Licença B", "qty": 1, "unit_value": 250.0, "sort_order": 1},
            ],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Licenças"
    assert body["title"] == "Licenças de software"
    assert body["show_labor"] is False
    assert body["notes"] is None
    assert body["billed_by_name"] is None
    assert body["key"].startswith("mod_licen")
    assert len(body["lines"]) == 2
    template_id = body["id"]

    listed = quotes_client.get("/orcamentos/module-templates")
    assert listed.status_code == 200
    assert any(t["id"] == template_id for t in listed.json()["templates"])

    updated = quotes_client.patch(
        f"/orcamentos/module-templates/{template_id}",
        json={
            "name": "Licenças v2",
            "title": "Licenças AVS",
            "show_labor": True,
            "notes": "Renovação anual",
            "billed_by_name": "Parceiro VHSYS",
            "lines": [{"name": "Licença X", "qty": 1, "unit_value": 99.0, "sort_order": 0}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Licenças v2"
    assert updated.json()["title"] == "Licenças AVS"
    assert updated.json()["show_labor"] is True
    assert updated.json()["notes"] == "Renovação anual"
    assert updated.json()["billed_by_name"] == "Parceiro VHSYS"
    assert updated.json()["lines"][0]["name"] == "Licença X"

    conflict = quotes_client.post(
        "/orcamentos/module-templates",
        json={
            "key": body["key"],
            "name": "Duplicado",
            "title": "Dup",
            "lines": [],
        },
    )
    assert conflict.status_code == 409

    deleted = quotes_client.delete(f"/orcamentos/module-templates/{template_id}")
    assert deleted.status_code == 204
    assert quotes_client.get("/orcamentos/module-templates").json()["templates"] == []
    assert (
        quotes_client.delete(f"/orcamentos/module-templates/{template_id}").status_code
        == 404
    )


def test_import_module_template_persists_on_quote(quotes_client: TestClient) -> None:
    """Simula wizard: modelo → quote com módulo custom_<uuid> + linhas."""
    tpl = quotes_client.post(
        "/orcamentos/module-templates",
        json={
            "name": "Licenças",
            "title": "Licenças",
            "lines": [
                {"name": "Office", "qty": 5, "unit_value": 40.0, "sort_order": 0},
                {"name": "Antivirus", "qty": 5, "unit_value": 15.0, "sort_order": 1},
            ],
        },
    )
    assert tpl.status_code == 201
    lines = tpl.json()["lines"]
    module_id = "custom_aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    created = quotes_client.post(
        "/orcamentos",
        json={
            **QUOTE_PAYLOAD,
            "modules": [
                {
                    "id": "implantacao",
                    "title": "Implantação",
                    "legacy_kind": "implantacao",
                    "show_labor": False,
                    "sort_order": 0,
                },
                {
                    "id": "mensalidade",
                    "title": "Mensalidade",
                    "legacy_kind": "mensalidade",
                    "show_labor": True,
                    "sort_order": 1,
                },
                {
                    "id": module_id,
                    "title": "Licenças",
                    "legacy_kind": None,
                    "show_labor": False,
                    "sort_order": 2,
                },
            ],
            "items": [
                *QUOTE_PAYLOAD["items"],
                {
                    "section": module_id,
                    "name": lines[0]["name"],
                    "qty": lines[0]["qty"],
                    "unit_value": lines[0]["unit_value"],
                    "sort_order": 0,
                    "template_key": tpl.json()["key"],
                },
                {
                    "section": module_id,
                    "name": lines[1]["name"],
                    "qty": lines[1]["qty"],
                    "unit_value": lines[1]["unit_value"],
                    "sort_order": 1,
                    "template_key": tpl.json()["key"],
                },
            ],
        },
    )
    assert created.status_code == 201
    quote_id = created.json()["id"]

    loaded = quotes_client.get(f"/orcamentos/{quote_id}")
    assert loaded.status_code == 200
    data = loaded.json()
    mod_ids = [m["id"] for m in data["modules"]]
    assert module_id in mod_ids
    custom = next(m for m in data["modules"] if m["id"] == module_id)
    assert custom["title"] == "Licenças"
    custom_items = [i for i in data["items"] if i["section"] == module_id]
    assert len(custom_items) == 2
    assert {i["name"] for i in custom_items} == {"Office", "Antivirus"}


def test_module_template_title_roundtrip_independent_of_name(
    quotes_client: TestClient,
) -> None:
    """name = rótulo catálogo; title = default ao importar — devem persistir separados."""
    created = quotes_client.post(
        "/orcamentos/module-templates",
        json={
            "name": "Catálogo Licenças",
            "title": "Licenças",
            "show_labor": False,
            "lines": [{"name": "Office", "qty": 1, "unit_value": 10.0, "sort_order": 0}],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Catálogo Licenças"
    assert body["title"] == "Licenças"

    listed = quotes_client.get("/orcamentos/module-templates")
    assert listed.status_code == 200
    match = next(t for t in listed.json()["templates"] if t["id"] == body["id"])
    assert match["name"] == "Catálogo Licenças"
    assert match["title"] == "Licenças"

    # Save-as rápido (um campo): name == title
    quick = quotes_client.post(
        "/orcamentos/module-templates",
        json={"name": "Licenças", "title": "Licenças", "lines": []},
    )
    assert quick.status_code == 201
    assert quick.json()["name"] == quick.json()["title"] == "Licenças"


def test_module_template_allows_empty_lines(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos/module-templates",
        json={"name": "Bloco vazio", "title": "Extras", "lines": []},
    )
    assert created.status_code == 201
    assert created.json()["lines"] == []


def test_module_template_notes_and_billed_by_roundtrip(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos/module-templates",
        json={
            "name": "Backup",
            "title": "Backup",
            "notes": "Cobrar por seat",
            "billed_by_name": "Fornecedor M365",
            "billed_by_cnpj": "08354533000183",
            "lines": [{"name": "Licença", "qty": 1, "unit_value": 26.4, "sort_order": 0}],
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["notes"] == "Cobrar por seat"
    assert body["billed_by_name"] == "Fornecedor M365"
    assert body["billed_by_cnpj"] == "08354533000183"

    cleared = quotes_client.patch(
        f"/orcamentos/module-templates/{body['id']}",
        json={"notes": "", "billed_by_name": "", "billed_by_cnpj": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None
    assert cleared.json()["billed_by_name"] is None
    assert cleared.json()["billed_by_cnpj"] is None


def test_approve_status_transition(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    approved = quotes_client.post(f"/orcamentos/{quote_id}/approve")
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["approved_at"] is not None


def test_orcamentos_requires_permission(quotes_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "limited@avs.com.br",
        "Limitado",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_ORCAMENTOS] = False
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(quotes_auth_client, "limited@avs.com.br", password)
    blocked = quotes_auth_client.get("/orcamentos", headers=headers)
    assert blocked.status_code == 403

    blocked_post = quotes_auth_client.post(
        "/orcamentos",
        json=QUOTE_PAYLOAD,
        headers=headers,
    )
    assert blocked_post.status_code == 403


def test_orcamentos_allowed_with_permission(quotes_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "user@avs.com.br",
        "Usuário",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_ORCAMENTOS] = True
    perms[PERMISSION_APROVAR_ORCAMENTO] = True
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(quotes_auth_client, "user@avs.com.br", password)
    created = quotes_auth_client.post("/orcamentos", json=QUOTE_PAYLOAD, headers=headers)
    assert created.status_code == 201, created.text
    listed = quotes_auth_client.get("/orcamentos", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["quotes"]) == 1


def test_approve_requires_aprovar_permission(quotes_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "user@avs.com.br",
        "Usuário",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_ORCAMENTOS] = True
    # sem PERMISSION_APROVAR_ORCAMENTO
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(quotes_auth_client, "user@avs.com.br", password)
    created = quotes_auth_client.post("/orcamentos", json=QUOTE_PAYLOAD, headers=headers)
    quote_id = created.json()["id"]
    blocked = quotes_auth_client.post(
        f"/orcamentos/{quote_id}/approve",
        headers=headers,
    )
    assert blocked.status_code == 403
    assert set(ALL_PERMISSIONS)  # catalog sanity


def test_pdf_generate_and_download(quotes_client: TestClient, quotes_env: Path) -> None:
    from src.config import get_settings

    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]

    gen = quotes_client.post(f"/orcamentos/{quote_id}/pdf")
    assert gen.status_code == 200, gen.text
    assert gen.headers["content-type"].startswith("application/pdf")
    assert gen.content[:4] == b"%PDF"
    # Sem X-Pdf-Path (evita vazar filename em header); path só no body da quote.
    assert "x-pdf-path" not in {k.lower() for k in gen.headers.keys()}

    got = quotes_client.get(f"/orcamentos/{quote_id}")
    pdf_name = got.json()["pdf_path"]
    assert pdf_name
    assert pdf_name.endswith(".pdf")
    assert "/" not in pdf_name and "\\" not in pdf_name

    pdf_root = Path(get_settings().hub_pdf_dir)
    assert (pdf_root / pdf_name).is_file()

    download = quotes_client.get(f"/orcamentos/{quote_id}/pdf")
    assert download.status_code == 200
    assert download.content[:4] == b"%PDF"


def test_pdf_layout_title_and_no_implant_labor(quotes_client: TestClient, tmp_path: Path) -> None:
    """PDF: Orçamento : M{id}, assinaturas; implant labor ignorada no cálculo/render."""
    from src.quotes.pdf import quote_display_id, render_quote_pdf
    from src.quotes.pdf_parties import QuotePdfClient, QuotePdfIssuer
    from src.quotes.schemas import QuoteItemRead, QuoteModule, QuoteRead

    quote = QuoteRead(
        id=2353,
        cnpj=CNPJ,
        client_name="Cliente PDF",
        tiflux_client_id=None,
        vhsys_client_id=None,
        status="draft",
        lead_temperature=None,
        billed_by_type=None,
        billed_by_name=None,
        implant_payment_plan="a_vista",
        implant_discount_pct=None,
        implant_discount_value=None,
        implant_labor_hours=10.0,
        implant_labor_hourly_rate=100.0,
        monthly_payment_plan=None,
        monthly_discount_pct=None,
        monthly_discount_value=None,
        monthly_labor_hours=2.0,
        monthly_labor_hourly_rate=50.0,
        client_email=None,
        extra_recipients=[],
        notes=None,
        tiflux_ticket_number=None,
        vhsys_os_id=None,
        pdf_path=None,
        created_by=None,
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
                sort_order=0,
            ),
            QuoteModule(
                id="mensalidade",
                title="Mensalidade",
                legacy_kind="mensalidade",
                show_labor=True,
                labor_hours=2.0,
                labor_hourly_rate=50.0,
                sort_order=1,
            ),
        ],
        items=[
            QuoteItemRead(
                id=1,
                quote_id=2353,
                section="implantacao",
                name="Setup",
                qty=1,
                unit_value=1000.0,
                total_value=1000.0,
                sort_order=0,
            ),
            QuoteItemRead(
                id=2,
                quote_id=2353,
                section="mensalidade",
                name="Plano",
                qty=1,
                unit_value=200.0,
                total_value=200.0,
                sort_order=0,
            ),
        ],
    )
    assert quote_display_id(quote.id) == "M2353"
    dest = tmp_path / "quote.pdf"
    render_quote_pdf(
        quote,
        dest,
        issuer=QuotePdfIssuer(
            name="AVS TECNOLOGIA",
            cnpj="08.354.533/0001-83",
            address_line="Rua Teste, 1",
            phone="(19) 3243-9559",
            mobile="(19) 99656-6524",
            email="contato@avstecnologia.com.br",
            site="www.avstecnologia.com.br",
        ),
        client=QuotePdfClient(
            legal_name="Cliente PDF",
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
    raw = dest.read_bytes()
    assert raw[:4] == b"%PDF"
    # fpdf2 comprime streams — extrai texto via zlib
    import re
    import zlib

    texts: list[str] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            dec = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        for lit in re.findall(rb"\((?:\\.|[^\\)])*\)", dec):
            try:
                texts.append(lit[1:-1].decode("latin-1"))
            except UnicodeDecodeError:
                pass
    blob = "\n".join(texts)
    assert "Orcamento : M2353" in blob
    assert "Assinatura do Prestador" in blob
    assert "Assinatura do Sacado" in blob
    assert "IMPLANTACAO" in blob
    assert "MENSALIDADE" in blob
    assert blob.count("Mao de obra") <= 1


def test_create_clears_implant_labor(quotes_client: TestClient) -> None:
    payload = {
        **QUOTE_PAYLOAD,
        "implant_labor_hours": 8,
        "implant_labor_hourly_rate": 120,
        "monthly_labor_hours": 1,
        "monthly_labor_hourly_rate": 90,
    }
    created = quotes_client.post("/orcamentos", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["implant_labor_hours"] is None
    assert body["implant_labor_hourly_rate"] is None
    assert body["monthly_labor_hours"] == 1
    assert body["monthly_labor_hourly_rate"] == 90


def test_pdf_404_quote_missing(quotes_client: TestClient) -> None:
    res = quotes_client.post("/orcamentos/999999/pdf")
    assert res.status_code == 404
    res_get = quotes_client.get("/orcamentos/999999/pdf")
    assert res_get.status_code == 404


def test_pdf_requires_permission(quotes_auth_client: TestClient) -> None:
    from src.config import get_settings

    settings = get_settings()
    db = AuthDatabase(settings.auth_db_path)
    password = "Test1Pass"
    user = create_test_user(
        db,
        "limited@avs.com.br",
        "Limitado",
        password,
        all_permissions=False,
    )
    perms = empty_permissions()
    perms[PERMISSION_ORCAMENTOS] = False
    db.set_permissions(user.id, perms)

    headers = login_and_csrf(quotes_auth_client, "limited@avs.com.br", password)
    blocked = quotes_auth_client.post("/orcamentos/1/pdf", headers=headers)
    assert blocked.status_code == 403
    blocked_get = quotes_auth_client.get("/orcamentos/1/pdf", headers=headers)
    assert blocked_get.status_code == 403


def test_create_starts_with_empty_modules(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos",
        json={"cnpj": CNPJ, "client_name": "Vazio", "items": []},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["modules"] == []
    assert body["items"] == []


def test_module_notes_billed_by_and_recorrente_anual_persist(
    quotes_client: TestClient,
) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    updated = quotes_client.put(
        f"/orcamentos/{quote_id}",
        json={
            **QUOTE_PAYLOAD,
            "modules": [
                {
                    "id": "implantacao",
                    "title": "Implantação",
                    "legacy_kind": "implantacao",
                    "show_labor": False,
                    "payment_plan": "recorrente_anual",
                    "discount_pct": None,
                    "discount_value": None,
                    "labor_hours": None,
                    "labor_hourly_rate": None,
                    "notes": "Boleto anual",
                    "billed_by_name": "Parceiro Bloco",
                    "sort_order": 0,
                },
                {
                    "id": "mensalidade",
                    "title": "Mensalidade",
                    "legacy_kind": "mensalidade",
                    "show_labor": True,
                    "payment_plan": "12x",
                    "discount_pct": None,
                    "discount_value": None,
                    "labor_hours": None,
                    "labor_hourly_rate": None,
                    "notes": None,
                    "billed_by_name": None,
                    "sort_order": 1,
                },
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    implant = next(m for m in updated.json()["modules"] if m["id"] == "implantacao")
    assert implant["payment_plan"] == "recorrente_anual"
    assert implant["notes"] == "Boleto anual"
    assert implant["billed_by_name"] == "Parceiro Bloco"


def test_remove_implantacao_clears_flat_and_allows_custom(
    quotes_client: TestClient,
) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    payload = {
        "modules": [
            {
                "id": "mensalidade",
                "title": "Mensalidade",
                "legacy_kind": "mensalidade",
                "show_labor": True,
                "payment_plan": "3x",
                "discount_pct": None,
                "discount_value": None,
                "labor_hours": None,
                "labor_hourly_rate": None,
                "sort_order": 0,
            },
            {
                "id": "licencas",
                "title": "Licenças",
                "legacy_kind": None,
                "show_labor": False,
                "payment_plan": "a_vista",
                "discount_pct": None,
                "discount_value": None,
                "labor_hours": None,
                "labor_hourly_rate": None,
                "sort_order": 1,
            },
        ],
        "items": [
            {
                "section": "mensalidade",
                "name": "Plano",
                "qty": 1,
                "unit_value": 100,
                "sort_order": 0,
            },
            {
                "section": "licencas",
                "name": "Office 365",
                "qty": 2,
                "unit_value": 50,
                "sort_order": 0,
            },
        ],
    }
    updated = quotes_client.put(f"/orcamentos/{quote_id}", json=payload)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert [m["id"] for m in body["modules"]] == ["mensalidade", "licencas"]
    assert body["implant_payment_plan"] is None
    assert body["implant_discount_pct"] is None
    assert body["implant_discount_value"] is None
    assert body["monthly_payment_plan"] == "3x"

    # Restore implantacao
    restore = {
        "modules": [
            {
                "id": "implantacao",
                "title": "Implantação",
                "legacy_kind": "implantacao",
                "show_labor": False,
                "sort_order": 0,
            },
            {
                "id": "mensalidade",
                "title": "Mensalidade",
                "legacy_kind": "mensalidade",
                "show_labor": True,
                "payment_plan": "3x",
                "sort_order": 1,
            },
            {
                "id": "licencas",
                "title": "Licenças",
                "legacy_kind": None,
                "show_labor": False,
                "sort_order": 2,
            },
        ],
        "items": body["items"],
    }
    restored = quotes_client.put(f"/orcamentos/{quote_id}", json=restore)
    assert restored.status_code == 200, restored.text
    ids = [m["id"] for m in restored.json()["modules"]]
    assert ids == ["implantacao", "mensalidade", "licencas"]


def test_reorder_modules_persists_sort_order(quotes_client: TestClient) -> None:
    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    reordered = quotes_client.put(
        f"/orcamentos/{quote_id}",
        json={
            "modules": [
                {
                    "id": "mensalidade",
                    "title": "Mensalidade",
                    "legacy_kind": "mensalidade",
                    "show_labor": True,
                    "sort_order": 0,
                },
                {
                    "id": "implantacao",
                    "title": "Implantação",
                    "legacy_kind": "implantacao",
                    "show_labor": False,
                    "sort_order": 1,
                },
            ],
            "items": created.json()["items"],
        },
    )
    assert reordered.status_code == 200, reordered.text
    mods = reordered.json()["modules"]
    assert mods[0]["id"] == "mensalidade"
    assert mods[0]["sort_order"] == 0
    assert mods[1]["id"] == "implantacao"
    assert mods[1]["sort_order"] == 1


def test_legacy_quote_without_modules_json_loads_seed(
    quotes_client: TestClient, quotes_env
) -> None:
    import sqlite3

    created = quotes_client.post("/orcamentos", json=QUOTE_PAYLOAD)
    quote_id = created.json()["id"]
    conn = sqlite3.connect(quotes_env)
    conn.execute("UPDATE quotes SET modules_json = NULL WHERE id = ?", (quote_id,))
    conn.commit()
    conn.close()

    got = quotes_client.get(f"/orcamentos/{quote_id}")
    assert got.status_code == 200
    mods = got.json()["modules"]
    assert len(mods) == 2
    assert mods[0]["id"] == "implantacao"
    assert mods[1]["id"] == "mensalidade"


def test_proposal_template_crud_and_apply_payload(quotes_client: TestClient) -> None:
    created = quotes_client.post(
        "/orcamentos/proposal-templates",
        json={
            "name": "Pacote M365",
            "modules": [
                {
                    "id": "custom_pack",
                    "title": "Licenças",
                    "show_labor": False,
                    "simplified": True,
                    "display_name": "Microsoft 365",
                    "billed_by_name": "Parceiro",
                    "billed_by_cnpj": "08354533000183",
                    "sort_order": 0,
                }
            ],
            "items": [
                {
                    "section": "custom_pack",
                    "name": "M365 E3",
                    "qty": 2,
                    "unit_value": 10,
                    "sort_order": 0,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Pacote M365"
    assert body["modules"][0]["simplified"] is True
    assert body["modules"][0]["display_name"] == "Microsoft 365"
    assert body["modules"][0]["billed_by_cnpj"] == "08354533000183"
    tid = body["id"]

    listed = quotes_client.get("/orcamentos/proposal-templates")
    assert listed.status_code == 200
    assert any(t["id"] == tid for t in listed.json()["templates"])

    deleted = quotes_client.delete(f"/orcamentos/proposal-templates/{tid}")
    assert deleted.status_code == 204
    assert quotes_client.get("/orcamentos/proposal-templates").json()["templates"] == []

