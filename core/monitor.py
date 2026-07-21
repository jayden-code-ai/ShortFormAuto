"""Upload_Queue 폴더를 감시하여 .mp4/.json 파일 쌍이 준비되면 콜백을 트리거한다."""

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
# NAS(SMB/AFP) 네트워크 마운트에서는 FSEvents 기반 기본 Observer가 이벤트를 놓치는 경우가 있어,
# 파일시스템 종류에 무관하게 동작하는 PollingObserver를 사용한다.
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0  # 폴링 주기(초)

STABLE_CHECK_INTERVAL = 1.0  # 초 단위 크기 재확인 간격
STABLE_CHECK_COUNT = 2  # 연속으로 크기가 동일해야 "쓰기 완료"로 판단


def _find_by_stem(queue_dir: Path, stem: str, suffix: str) -> Path | None:
    """stem/확장자를 대소문자 구분 없이 비교해 실제 파일 경로를 찾는다.

    경로를 f"{stem}.mp4"로 조립하면 `.MP4` 같은 대문자 확장자를 가진 파일이
    대소문자 구분 파일시스템에서 발견되지 않고, 대소문자 무시 파일시스템에서는
    원본과 다른 이름으로 이동되는 문제가 있어 실제 파일을 직접 찾는다.
    """
    target = stem.casefold()
    for path in queue_dir.iterdir():
        if path.stem.casefold() == target and path.suffix.casefold() == suffix:
            return path
    return None


def _is_file_stable(path: Path) -> bool:
    # NAS 복사 도중 파일이 계속 커질 수 있으므로, 크기 변화가 멈출 때까지 대기한다.
    last_size = -1
    stable_count = 0
    while stable_count < STABLE_CHECK_COUNT:
        if not path.exists():
            return False
        size = path.stat().st_size
        if size == last_size:
            stable_count += 1
        else:
            stable_count = 0
        last_size = size
        time.sleep(STABLE_CHECK_INTERVAL)
    return True


class UploadQueueHandler(FileSystemEventHandler):
    def __init__(self, queue_dir: Path, on_pair_ready):
        self.queue_dir = queue_dir
        self.on_pair_ready = on_pair_ready
        self._triggered = set()

    def on_created(self, event):
        if not event.is_directory:
            self._handle_path(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._handle_path(Path(event.dest_path))

    def _handle_path(self, path: Path):
        if path.suffix.casefold() not in (".mp4", ".json"):
            return

        # 대소문자만 다른 이름이 같은 쌍으로 취급되도록 정규화한 키로 중복을 막는다.
        key = path.stem.casefold()
        if key in self._triggered:
            return

        mp4_path = _find_by_stem(self.queue_dir, path.stem, ".mp4")
        json_path = _find_by_stem(self.queue_dir, path.stem, ".json")
        if not (mp4_path and json_path):
            return

        self._triggered.add(key)
        try:
            logger.info("쌍 감지됨: '%s' (안정화 대기 중...)", path.stem)
            if _is_file_stable(mp4_path) and _is_file_stable(json_path):
                logger.info("쌍 준비 완료: %s", path.stem)
                self.on_pair_ready(mp4_path, json_path)
        finally:
            # 처리가 끝나면 키를 비운다. 남겨두면 같은 파일명을 나중에 다시 넣었을 때
            # 데몬 재시작 전까지 조용히 무시된다.
            self._triggered.discard(key)


def start_monitor(queue_dir: Path, on_pair_ready) -> PollingObserver:
    handler = UploadQueueHandler(queue_dir, on_pair_ready)
    observer = PollingObserver(timeout=POLL_INTERVAL)
    observer.schedule(handler, str(queue_dir), recursive=False)
    observer.start()
    logger.info("모니터링 시작: %s", queue_dir)
    return observer
