"""쌍(mp4+json) 하나를 받아 전체 처리: 메타데이터 보완 -> 비동기 멀티 업로드 -> 로깅 -> 파일 이동."""

import asyncio
import logging
import shutil
from pathlib import Path

from config import settings
from core import database
from core.llm_helper import enrich_metadata
from core.uploader import (
    upload_to_instagram_async,
    upload_to_tiktok_async,
    upload_to_youtube_async,
)

logger = logging.getLogger(__name__)

_UPLOADERS = {
    "youtube": upload_to_youtube_async,
    "tiktok": upload_to_tiktok_async,
    "instagram": upload_to_instagram_async,
}


async def _run_uploads(mp4_path: Path, metadata: dict) -> dict:
    platforms = [p for p in settings.ENABLED_PLATFORMS if p in _UPLOADERS]
    coros = [_UPLOADERS[p](mp4_path, metadata) for p in platforms]
    results = await asyncio.gather(*coros, return_exceptions=True)
    return dict(zip(platforms, results))


def _move_pair(mp4_path: Path, json_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in (mp4_path, json_path):
        if path.exists():
            shutil.move(str(path), str(dest_dir / path.name))


def process_pair(mp4_path: Path, json_path: Path) -> dict:
    """하나의 영상 쌍을 처리하고 플랫폼별 결과를 반환한다."""
    logger.info("처리 시작: %s", mp4_path.name)

    try:
        metadata = enrich_metadata(json_path)
    except Exception as exc:
        logger.exception("메타데이터 처리 실패: %s", mp4_path.name)
        database.log_upload(mp4_path.name, "metadata", "failed", str(exc))
        _move_pair(mp4_path, json_path, settings.FAILED_DIR)
        return {"metadata": exc}

    results = asyncio.run(_run_uploads(mp4_path, metadata))

    all_success = True
    for platform, result in results.items():
        if isinstance(result, Exception):
            all_success = False
            logger.error("[%s] 업로드 실패: %s", platform, result)
            database.log_upload(mp4_path.name, platform, "failed", str(result))
        else:
            detail = result.get("url") or result.get("media_id") or result.get("video_id") or str(result)
            logger.info("[%s] 업로드 성공: %s", platform, detail)
            database.log_upload(mp4_path.name, platform, "success", str(detail))

    dest = settings.ARCHIVE_DIR if all_success else settings.FAILED_DIR
    _move_pair(mp4_path, json_path, dest)
    logger.info("처리 완료: %s -> %s", mp4_path.name, dest.name)

    return results
