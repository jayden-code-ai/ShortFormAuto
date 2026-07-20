"""전역 설정: LLM On/Off, 경로, 모델 이름 등."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "config" / ".env")

# LLM 메타데이터 자동 생성 기본값 (대시보드 토글의 초기값. 런타임 값은 runtime_config가 관리)
LLM_ON = True

# 업로드를 시도할 플랫폼 (토큰 미설정/보류 플랫폼은 여기서 제외하면 됨)
# 환경변수 ENABLED_PLATFORMS로 재정의 가능 (쉼표 구분, 빈 문자열이면 업로드 없이 파이프라인만 동작)
_platforms_env = os.getenv("ENABLED_PLATFORMS")
if _platforms_env is not None:
    ENABLED_PLATFORMS = [p.strip() for p in _platforms_env.split(",") if p.strip()]
else:
    ENABLED_PLATFORMS = ["youtube", "tiktok", "instagram"]

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = "claude-haiku-4-5-20251001"

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_TOKEN_FILE = BASE_DIR / "config" / "youtube_token.json"

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_REDIRECT_URI = "http://localhost:8921/callback"
TIKTOK_TOKEN_FILE = BASE_DIR / "config" / "tiktok_token.json"

INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_SEED_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
INSTAGRAM_TOKEN_FILE = BASE_DIR / "config" / "instagram_token.json"

QUEUE_DIR = BASE_DIR / "Upload_Queue"
ARCHIVE_DIR = BASE_DIR / "Uploaded_Archive"
FAILED_DIR = BASE_DIR / "Failed_Uploads"
DB_PATH = BASE_DIR / "data" / "upload_logs.db"
RUNTIME_CONFIG_PATH = BASE_DIR / "data" / "runtime_config.json"
