"""업로드 결과를 SQLite에 기록/조회한다."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import settings


@contextmanager
def _connect():
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                platform TEXT NOT NULL,
                status TEXT NOT NULL,       -- 'success' | 'failed'
                detail TEXT,                 -- 성공: url/id, 실패: 에러 메시지
                created_at TEXT NOT NULL
            )
            """
        )


def log_upload(filename: str, platform: str, status: str, detail: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO upload_logs (filename, platform, status, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (filename, platform, status, detail, datetime.now().isoformat(timespec="seconds")),
        )


def get_recent_logs(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM upload_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
