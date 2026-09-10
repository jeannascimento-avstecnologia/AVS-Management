from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SessionLogEventType = Literal[
    "navigation",
    "click",
    "console.error",
    "console.warn",
    "error",
    "unhandledrejection",
    "api.error",
]
DebugReportApp = Literal["avs-management"]

DEBUG_REPORT_MAX_SCREENSHOT_BASE64 = 4 * 1024 * 1024
DEBUG_REPORT_MAX_SESSION_EVENTS_SERVER = 500


class SessionLogEvent(BaseModel):
    ts: str
    type: SessionLogEventType
    message: str = Field(max_length=2000)
    meta: dict[str, Any] | None = None


class DebugReportViewport(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DebugReportClientMeta(BaseModel):
    url: str = Field(max_length=2000)
    userAgent: str = Field(max_length=500)
    viewport: DebugReportViewport
    app: DebugReportApp


class SubmitDebugReportInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    notes: str | None = Field(default=None, max_length=2000)
    screenshotBase64: str = Field(min_length=1)
    sessionLog: list[SessionLogEvent] = Field(default_factory=list, max_length=DEBUG_REPORT_MAX_SESSION_EVENTS_SERVER)
    clientMeta: DebugReportClientMeta

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_required(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("notes", mode="before")
    @classmethod
    def empty_notes_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value
