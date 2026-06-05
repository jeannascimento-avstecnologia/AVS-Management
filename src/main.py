from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import get_settings
from src.debug_log import dbg
from src.orchestrator import OrchestratorError, integrate_company, preview_cnpj
from src.ui import INDEX_HTML

load_dotenv()

app = FastAPI(
    title="Integração CNPJ → TiFlux + VHSYS",
    version="1.1.0",
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML


@app.post("/preview")
async def preview(
    request: Request,
    cnpj: str = Form(default=""),
):
    settings = get_settings()
    raw = cnpj.strip()

    if not raw and "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw = str(body.get("cnpj", "")).strip()

    if not raw:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "CNPJ é obrigatório."},
        )

    try:
        result = await preview_cnpj(raw, settings)
        return JSONResponse(content=result.to_dict())
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc), "cnpj": raw},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "cnpj": raw},
        )


def _parse_id_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


@app.post("/integrar")
async def integrar(request: Request):
    settings = get_settings()
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        body = await request.json()
        company_data = body.get("company") or body
        desk_ids = _parse_id_list(body.get("desk_ids"))
        technical_group_ids = _parse_id_list(body.get("technical_group_ids"))
        override_inactive = bool(body.get("override_inactive_registration"))
        raw_cnpj = str(company_data.get("cnpj_digits") or company_data.get("cnpj") or "")
    else:
        form = await request.form()
        raw_cnpj = str(form.get("cnpj", "")).strip()
        company_data = {
            "cnpj_digits": raw_cnpj,
            "trade_name": form.get("trade_name"),
            "legal_name": form.get("legal_name"),
            "phone": form.get("phone"),
            "email": form.get("email"),
            "status_active": form.get("status_active") in ("true", "on", "1"),
            "registration_status": str(form.get("registration_status") or "").strip().upper(),
            "address": {
                "street": form.get("street"),
                "number": form.get("number"),
                "complement": form.get("complement"),
                "district": form.get("district"),
                "city": form.get("city"),
                "state": form.get("state"),
                "zip_code": form.get("zip_code"),
            },
        }
        desk_ids = _parse_id_list(form.getlist("desk_ids"))
        technical_group_ids = _parse_id_list(form.getlist("technical_group_ids"))
        override_inactive = form.get("override_inactive_registration") in ("true", "on", "1")

    if not raw_cnpj and not company_data.get("cnpj_digits"):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "CNPJ é obrigatório."},
        )

    try:
        dbg("H4", "main.py:integrar", "integrate_start", {"desk_count": len(desk_ids)})
        result = await integrate_company(
            company_data,
            desk_ids=desk_ids,
            technical_group_ids=technical_group_ids,
            settings=settings,
            override_inactive_registration=override_inactive,
        )
        dbg("H4", "main.py:integrar", "integrate_done", {"success": result.success})
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        dbg("H1", "main.py:integrar", "uncaught_exception", {"type": type(exc).__name__, "err": str(exc)})
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )

    payload = result.to_dict()
    if result.success:
        status = 200
    elif result.partial:
        status = 207
    else:
        status = 502

    return JSONResponse(status_code=status, content=payload)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

