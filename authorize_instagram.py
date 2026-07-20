"""1회성 스크립트: Facebook Login 방식의 단기 EAA 토큰을 장기(60일) 토큰으로 교환해 저장한다.

Graph API Explorer에서 발급받은 단기 사용자 토큰을 config/.env의 INSTAGRAM_ACCESS_TOKEN에 넣고 실행.
교환에는 메인 Facebook 앱의 App ID / App Secret이 필요하다.

사용법: venv 활성화 후 `python authorize_instagram.py` 실행 (브라우저 필요 없음).
"""

import json
import time

import requests

from config import settings

GRAPH_API_VERSION = "v23.0"


def main():
    if not (
        settings.INSTAGRAM_APP_ID
        and settings.INSTAGRAM_APP_SECRET
        and settings.INSTAGRAM_SEED_ACCESS_TOKEN
    ):
        raise SystemExit(
            "config/.env에 INSTAGRAM_APP_ID / INSTAGRAM_APP_SECRET / INSTAGRAM_ACCESS_TOKEN을 먼저 입력하세요."
        )

    resp = requests.get(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.INSTAGRAM_APP_ID,
            "client_secret": settings.INSTAGRAM_APP_SECRET,
            "fb_exchange_token": settings.INSTAGRAM_SEED_ACCESS_TOKEN,
        },
    )
    data = resp.json()

    if "access_token" not in data:
        raise SystemExit(f"토큰 교환 실패: {data}")

    data["obtained_at"] = int(time.time())
    settings.INSTAGRAM_TOKEN_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    days = data.get("expires_in", 0) // 86400
    print(f"저장 완료: {settings.INSTAGRAM_TOKEN_FILE} (만료까지 약 {days}일)")


if __name__ == "__main__":
    main()
