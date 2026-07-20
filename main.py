"""백그라운드 데몬 실행 파일: Upload_Queue를 감시하고 쌍이 준비되면 전체 파이프라인을 실행한다."""

import logging
import time

from config import settings
from core import database
from core.pipeline import process_pair

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def on_pair_ready(mp4_path, json_path):
    try:
        process_pair(mp4_path, json_path)
    except Exception:
        # 한 건의 처리 실패가 데몬 전체를 죽이지 않도록 방어한다.
        logger.exception("파이프라인 처리 중 예외 발생: %s", mp4_path.name)


def main():
    settings.QUEUE_DIR.mkdir(exist_ok=True)
    database.init_db()

    # start_monitor는 watchdog observer를 띄우므로 import 시점 부작용을 피하기 위해 여기서 임포트
    from core.monitor import start_monitor

    observer = start_monitor(settings.QUEUE_DIR, on_pair_ready)
    logger.info("데몬 시작 완료. 활성 플랫폼: %s", ", ".join(settings.ENABLED_PLATFORMS))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("종료 신호 수신, 모니터링 중지 중...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
