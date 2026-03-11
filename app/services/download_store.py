from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


class DownloadStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._write_lock = threading.Lock()

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS downloads (
                    filename TEXT PRIMARY KEY,
                    count INTEGER NOT NULL DEFAULT 0,
                    last_download_at TEXT
                )
                """
            )

    def load_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT filename, count FROM downloads"
            ).fetchall()
        return {row["filename"]: int(row["count"]) for row in rows}

    def increment(self, filename: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._write_lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO downloads (filename, count, last_download_at)
                    VALUES (?, 1, ?)
                    ON CONFLICT(filename) DO UPDATE SET
                        count = downloads.count + 1,
                        last_download_at = excluded.last_download_at
                    """,
                    (filename, timestamp),
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=30,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection

