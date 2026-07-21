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
        # 기존 DB에도 적용되도록 컬럼 추가는 마이그레이션으로 처리한다.
        # video_id: 성과 조회(조회수/댓글수)에 쓰는 플랫폼 영상 식별자.
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(upload_logs)")}
        if "video_id" not in existing:
            conn.execute("ALTER TABLE upload_logs ADD COLUMN video_id TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS video_metrics (
                platform TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT,
                views INTEGER,
                likes INTEGER,
                comments INTEGER,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (platform, video_id)
            )
            """
        )


def log_upload(filename: str, platform: str, status: str, detail: str, video_id: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO upload_logs (filename, platform, status, detail, created_at, video_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                filename,
                platform,
                status,
                detail,
                datetime.now().isoformat(timespec="seconds"),
                video_id,
            ),
        )


def get_recent_logs(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM upload_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_successful_videos() -> list[dict]:
    """성과 조회 대상: video_id가 있는 성공 업로드 (파일당 플랫폼별 최신 1건)."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT platform, video_id, filename, MAX(created_at) AS created_at
            FROM upload_logs
            WHERE status = 'success' AND video_id IS NOT NULL AND video_id != ''
            GROUP BY platform, video_id
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_succeeded_platforms(filename: str) -> set[str]:
    """해당 파일이 이미 업로드에 성공한 플랫폼 집합 (재시도 시 중복 게시 방지용)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT platform FROM upload_logs WHERE filename = ? AND status = 'success'",
            (filename,),
        ).fetchall()
    return {row["platform"] for row in rows}


def save_metrics(platform: str, video_id: str, title: str, views, likes, comments) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO video_metrics (platform, video_id, title, views, likes, comments, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, video_id) DO UPDATE SET
                title = excluded.title,
                views = excluded.views,
                likes = excluded.likes,
                comments = excluded.comments,
                fetched_at = excluded.fetched_at
            """,
            (
                platform,
                video_id,
                title,
                views,
                likes,
                comments,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def get_metrics() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM video_metrics ORDER BY fetched_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
