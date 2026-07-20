"""백그라운드 데몬 실행 파일: Upload_Queue를 감시하고 쌍이 준비되면 처리한다."""

import logging
import time
from pathlib import Path

from core.monitor import start_monitor

BASE_DIR = Path(__file__).resolve().parent
QUEUE_DIR = BASE_DIR / "Upload_Queue"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def on_pair_ready(mp4_path: Path, json_path: Path):
    # TODO(Step 2~4): LLM 메타데이터 보완, 업로드, 아카이브 이동, 로깅
    logger.info("처리 대상 쌍: %s / %s", mp4_path.name, json_path.name)


def main():
    QUEUE_DIR.mkdir(exist_ok=True)
    observer = start_monitor(QUEUE_DIR, on_pair_ready)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("종료 신호 수신, 모니터링 중지 중...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
