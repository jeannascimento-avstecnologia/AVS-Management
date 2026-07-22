"""HMAC-SHA256 para webhooks n8n (ADR-0003). Header: X-AVS-Signature."""

from __future__ import annotations

import hmac
import hashlib

SIGNATURE_HEADER = "X-AVS-Signature"


class HmacSecretMissingError(Exception):
    """Segredo ausente — fail closed (não assinar / não aceitar)."""


def sign_body(secret: str, raw_body: bytes) -> str:
    """Retorna hex digest HMAC-SHA256 do body raw."""
    key = (secret or "").strip()
    if not key:
        raise HmacSecretMissingError("N8N_WEBHOOK_SECRET ausente — fail closed.")
    return hmac.new(key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    """Compara timing-safe. False se secret/header ausentes ou inválidos."""
    key = (secret or "").strip()
    provided = (signature_header or "").strip()
    if not key or not provided:
        return False
    expected = hmac.new(key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)
