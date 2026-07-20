"""전역 설정: LLM On/Off, 경로, 모델 이름 등."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "config" / ".env")

# LLM 메타데이터 자동 생성 기본값 (Step 5에서 대시보드 토글과 연동 예정)
LLM_ON = True

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-haiku-4-5-20251001"

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_TOKEN_FILE = BASE_DIR / "config" / "youtube_token.json"

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = "http://localhost:8921/callback"
TIKTOK_TOKEN_FILE = BASE_DIR / "config" / "tiktok_token.json"

QUEUE_DIR = BASE_DIR / "Upload_Queue"
ARCHIVE_DIR = BASE_DIR / "Uploaded_Archive"
DB_PATH = BASE_DIR / "data" / "upload_logs.db"
