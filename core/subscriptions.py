from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SubscriptionStore:
    """
    Lightweight SQLite persistence for users and signal subscriptions.

    This intentionally stores only dashboard preferences.
    Signal execution remains global and cache-backed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS subscriptions (
                    username TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (username, signal_id),
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );
                """
            )
            conn.commit()

    def create_user(self, username: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users (username, created_at) VALUES (?, ?)",
                (username, _now_iso()),
            )
            conn.commit()
            return cur.rowcount > 0

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT username, created_at FROM users ORDER BY username COLLATE NOCASE"
            ).fetchall()
        return [{"username": row["username"], "created_at": row["created_at"]} for row in rows]

    def user_exists(self, username: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        return row is not None

    def list_subscriptions(self, username: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT signal_id
                FROM subscriptions
                WHERE username = ?
                ORDER BY signal_id COLLATE NOCASE
                """,
                (username,),
            ).fetchall()
        return [row["signal_id"] for row in rows]

    def subscribe(self, username: str, signal_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO subscriptions (username, signal_id, created_at)
                VALUES (?, ?, ?)
                """,
                (username, signal_id, _now_iso()),
            )
            conn.commit()
            return cur.rowcount > 0

    def unsubscribe(self, username: str, signal_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM subscriptions WHERE username = ? AND signal_id = ?",
                (username, signal_id),
            )
            conn.commit()
            return cur.rowcount > 0
