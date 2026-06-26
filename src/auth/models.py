from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from src.auth.permissions import ALL_PERMISSIONS, empty_permissions


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
class AuditLogEntry:
    id: int
    user_id: int | None
    user_email: str
    action: str
    resource: str
    detail: str
    ip_address: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "action": self.action,
            "resource": self.resource,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "created_at": self.created_at,
        }


@dataclass
class User:
    id: int
    email: str
    name: str
    password_hash: str
    is_active: bool
    created_at: str
    updated_at: str
    backup_email: str = ""
    phone: str = ""

    def to_session_dict(self) -> dict:
        return {"email": self.email, "name": self.name, "id": self.id}

    def to_profile_dict(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            "backup_email": self.backup_email or "",
            "phone": self.phone or "",
        }


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

                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(user_id, permission),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_email TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '{}',
                    ip_address TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_audit_logs_created
                    ON audit_logs (created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_audit_logs_user
                    ON audit_logs (user_id, created_at DESC);
                """
            )
            self._migrate_user_profile_columns(conn)
            self._seed_initial_admin_permissions(conn)

    def _seed_initial_admin_permissions(self, conn: sqlite3.Connection) -> None:
        from src.auth.cli import SEED_USERS

        seed_emails = {email.strip().lower() for email, _ in SEED_USERS}
        if not seed_emails:
            return
        placeholders = ",".join("?" * len(seed_emails))
        rows = conn.execute(
            f"SELECT id, email FROM users WHERE email IN ({placeholders})",
            tuple(seed_emails),
        ).fetchall()
        for row in rows:
            self._grant_all_permissions_conn(conn, int(row["id"]))

    def _grant_all_permissions_conn(self, conn: sqlite3.Connection, user_id: int) -> None:
        for permission in ALL_PERMISSIONS:
            conn.execute(
                """
                INSERT INTO user_permissions (user_id, permission, enabled)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, permission) DO UPDATE SET enabled = 1
                """,
                (user_id, permission),
            )

    def _migrate_user_profile_columns(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "backup_email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN backup_email TEXT NOT NULL DEFAULT ''")
        if "phone" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''")

    def _row_to_user(self, row: sqlite3.Row) -> User:
        keys = row.keys()
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            password_hash=row["password_hash"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            backup_email=row["backup_email"] if "backup_email" in keys else "",
            phone=row["phone"] if "phone" in keys else "",
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

    def update_profile(
        self,
        user_id: int,
        *,
        name: str,
        backup_email: str,
        phone: str,
    ) -> User | None:
        now = _iso(_utcnow())
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE users
                SET name = ?, backup_email = ?, phone = ?, updated_at = ?
                WHERE id = ?
                """,
                (name.strip(), backup_email.strip(), phone.strip(), now, user_id),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

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
                SELECT u.*
                FROM password_reset_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = ? AND t.used_at IS NULL AND t.expires_at > ?
                """,
                (token_hash, _iso(now)),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?",
                (_iso(now), token_hash),
            )
            return self._row_to_user(row)

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

    def deactivate_user(self, user_id: int) -> bool:
        now = _iso(_utcnow())
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1",
                (now, user_id),
            )
        return cur.rowcount > 0

    def get_permissions_map(self, user_id: int) -> dict[str, bool]:
        base = empty_permissions()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT permission, enabled FROM user_permissions WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        for row in rows:
            if row["permission"] in base:
                base[row["permission"]] = bool(row["enabled"])
        return base

    def is_permission_enabled(self, user_id: int, permission: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT enabled FROM user_permissions
                WHERE user_id = ? AND permission = ?
                """,
                (user_id, permission),
            ).fetchone()
        return bool(row and row["enabled"])

    def set_permissions(self, user_id: int, permissions: dict[str, bool]) -> dict[str, bool]:
        with self._connect() as conn:
            for key in ALL_PERMISSIONS:
                enabled = 1 if permissions.get(key) else 0
                conn.execute(
                    """
                    INSERT INTO user_permissions (user_id, permission, enabled)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, permission) DO UPDATE SET enabled = excluded.enabled
                    """,
                    (user_id, key, enabled),
                )
        return self.get_permissions_map(user_id)

    def grant_all_permissions(self, user_id: int) -> dict[str, bool]:
        with self._connect() as conn:
            self._grant_all_permissions_conn(conn, user_id)
        return self.get_permissions_map(user_id)

    def count_active_users_with_permission(self, permission: str, *, exclude_user_id: int | None = None) -> int:
        query = """
            SELECT COUNT(*) AS cnt
            FROM users u
            JOIN user_permissions p ON p.user_id = u.id
            WHERE u.is_active = 1 AND p.permission = ? AND p.enabled = 1
        """
        params: list[Any] = [permission]
        if exclude_user_id is not None:
            query += " AND u.id != ?"
            params.append(exclude_user_id)
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def insert_audit_log(
        self,
        *,
        user_id: int | None,
        user_email: str,
        action: str,
        resource: str,
        detail: str,
        ip_address: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (user_id, user_email, action, resource, detail, ip_address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, user_email, action, resource, detail, ip_address, _iso(_utcnow())),
            )

    def list_audit_logs(
        self,
        *,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        query = "SELECT * FROM audit_logs"
        params: list[Any] = []
        if user_id is not None:
            query += " WHERE user_id = ?"
            params.append(user_id)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_audit(row) for row in rows]

    def _row_to_audit(self, row: sqlite3.Row) -> AuditLogEntry:
        return AuditLogEntry(
            id=row["id"],
            user_id=row["user_id"],
            user_email=row["user_email"],
            action=row["action"],
            resource=row["resource"],
            detail=row["detail"],
            ip_address=row["ip_address"],
            created_at=row["created_at"],
        )

    def revoke_remember_tokens(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM remember_tokens WHERE user_id = ?", (user_id,))

    def revoke_all_remember_tokens(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM remember_tokens")
