"""1회성 스크립트: 브라우저로 유튜브 OAuth 동의를 받아 refresh token을 저장한다.

사용법: venv 활성화 후 `python authorize_youtube.py` 실행 -> 브라우저가 열리면 로그인/동의.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    if not (settings.YOUTUBE_CLIENT_ID and settings.YOUTUBE_CLIENT_SECRET):
        raise SystemExit("config/.env에 YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET을 먼저 입력하세요.")

    client_config = {
        "installed": {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    settings.YOUTUBE_TOKEN_FILE.write_text(creds.to_json())
    print(f"저장 완료: {settings.YOUTUBE_TOKEN_FILE}")


if __name__ == "__main__":
    main()
