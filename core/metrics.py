"""업로드한 영상의 성과 지표(조회수/좋아요/댓글수)를 플랫폼 API로 조회한다.

플랫폼별 제약:
- YouTube : youtube.readonly 스코프 필요. 없으면 재인증(authorize_youtube.py) 안내.
- Instagram: like_count/comments_count는 instagram_basic으로 가능.
             조회수(재생수)는 instagram_manage_insights 권한이 있어야 해서 현재는 미지원.
- TikTok  : video.list 스코프가 필요하나 앱 심사 중이라 보류. (publish_id는 영상 ID가 아님)
"""

import json
import logging

import requests
from googleapiclient.errors import HttpError

from config import settings
from core import database
from core.uploader import (
    INSTAGRAM_GRAPH_BASE,
    _get_instagram_access_token,
    _get_youtube_service,
)

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS = ("youtube", "instagram")


def youtube_stats_available() -> bool:
    """저장된 토큰이 통계 조회 스코프를 갖고 있는지 확인한다."""
    if not settings.YOUTUBE_TOKEN_FILE.exists():
        return False
    try:
        scopes = json.loads(settings.YOUTUBE_TOKEN_FILE.read_text()).get("scopes", [])
    except (json.JSONDecodeError, OSError):
        return False
    return any("readonly" in s for s in scopes)


def _fetch_youtube(video_ids: list[str]) -> dict:
    """여러 영상을 한 번의 호출로 조회한다 (id는 최대 50개까지 콤마 구분 지원)."""
    if not video_ids:
        return {}

    service = _get_youtube_service()
    out = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = service.videos().list(part="snippet,statistics", id=",".join(batch)).execute()
        for item in resp.get("items", []):
            stats = item.get("statistics", {})
            out[item["id"]] = {
                "title": item.get("snippet", {}).get("title", ""),
                # 비공개 영상은 일부 카운트가 응답에서 아예 빠지므로 None으로 둔다.
                "views": int(stats["viewCount"]) if "viewCount" in stats else None,
                "likes": int(stats["likeCount"]) if "likeCount" in stats else None,
                "comments": int(stats["commentCount"]) if "commentCount" in stats else None,
            }
    return out


def _fetch_instagram(media_id: str) -> dict | None:
    access_token = _get_instagram_access_token()
    resp = requests.get(
        f"{INSTAGRAM_GRAPH_BASE}/{media_id}",
        params={
            "fields": "caption,like_count,comments_count,permalink",
            "access_token": access_token,
        },
        timeout=30,
    )
    if not resp.ok:
        logger.warning("인스타그램 지표 조회 실패 (%s): %s", media_id, resp.text[:200])
        return None
    data = resp.json()
    caption = (data.get("caption") or "").splitlines()
    return {
        "title": caption[0][:80] if caption else "(캡션 없음)",
        "views": None,  # instagram_manage_insights 권한이 없어 조회 불가
        "likes": data.get("like_count"),
        "comments": data.get("comments_count"),
    }


def refresh_all_metrics() -> dict:
    """성공 업로드 기록을 훑어 지표를 갱신하고 요약을 반환한다."""
    videos = database.get_successful_videos()
    summary = {"updated": 0, "skipped": 0, "errors": []}

    youtube_ids = [v["video_id"] for v in videos if v["platform"] == "youtube"]
    youtube_titles = {v["video_id"]: v["filename"] for v in videos if v["platform"] == "youtube"}

    if youtube_ids:
        if not youtube_stats_available():
            summary["errors"].append(
                "YouTube: 통계 권한이 없습니다. `python authorize_youtube.py`로 재인증하세요."
            )
            summary["skipped"] += len(youtube_ids)
        else:
            try:
                stats = _fetch_youtube(youtube_ids)
                for vid, data in stats.items():
                    database.save_metrics(
                        "youtube",
                        vid,
                        data["title"] or youtube_titles.get(vid, ""),
                        data["views"],
                        data["likes"],
                        data["comments"],
                    )
                    summary["updated"] += 1
                summary["skipped"] += len(youtube_ids) - len(stats)
            except (HttpError, OSError, RuntimeError) as exc:
                summary["errors"].append(f"YouTube: {exc}")

    for video in videos:
        if video["platform"] != "instagram":
            continue
        try:
            data = _fetch_instagram(video["video_id"])
            if data is None:
                summary["skipped"] += 1
                continue
            database.save_metrics(
                "instagram",
                video["video_id"],
                data["title"] or video["filename"],
                data["views"],
                data["likes"],
                data["comments"],
            )
            summary["updated"] += 1
        except (requests.RequestException, RuntimeError) as exc:
            summary["errors"].append(f"Instagram({video['video_id']}): {exc}")

    tiktok_count = sum(1 for v in videos if v["platform"] == "tiktok")
    if tiktok_count:
        summary["skipped"] += tiktok_count
        summary["errors"].append(
            f"TikTok {tiktok_count}건: video.list 스코프 미보유(앱 심사 중)로 지표 조회를 건너뜁니다."
        )

    return summary
