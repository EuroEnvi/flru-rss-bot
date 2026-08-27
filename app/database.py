from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import FeedItem


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=15000")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS seen_items (
                    uid TEXT PRIMARY KEY,
                    link TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    published_at TEXT,
                    first_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def has_seen(self, uid: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM seen_items WHERE uid = ? LIMIT 1", (uid,)
            ).fetchone()
        return row is not None

    def mark_seen(self, item: FeedItem) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO seen_items
                    (uid, link, title, published_at, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    item.uid,
                    item.link,
                    item.title,
                    item.published_at.isoformat() if item.published_at else None,
                    now,
                ),
            )

    def mark_many_seen(self, items: Iterable[FeedItem]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                item.uid,
                item.link,
                item.title,
                item.published_at.isoformat() if item.published_at else None,
                now,
            )
            for item in items
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO seen_items
                    (uid, link, title, published_at, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def seen_count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM seen_items").fetchone()
        return int(row["count"] if row else 0)

    def get_state(self, key: str, default: str | None = None) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM state WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else default

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get_state(key)
        if value is None:
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    def set_bool(self, key: str, value: bool) -> None:
        self.set_state(key, "1" if value else "0")
