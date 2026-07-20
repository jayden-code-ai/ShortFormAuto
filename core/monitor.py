"""Upload_Queue 폴더를 감시하여 .mp4/.json 파일 쌍이 준비되면 콜백을 트리거한다."""

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

STABLE_CHECK_INTERVAL = 1.0  # 초 단위 크기 재확인 간격
STABLE_CHECK_COUNT = 2  # 연속으로 크기가 동일해야 "쓰기 완료"로 판단


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
        if path.suffix.lower() not in (".mp4", ".json"):
            return

        stem = path.stem
        if stem in self._triggered:
            return

        mp4_path = self.queue_dir / f"{stem}.mp4"
        json_path = self.queue_dir / f"{stem}.json"
        if not (mp4_path.exists() and json_path.exists()):
            return

        self._triggered.add(stem)
        logger.info("쌍 감지됨: '%s' (안정화 대기 중...)", stem)
        if _is_file_stable(mp4_path) and _is_file_stable(json_path):
            logger.info("쌍 준비 완료: %s", stem)
            self.on_pair_ready(mp4_path, json_path)
        else:
            self._triggered.discard(stem)


def start_monitor(queue_dir: Path, on_pair_ready) -> Observer:
    handler = UploadQueueHandler(queue_dir, on_pair_ready)
    observer = Observer()
    observer.schedule(handler, str(queue_dir), recursive=False)
    observer.start()
    logger.info("모니터링 시작: %s", queue_dir)
    return observer
