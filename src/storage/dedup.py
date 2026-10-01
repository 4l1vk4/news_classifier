"""Deduplication and persistence store for news items."""
import sqlite3
import time
from pathlib import Path
from typing import List, Optional
from src.models import NewsItem

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seen_news.db"


class DedupStore:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._is_memory = str(self.db_path) == ":memory:"
        self._mem_conn = sqlite3.connect(":memory:") if self._is_memory else None
        if not self._is_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory:
            return self._mem_conn
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_news (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    title TEXT,
                    seen_at REAL
                )
                """
            )
            conn.commit()

    def is_seen(self, item_id: str) -> bool:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM seen_news WHERE id = ?", (item_id,))
            return cur.fetchone() is not None

    def mark_seen(self, item_id: str, source: str = "", title: str = "") -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_news (id, source, title, seen_at)
                VALUES (?, ?, ?, ?)
                """,
                (item_id, source, title, time.time()),
            )
            conn.commit()

    def filter_unseen(self, items: List[NewsItem]) -> List[NewsItem]:
        """Returns only items that have not been seen before, and marks them as seen."""
        unseen = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            for item in items:
                cur.execute("SELECT 1 FROM seen_news WHERE id = ?", (item.id,))
                if cur.fetchone() is None:
                    unseen.append(item)
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO seen_news (id, source, title, seen_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (item.id, item.source, item.title, time.time()),
                    )
            conn.commit()
        return unseen

    def count(self) -> int:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM seen_news")
            row = cur.fetchone()
            return row[0] if row else 0

    def clear(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM seen_news")
            conn.commit()
