from __future__ import annotations

import re
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

MIN_PASSWORD_LENGTH = 5
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

_BLOCKLIST: set[str] | None = None
_BLOCKLIST_PATH = Path(__file__).resolve().parent / "data" / "common_passwords.txt"


def _load_blocklist() -> set[str]:
    global _BLOCKLIST
    if _BLOCKLIST is not None:
        return _BLOCKLIST
    entries: set[str] = set()
    if _BLOCKLIST_PATH.is_file():
        for line in _BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines():
            value = line.strip().lower()
            if value and not value.startswith("#"):
                entries.add(value)
    _BLOCKLIST = entries
    return entries


def normalize_password(password: str) -> str:
    return password.strip()


def validate_password_policy(password: str) -> list[str]:
    errors: list[str] = []
    normalized = normalize_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        errors.append(f"A senha deve ter no mínimo {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"A senha deve ter no máximo {MAX_PASSWORD_LENGTH} caracteres.")
    if normalized and not re.search(r"[a-z]", normalized):
        errors.append("A senha deve conter pelo menos uma letra minúscula.")
    if normalized and not re.search(r"[A-Z]", normalized):
        errors.append("A senha deve conter pelo menos uma letra maiúscula.")
    if normalized and not re.search(r"\d", normalized):
        errors.append("A senha deve conter pelo menos um número.")
    blocklist = _load_blocklist()
    if normalized.lower() in blocklist:
        errors.append("Esta senha é muito comum. Escolha outra mais segura.")
    return errors


def hash_password(password: str) -> str:
    normalized = normalize_password(password)
    policy_errors = validate_password_policy(normalized)
    if policy_errors:
        raise ValueError(policy_errors[0])
    return _hasher.hash(normalized)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, normalize_password(password))
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
