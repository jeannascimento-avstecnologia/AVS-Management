from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass
class User:
    id: int
    email: str
    name: str
    password_hash: str
    is_active: bool
    created_at: str
    updated_at: str

    def to_session_dict(self) -> dict:
        return {"email": self.email, "name": self.name, "id": self.id}


class AuthDatabase:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS remember_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL COLLATE NOCASE,
                    ip_address TEXT NOT NULL,
                    attempted_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup
                    ON login_attempts (email, ip_address, attempted_at);
                """
            )

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_user_by_email(self, email: str) -> User | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
                (email.strip().lower(),),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: int) -> User | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self) -> list[User]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY email").fetchall()
        return [self._row_to_user(r) for r in rows]

    def create_user(self, email: str, name: str, password_hash: str) -> User:
        now = _iso(_utcnow())
        normalized_email = email.strip().lower()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (email, name, password_hash, is_active, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (normalized_email, name.strip(), password_hash, now, now),
            )
            user_id = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        assert row is not None
        return self._row_to_user(row)

    def update_password(self, user_id: int, password_hash: str) -> None:
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, now, user_id),
            )

    def record_login_attempt(self, email: str, ip_address: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip_address, attempted_at) VALUES (?, ?, ?)",
                (email.strip().lower(), ip_address, _iso(_utcnow())),
            )

    def count_recent_login_attempts(
        self,
        email: str,
        ip_address: str,
        *,
        window_minutes: int,
    ) -> int:
        since = _iso(_utcnow() - timedelta(minutes=window_minutes))
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM login_attempts
                WHERE email = ? COLLATE NOCASE AND ip_address = ? AND attempted_at >= ?
                """,
                (email.strip().lower(), ip_address, since),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def clear_login_attempts(self, email: str, ip_address: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM login_attempts WHERE email = ? COLLATE NOCASE AND ip_address = ?",
                (email.strip().lower(), ip_address),
            )

    def create_password_reset_token(self, user_id: int, *, hours: int) -> str:
        raw = generate_token()
        token_hash = hash_token(raw)
        now = _utcnow()
        expires = now + timedelta(hours=hours)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ? AND used_at IS NULL",
                (user_id,),
            )
            conn.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, token_hash, _iso(expires), _iso(now)),
            )
        return raw

    def consume_password_reset_token(self, raw_token: str) -> User | None:
        token_hash = hash_token(raw_token)
        now = _utcnow()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT t.*, u.email, u.name, u.password_hash, u.is_active, u.created_at, u.updated_at
                FROM password_reset_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = ? AND t.used_at IS NULL AND t.expires_at > ?
                """,
                (token_hash, _iso(now)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (_iso(now), row["id"]),
            )
            return User(
                id=row["user_id"],
                email=row["email"],
                name=row["name"],
                password_hash=row["password_hash"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def create_remember_token(self, user_id: int, *, days: int) -> str:
        raw = generate_token()
        token_hash = hash_token(raw)
        now = _utcnow()
        expires = now + timedelta(days=days)
        with self._connect() as conn:
            conn.execute("DELETE FROM remember_tokens WHERE user_id = ?", (user_id,))
            conn.execute(
                """
                INSERT INTO remember_tokens (user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, token_hash, _iso(expires), _iso(now)),
            )
        return raw

    def get_user_by_remember_token(self, raw_token: str) -> User | None:
        token_hash = hash_token(raw_token)
        now = _utcnow()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.* FROM remember_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = ? AND t.expires_at > ? AND u.is_active = 1
                """,
                (token_hash, _iso(now)),
            ).fetchone()
        return self._row_to_user(row) if row else None

    def revoke_remember_tokens(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM remember_tokens WHERE user_id = ?", (user_id,))

    def revoke_all_remember_tokens(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM remember_tokens")
