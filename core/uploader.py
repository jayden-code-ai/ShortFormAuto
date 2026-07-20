"""플랫폼별(유튜브/인스타그램/틱톡) 공식 API 업로드 모듈.

각 플랫폼 업로드 함수는 asyncio.gather로 동시 실행할 수 있도록
동기 SDK 호출을 asyncio.to_thread로 감싼 async 버전을 함께 제공한다.
"""

import asyncio
import logging
from pathlib import Path

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
# TODO: TikTok Content Posting API 자격증명 발급 완료 후 upload_to_tiktok(_async) 추가
