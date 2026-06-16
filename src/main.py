from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.auth.deps import require_user
from src.auth.local import RememberMeMiddleware
from src.auth.router import build_auth_router
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
from src.stats import compute_stats

load_dotenv()

settings = get_settings()

app = FastAPI(
    title="AVS Management",
    version="1.4.0",
)

app.add_middleware(RememberMeMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.app_base_url.startswith("https://"),
    max_age=settings.session_idle_hours * 3600,
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
        raw_targets = body.get("targets")
        targets = [str(t) for t in raw_targets] if isinstance(raw_targets, list) else None
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
            targets=targets,
        )
        dbg("H4", "main.py:integrar", "integrate_done", {"success": result.success, "all_duplicates": result.all_duplicates})
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
    if result.all_duplicates:
        payload["error"] = "Cliente já cadastrado nos sistemas selecionados."
        status = 409
    elif result.success:
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


def _dormant_error_response(exc: Exception) -> tuple[int, dict[str, Any]]:
    if isinstance(exc, OrchestratorError):
        return exc.status_code, {"success": False, "error": str(exc)}
    if isinstance(exc, TifluxApiError):
        return exc.status_code or 502, {"success": False, "error": str(exc)}
    return 500, {"success": False, "error": str(exc)}


@app.get("/relatorio/empresas-inativas")
async def relatorio_empresas_inativas(
    months: int = 24,
    limit: int = 100,
    _user: dict = Depends(require_user),
):
    try:
        result = await scan_dormant_clients(get_settings(), months=months, limit=limit)
        return JSONResponse(content=result.to_dict())
    except (OrchestratorError, TifluxApiError, Exception) as exc:
        status, payload = _dormant_error_response(exc)
        return JSONResponse(status_code=status, content=payload)


@app.get("/relatorio/empresas-inativas/stream")
async def relatorio_empresas_inativas_stream(
    months: int = 24,
    limit: int = 100,
    _user: dict = Depends(require_user),
):
    import asyncio
    import contextlib
    import json

    queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

    async def on_progress(payload: dict[str, Any]) -> None:
        await queue.put(("progress", payload))

    async def run_scan() -> None:
        try:
            result = await scan_dormant_clients(
                get_settings(),
                months=months,
                limit=limit,
                on_progress=on_progress,
            )
            await queue.put(("done", result.to_dict()))
        except Exception as exc:
            status, payload = _dormant_error_response(exc)
            await queue.put(("error", {**payload, "status": status}))

    async def event_stream():
        task = asyncio.create_task(run_scan())
        try:
            while True:
                kind, payload = await queue.get()
                yield f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if kind in ("done", "error"):
                    break
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/stats")
async def stats(_user: dict = Depends(require_user)):
    from src.debug_log import dbg
    import time as _time

    t0 = _time.monotonic()
    dbg("A", "main.py:stats", "stats_request_start", {})
    try:
        result = await compute_stats(get_settings())
        dbg(
            "A",
            "main.py:stats",
            "stats_request_done",
            {
                "elapsed_ms": int((_time.monotonic() - t0) * 1000),
                "tiflux_total": result.get("tiflux_total"),
                "vhsys_total": result.get("vhsys_total"),
                "tiflux_dormant": result.get("tiflux_dormant"),
            },
        )
        return JSONResponse(content=result)
    except OrchestratorError as exc:
        dbg("C", "main.py:stats", "stats_orchestrator_error", {"error": str(exc), "status": exc.status_code})
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": str(exc)},
        )
    except Exception as exc:
        dbg("C", "main.py:stats", "stats_exception", {"error": str(exc), "type": type(exc).__name__})
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
