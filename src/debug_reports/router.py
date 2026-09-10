from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from src.auth.deps import require_user
from src.config import get_settings
from src.debug_reports.schemas import SubmitDebugReportInput
from src.debug_reports.service import send_debug_report


def build_debug_reports_router() -> APIRouter:
    router = APIRouter(tags=["debug-reports"])

    @router.post("/debug-reports", status_code=201)
    def create_debug_report(
        request: Request,
        payload: SubmitDebugReportInput,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, bool]:
        return send_debug_report(request, get_settings(), payload, user)

    return router
