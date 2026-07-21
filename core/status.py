"""대시보드 상단 상태 바용 조회: 데몬 가동 여부, 대기열, 토큰 유효성.

여기서는 네트워크 호출을 하지 않는다(대시보드가 자주 재실행되므로).
토큰은 파일에 저장된 만료 정보만으로 판단한다.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from config import settings

LAUNCHD_LABEL = "com.shortformauto.daemon"
DAEMON_PATTERN = "Shortform_Auto/main.py"


def get_daemon_status() -> dict:
    """데몬 프로세스가 살아있는지 확인한다."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", DAEMON_PATTERN], capture_output=True, text=True, timeout=5
        )
        pids = [p for p in result.stdout.split() if p]
    except (subprocess.SubprocessError, OSError):
        return {"running": False, "pid": None, "detail": "확인 실패"}

    if not pids:
        return {"running": False, "pid": None, "detail": "실행 중 아님"}
    return {"running": True, "pid": pids[0], "detail": f"PID {pids[0]}"}


def get_queue_status() -> dict:
    """Upload_Queue에 쌓여 있는 파일 현황."""
    queue_dir: Path = settings.QUEUE_DIR
    if not queue_dir.exists():
        return {"pairs": 0, "orphans": [], "total": 0}

    mp4_stems, json_stems = set(), set()
    for path in queue_dir.iterdir():
        if path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix == ".mp4":
            mp4_stems.add(path.stem)
        elif suffix == ".json":
            json_stems.add(path.stem)

    pairs = mp4_stems & json_stems
    # 짝이 없어 대기 중인 파일(업로드가 트리거되지 않는 상태)
    orphans = sorted(
        [f"{s}.mp4" for s in mp4_stems - json_stems] + [f"{s}.json" for s in json_stems - mp4_stems]
    )
    return {"pairs": len(pairs), "orphans": orphans, "total": len(mp4_stems) + len(json_stems)}


def _days_left(expiry_epoch: float) -> int:
    return int((expiry_epoch - datetime.now().timestamp()) // 86400)


def get_token_status() -> dict:
    """플랫폼별 토큰 존재/만료 상태. 값은 읽되 토큰 자체는 반환하지 않는다."""
    result = {}

    # YouTube: refresh token이 있으면 만료돼도 자동 갱신되므로 유효로 본다.
    yt = settings.YOUTUBE_TOKEN_FILE
    if not yt.exists():
        result["youtube"] = {"ok": False, "detail": "미인증"}
    else:
        try:
            data = json.loads(yt.read_text())
            has_refresh = bool(data.get("refresh_token"))
            scopes = data.get("scopes", [])
            can_read = any("readonly" in s for s in scopes)
            detail = "정상" if has_refresh else "refresh token 없음"
            if has_refresh and not can_read:
                detail = "업로드만 (통계 권한 없음)"
            result["youtube"] = {"ok": has_refresh, "detail": detail, "can_read_stats": can_read}
        except (json.JSONDecodeError, OSError) as exc:
            result["youtube"] = {"ok": False, "detail": f"읽기 실패: {exc}"}

    # TikTok: refresh token 만료일이 중요(재인증 필요 시점).
    tt = settings.TIKTOK_TOKEN_FILE
    if not tt.exists():
        result["tiktok"] = {"ok": False, "detail": "미인증"}
    else:
        try:
            data = json.loads(tt.read_text())
            ok = bool(data.get("refresh_token"))
            result["tiktok"] = {"ok": ok, "detail": "정상" if ok else "refresh token 없음"}
        except (json.JSONDecodeError, OSError) as exc:
            result["tiktok"] = {"ok": False, "detail": f"읽기 실패: {exc}"}

    # Instagram: 장기 토큰이라 만료일을 남은 일수로 보여준다.
    ig = settings.INSTAGRAM_TOKEN_FILE
    if not ig.exists():
        result["instagram"] = {"ok": False, "detail": "미인증"}
    else:
        try:
            data = json.loads(ig.read_text())
            obtained = data.get("obtained_at", 0)
            expires_in = data.get("expires_in", 0)
            days = _days_left(obtained + expires_in)
            result["instagram"] = {
                "ok": days > 0,
                "detail": f"{days}일 남음" if days > 0 else "만료됨",
                "days_left": days,
            }
        except (json.JSONDecodeError, OSError) as exc:
            result["instagram"] = {"ok": False, "detail": f"읽기 실패: {exc}"}

    return result


def get_failed_items() -> list[dict]:
    """Failed_Uploads에 있는 재시도 대상 쌍 목록."""
    failed_dir: Path = settings.FAILED_DIR
    if not failed_dir.exists():
        return []

    items = []
    for mp4 in sorted(failed_dir.iterdir()):
        if mp4.suffix.lower() != ".mp4":
            continue
        json_path = failed_dir / f"{mp4.stem}.json"
        if json_path.exists():
            items.append(
                {
                    "stem": mp4.stem,
                    "mp4": str(mp4),
                    "json": str(json_path),
                    "size_mb": round(mp4.stat().st_size / 1024 / 1024, 1),
                    "modified": datetime.fromtimestamp(mp4.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
    return items
