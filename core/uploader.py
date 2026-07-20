"""플랫폼별(유튜브/인스타그램/틱톡) 공식 API 업로드 모듈.

각 플랫폼 업로드 함수는 asyncio.gather로 동시 실행할 수 있도록
동기 SDK 호출을 asyncio.to_thread로 감싼 async 버전을 함께 제공한다.
"""

import asyncio
import json
import logging
import math
import time
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import settings

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_youtube_service():
    if not settings.YOUTUBE_TOKEN_FILE.exists():
        raise RuntimeError(
            "유튜브 인증 토큰이 없습니다. 먼저 `python authorize_youtube.py`를 실행해 1회 인증하세요."
        )

    creds = Credentials.from_authorized_user_file(str(settings.YOUTUBE_TOKEN_FILE), YOUTUBE_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        settings.YOUTUBE_TOKEN_FILE.write_text(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(mp4_path: Path, metadata: dict) -> dict:
    """유튜브 쇼츠로 영상을 업로드한다.

    metadata: title, description, hashtags(list), privacy_status(선택, 기본 private)
    """
    service = _get_youtube_service()

    tags = [tag.lstrip("#") for tag in metadata.get("hashtags", [])]

    body = {
        "snippet": {
            "title": metadata.get("title", mp4_path.stem),
            "description": metadata.get("description", ""),
            "tags": tags,
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            # 실수로 바로 공개되지 않도록 기본값은 private. 실제 배포 시 json에서 public으로 지정.
            "privacyStatus": metadata.get("privacy_status", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True, chunksize=4 * 1024 * 1024)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("유튜브 업로드 진행률: %d%%", int(status.progress() * 100))

    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    logger.info("유튜브 업로드 완료: %s", url)
    return {"platform": "youtube", "video_id": video_id, "url": url}


async def upload_to_youtube_async(mp4_path: Path, metadata: dict) -> dict:
    return await asyncio.to_thread(upload_to_youtube, mp4_path, metadata)


# TODO: Instagram Graph API 자격증명 발급 완료 후 upload_to_instagram(_async) 추가


TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TIKTOK_SINGLE_CHUNK_LIMIT = 64 * 1024 * 1024  # 이 크기 이하면 청크 분할 없이 한 번에 전송
TIKTOK_CHUNK_SIZE = 10 * 1024 * 1024


def _get_tiktok_access_token() -> str:
    """저장된 refresh token으로 access token을 새로 발급받는다 (매 업로드마다 갱신)."""
    if not settings.TIKTOK_TOKEN_FILE.exists():
        raise RuntimeError(
            "틱톡 인증 토큰이 없습니다. 먼저 `python authorize_tiktok.py`를 실행해 1회 인증하세요."
        )
    tokens = json.loads(settings.TIKTOK_TOKEN_FILE.read_text())
    if "refresh_token" not in tokens:
        raise RuntimeError(
            f"저장된 틱톡 토큰이 유효하지 않습니다 ({tokens}). "
            "`python authorize_tiktok.py`를 다시 실행해 재인증하세요."
        )

    resp = requests.post(
        f"{TIKTOK_API_BASE}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    if "access_token" not in new_tokens:
        raise RuntimeError(f"틱톡 토큰 갱신 실패: {new_tokens}")
    settings.TIKTOK_TOKEN_FILE.write_text(json.dumps(new_tokens, ensure_ascii=False, indent=2))
    return new_tokens["access_token"]


def _tiktok_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}


def _tiktok_raise_for_status(resp: requests.Response) -> None:
    if not resp.ok:
        logger.error("틱톡 API 오류 응답 (%s): %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _tiktok_creator_info(access_token: str) -> dict:
    resp = requests.post(
        f"{TIKTOK_API_BASE}/post/publish/creator_info/query/",
        headers=_tiktok_headers(access_token),
    )
    _tiktok_raise_for_status(resp)
    return resp.json()["data"]


def _tiktok_poll_status(access_token: str, publish_id: str, timeout: int = 120, interval: int = 3) -> str:
    elapsed = 0
    while elapsed < timeout:
        resp = requests.post(
            f"{TIKTOK_API_BASE}/post/publish/status/fetch/",
            headers=_tiktok_headers(access_token),
            json={"publish_id": publish_id},
        )
        _tiktok_raise_for_status(resp)
        status = resp.json()["data"]["status"]
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            return status
        time.sleep(interval)
        elapsed += interval
    return "TIMEOUT"


def upload_to_tiktok(mp4_path: Path, metadata: dict) -> dict:
    """틱톡에 영상을 Direct Post로 업로드한다 (push_by_file 방식).

    미심사 앱은 privacy_level 설정과 무관하게 항상 비공개(SELF_ONLY)로만 게시된다.
    """
    access_token = _get_tiktok_access_token()

    creator_info = _tiktok_creator_info(access_token)
    privacy_options = creator_info.get("privacy_level_options", [])
    privacy_level = metadata.get("privacy_status", "SELF_ONLY")
    if privacy_options and privacy_level not in privacy_options:
        privacy_level = privacy_options[0]

    video_size = mp4_path.stat().st_size
    if video_size <= TIKTOK_SINGLE_CHUNK_LIMIT:
        chunk_size = video_size
        total_chunk_count = 1
    else:
        chunk_size = TIKTOK_CHUNK_SIZE
        total_chunk_count = math.ceil(video_size / chunk_size)

    init_body = {
        "post_info": {
            "title": metadata.get("title", mp4_path.stem),
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }
    init_resp = requests.post(
        f"{TIKTOK_API_BASE}/post/publish/video/init/",
        headers=_tiktok_headers(access_token),
        json=init_body,
    )
    _tiktok_raise_for_status(init_resp)
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    with open(mp4_path, "rb") as f:
        start = 0
        while start < video_size:
            end = min(start + chunk_size, video_size) - 1
            f.seek(start)
            chunk = f.read(end - start + 1)
            put_resp = requests.put(
                upload_url,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                },
                data=chunk,
            )
            _tiktok_raise_for_status(put_resp)
            start = end + 1

    status = _tiktok_poll_status(access_token, publish_id)
    logger.info("틱톡 업로드 완료: publish_id=%s status=%s", publish_id, status)
    return {"platform": "tiktok", "publish_id": publish_id, "status": status}


async def upload_to_tiktok_async(mp4_path: Path, metadata: dict) -> dict:
    return await asyncio.to_thread(upload_to_tiktok, mp4_path, metadata)
