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


async def _run_uploads(mp4_path: Path, metadata: dict, platforms: list[str] | None = None) -> dict:
    if platforms is None:
        platforms = [p for p in settings.ENABLED_PLATFORMS if p in _UPLOADERS]
    coros = [_UPLOADERS[p](mp4_path, metadata) for p in platforms]
    results = await asyncio.gather(*coros, return_exceptions=True)
    return dict(zip(platforms, results))


def _extract_video_id(result: dict) -> str | None:
    """플랫폼별 응답에서 성과 조회에 쓸 식별자를 뽑는다.

    틱톡의 publish_id는 영상 ID가 아니라 게시 요청 ID지만, video.list 스코프를
    받기 전까지는 이것 말고 참조할 값이 없으므로 그대로 보관한다.
    """
    return result.get("video_id") or result.get("media_id") or result.get("publish_id")


def _move_pair(mp4_path: Path, json_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in (mp4_path, json_path):
        if path.exists():
            shutil.move(str(path), str(dest_dir / path.name))


def retry_failed(stem: str) -> dict:
    """Failed_Uploads의 쌍을 Upload_Queue로 되돌려 데몬이 다시 처리하게 한다.

    이미 성공한 플랫폼에 중복 게시하지 않도록, 직전 실행에서 실패한 플랫폼만 대상으로 삼는다.
    """
    mp4_path = settings.FAILED_DIR / f"{stem}.mp4"
    json_path = settings.FAILED_DIR / f"{stem}.json"
    if not (mp4_path.exists() and json_path.exists()):
        raise FileNotFoundError(f"재시도할 쌍을 찾을 수 없습니다: {stem}")

    filename = mp4_path.name
    succeeded = database.get_succeeded_platforms(filename)
    targets = [p for p in settings.ENABLED_PLATFORMS if p in _UPLOADERS and p not in succeeded]
    if not targets:
        raise RuntimeError(f"재시도할 플랫폼이 없습니다 (이미 전부 성공): {stem}")

    metadata = enrich_metadata(json_path)
    results = asyncio.run(_run_uploads(mp4_path, metadata, platforms=targets))

    all_success = True
    for platform, result in results.items():
        if isinstance(result, Exception):
            all_success = False
            logger.error("[재시도][%s] 업로드 실패: %s", platform, result)
            database.log_upload(filename, platform, "failed", str(result))
        else:
            detail = result.get("url") or result.get("media_id") or result.get("video_id") or str(result)
            logger.info("[재시도][%s] 업로드 성공: %s", platform, detail)
            database.log_upload(filename, platform, "success", str(detail), _extract_video_id(result))

    dest = settings.ARCHIVE_DIR if all_success else settings.FAILED_DIR
    if dest != settings.FAILED_DIR:
        _move_pair(mp4_path, json_path, dest)
    logger.info("재시도 완료: %s -> %s", filename, dest.name)
    return results


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
            database.log_upload(
                mp4_path.name, platform, "success", str(detail), _extract_video_id(result)
            )

    dest = settings.ARCHIVE_DIR if all_success else settings.FAILED_DIR
    _move_pair(mp4_path, json_path, dest)
    logger.info("처리 완료: %s -> %s", mp4_path.name, dest.name)

    return results
