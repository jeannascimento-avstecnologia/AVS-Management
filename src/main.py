from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.auth.deps import require_user
from src.auth.m365 import build_auth_router
from src.config import get_settings
from src.debug_log import dbg
from src.integrations.tiflux_client import TifluxApiError
from src.orchestrator import (
    OrchestratorError,
    execute_inactivate,
    fetch_consult_detail,
    integrate_company,
    preview_cnpj,
    preview_consult_client,
    preview_inactivate_client,
    scan_dormant_clients,
)

load_dotenv()

settings = get_settings()

app = FastAPI(
    title="AVS Management",
    version="1.4.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

app.include_router(build_auth_router())


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


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _spa_index() -> FileResponse | HTMLResponse:
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    from src.ui import INDEX_HTML

    return HTMLResponse(INDEX_HTML)


@app.get("/", response_class=HTMLResponse, response_model=None)
async def index():
    return _spa_index()


@app.post("/preview")
async def preview(
    request: Request,
    cnpj: str = Form(default=""),
    _user: dict = Depends(require_user),
):
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
        result = await preview_cnpj(raw, get_settings())
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


@app.post("/integrar")
async def integrar(request: Request, _user: dict = Depends(require_user)):
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
            settings=get_settings(),
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


async def _inativar_preview_handler(request: Request):
    raw = ""
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw = str(body.get("query", "")).strip()
    else:
        form = await request.form()
        raw = str(form.get("query", "")).strip()

    if not raw:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Informe CNPJ ou nome para buscar."},
        )

    try:
        result = await preview_inactivate_client(raw, get_settings())
        return JSONResponse(content=result.to_dict())
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc), "query": raw},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "query": raw},
        )


@app.post("/inativar/preview")
async def inativar_preview(request: Request, _user: dict = Depends(require_user)):
    return await _inativar_preview_handler(request)


@app.post("/excluir/preview")
async def excluir_preview(request: Request, _user: dict = Depends(require_user)):
    return await _inativar_preview_handler(request)


async def _inativar_execute_handler(request: Request):
    if "application/json" not in request.headers.get("content-type", ""):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Use JSON no corpo da requisição."},
        )

    body = await request.json()
    raw_query = str(body.get("query", "")).strip()
    tiflux_id = _optional_int(body.get("tiflux_client_id"))

    if not raw_query:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Campo query é obrigatório."},
        )

    try:
        result = await execute_inactivate(raw_query, get_settings(), tiflux_client_id=tiflux_id)
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )

    payload = result.to_dict()
    status = 200 if result.success else 502
    return JSONResponse(status_code=status, content=payload)


@app.post("/inativar")
async def inativar_cliente(request: Request, _user: dict = Depends(require_user)):
    return await _inativar_execute_handler(request)


@app.post("/excluir")
async def excluir_cliente(request: Request, _user: dict = Depends(require_user)):
    return await _inativar_execute_handler(request)


@app.post("/consulta/preview")
async def consulta_preview(request: Request, _user: dict = Depends(require_user)):
    raw = ""
    if "application/json" in request.headers.get("content-type", ""):
        body = await request.json()
        raw = str(body.get("query", "")).strip()
    else:
        form = await request.form()
        raw = str(form.get("query", "")).strip()

    if not raw:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Informe CNPJ ou nome para buscar."},
        )

    try:
        result = await preview_consult_client(raw, get_settings())
        return JSONResponse(content=result.to_dict())
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc), "query": raw},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc), "query": raw},
        )


@app.post("/consulta/detalhe")
async def consulta_detalhe(request: Request, _user: dict = Depends(require_user)):
    if "application/json" not in request.headers.get("content-type", ""):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Use JSON no corpo da requisição."},
        )

    body = await request.json()
    raw_query = str(body.get("query", "")).strip()
    tiflux_id = _optional_int(body.get("tiflux_client_id"))
    vhsys_id = _optional_int(body.get("vhsys_client_id"))

    if not raw_query:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Campo query é obrigatório."},
        )

    try:
        result = await fetch_consult_detail(
            raw_query,
            get_settings(),
            tiflux_client_id=tiflux_id,
            vhsys_client_id=vhsys_id,
        )
    except OrchestratorError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )

    payload = result.to_dict()
    status = 200 if result.success else 502
    return JSONResponse(status_code=status, content=payload)


@app.get("/relatorio/empresas-inativas")
async def relatorio_empresas_inativas(
    months: int = 24,
    limit: int = 100,
    _user: dict = Depends(require_user),
):
    import json
    import time

    _dbg_started = time.time()
    # #region agent log
    try:
        with open("debug-d84fb3.log", "a", encoding="utf-8") as _f:
            _f.write(json.dumps({"sessionId": "d84fb3", "location": "main.py:relatorio:start", "message": "dormant scan start", "data": {"months": months, "limit": limit}, "timestamp": int(time.time() * 1000), "hypothesisId": "B"}) + "\n")
    except OSError:
        pass
    # #endregion
    try:
        result = await scan_dormant_clients(get_settings(), months=months, limit=limit)
        payload = result.to_dict()
        # #region agent log
        try:
            with open("debug-d84fb3.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"sessionId": "d84fb3", "location": "main.py:relatorio:ok", "message": "dormant scan ok", "data": {"elapsedMs": int((time.time() - _dbg_started) * 1000), "total": payload.get("total"), "scanned": payload.get("scanned"), "truncated": payload.get("truncated")}, "timestamp": int(time.time() * 1000), "hypothesisId": "C"}) + "\n")
        except OSError:
            pass
        # #endregion
        return JSONResponse(content=payload)
    except OrchestratorError as exc:
        # #region agent log
        try:
            with open("debug-d84fb3.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"sessionId": "d84fb3", "location": "main.py:relatorio:orch_err", "message": "dormant orchestrator error", "data": {"elapsedMs": int((time.time() - _dbg_started) * 1000), "error": str(exc), "status": exc.status_code}, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}) + "\n")
        except OSError:
            pass
        # #endregion
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc)},
        )
    except TifluxApiError as exc:
        # #region agent log
        try:
            with open("debug-d84fb3.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"sessionId": "d84fb3", "location": "main.py:relatorio:tiflux_err", "message": "dormant tiflux error", "data": {"elapsedMs": int((time.time() - _dbg_started) * 1000), "error": str(exc), "status": exc.status_code}, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}) + "\n")
        except OSError:
            pass
        # #endregion
        return JSONResponse(
            status_code=exc.status_code or 502,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        # #region agent log
        try:
            with open("debug-d84fb3.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"sessionId": "d84fb3", "location": "main.py:relatorio:exc", "message": "dormant unhandled error", "data": {"elapsedMs": int((time.time() - _dbg_started) * 1000), "error": str(exc), "type": type(exc).__name__}, "timestamp": int(time.time() * 1000), "hypothesisId": "A"}) + "\n")
        except OSError:
            pass
        # #endregion
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(exc)},
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "AVS Management", "version": "1.4.0"}


@app.get("/{full_path:path}", response_class=HTMLResponse, response_model=None)
async def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "auth/", "static/", "assets/")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return _spa_index()
