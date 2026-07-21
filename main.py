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


# 인스타그램 장기 토큰(60일)이 업로드 공백기에 만료되지 않도록 주기적으로 점검한다.
TOKEN_CHECK_INTERVAL = 6 * 3600


def on_pair_ready(mp4_path, json_path):
    try:
        process_pair(mp4_path, json_path)
    except Exception:
        # 한 건의 처리 실패가 데몬 전체를 죽이지 않도록 방어한다.
        logger.exception("파이프라인 처리 중 예외 발생: %s", mp4_path.name)


def maintain_tokens():
    """만료가 임박한 토큰을 갱신한다. 실패해도 데몬은 계속 돌아야 한다."""
    if "instagram" not in settings.ENABLED_PLATFORMS:
        return
    try:
        from core.uploader import ensure_instagram_token

        ensure_instagram_token()
    except Exception as exc:
        logger.warning("인스타그램 토큰 점검 실패(다음 주기에 재시도): %s", exc)


def main():
    settings.QUEUE_DIR.mkdir(exist_ok=True)
    database.init_db()

    # start_monitor는 watchdog observer를 띄우므로 import 시점 부작용을 피하기 위해 여기서 임포트
    from core.monitor import start_monitor

    observer = start_monitor(settings.QUEUE_DIR, on_pair_ready)
    logger.info("데몬 시작 완료. 활성 플랫폼: %s", ", ".join(settings.ENABLED_PLATFORMS))

    maintain_tokens()
    last_token_check = time.monotonic()

    try:
        while True:
            time.sleep(1)
            if time.monotonic() - last_token_check >= TOKEN_CHECK_INTERVAL:
                maintain_tokens()
                last_token_check = time.monotonic()
    except KeyboardInterrupt:
        logger.info("종료 신호 수신, 모니터링 중지 중...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
