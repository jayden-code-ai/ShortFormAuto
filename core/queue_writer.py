"""대시보드에서 영상+메타데이터를 Upload_Queue에 안전하게 배치한다.

파일명을 사람이 직접 맞추지 않아도 되도록 mp4와 json 이름을 코드가 동일하게 생성한다.
데몬이 쓰는 도중의 영상을 집어가지 않도록, 영상은 임시 확장자로 먼저 쓰고 마지막에 이름을 바꾼다.
"""

import json
import re
import unicodedata
from pathlib import Path

from config import settings

# 파일시스템/플랫폼에서 문제가 되는 문자만 치환한다(한글은 그대로 유지).
_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")

VIDEO_SUFFIXES = (".mp4", ".mov")
TEMP_SUFFIX = ".uploading"


def sanitize_stem(name: str) -> str:
    """제목/파일명을 안전한 파일 이름(확장자 제외)으로 바꾼다."""
    stem = Path(name).stem
    stem = unicodedata.normalize("NFC", stem)  # macOS 자소 분리(NFD) 정규화
    stem = _UNSAFE_CHARS.sub("_", stem)
    stem = _WHITESPACE.sub("_", stem).strip("._ ")
    return stem[:80] or "untitled"


def resolve_available_stem(stem: str, queue_dir: Path | None = None) -> str:
    """이미 같은 이름이 대기열에 있으면 -1, -2 를 붙여 충돌을 피한다."""
    queue_dir = queue_dir or settings.QUEUE_DIR
    existing = {p.stem.casefold() for p in queue_dir.iterdir()} if queue_dir.exists() else set()

    if stem.casefold() not in existing:
        return stem
    for i in range(1, 1000):
        candidate = f"{stem}-{i}"
        if candidate.casefold() not in existing:
            return candidate
    raise RuntimeError(f"사용 가능한 파일 이름을 찾지 못했습니다: {stem}")


def build_metadata(title: str, description: str, hashtags, privacy_status: str | None = None) -> dict:
    """폼 입력을 업로드용 JSON 구조로 정리한다."""
    if isinstance(hashtags, str):
        # "#a, #b" / "#a #b" / "a b" 등 어떤 형태로 입력해도 리스트로 만든다.
        raw = [t for t in re.split(r"[,\s]+", hashtags) if t.strip()]
    else:
        raw = list(hashtags or [])

    tags = []
    for tag in raw:
        tag = tag.strip().lstrip("#")
        if tag:
            tags.append(f"#{tag}")

    metadata = {
        "title": title.strip(),
        "description": description.strip(),
        "hashtags": tags,
    }
    if privacy_status:
        metadata["privacy_status"] = privacy_status
    return metadata


def write_to_queue(
    video_bytes: bytes,
    original_filename: str,
    metadata: dict,
    queue_dir: Path | None = None,
) -> dict:
    """영상과 메타데이터를 같은 이름으로 Upload_Queue에 넣는다.

    반환: {"stem", "video", "json"}
    """
    queue_dir = queue_dir or settings.QUEUE_DIR
    queue_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename).suffix.casefold()
    if suffix not in VIDEO_SUFFIXES:
        raise ValueError(f"지원하지 않는 영상 형식입니다: {suffix or '(확장자 없음)'}")

    if not metadata.get("title"):
        raise ValueError("제목은 비워둘 수 없습니다.")

    # 파일명은 제목이 아니라 원본 영상 파일명을 기준으로 삼는다(제목은 자유롭게 바뀔 수 있으므로).
    stem = resolve_available_stem(sanitize_stem(original_filename), queue_dir)

    video_path = queue_dir / f"{stem}{suffix}"
    json_path = queue_dir / f"{stem}.json"
    temp_path = queue_dir / f"{stem}{suffix}{TEMP_SUFFIX}"

    # 1) 영상을 임시 확장자로 기록 (감시 대상 확장자가 아니라 데몬이 반응하지 않음)
    temp_path.write_bytes(video_bytes)
    try:
        # 2) 메타데이터 기록
        json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        # 3) 마지막에 영상 이름을 확정 -> 이 시점에 쌍이 완성되어 데몬이 트리거된다.
        temp_path.rename(video_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        json_path.unlink(missing_ok=True)
        raise

    return {"stem": stem, "video": str(video_path), "json": str(json_path)}
