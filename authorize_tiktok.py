"""1회성 스크립트: 브라우저로 틱톡 OAuth 동의를 받아 refresh token을 저장한다.

사용법: venv 활성화 후 `python authorize_tiktok.py` 실행 -> 브라우저가 열리면 로그인/동의.
TikTok Login Kit 앱 설정의 Desktop Redirect URI가 settings.TIKTOK_REDIRECT_URI와
정확히 일치해야 한다.
"""

import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser

import requests

from config import settings

SCOPES = "user.info.basic,video.publish"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"[디버그] 콜백 원본 경로: {self.path}")
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _result["code"] = params.get("code", [None])[0]
        _result["state"] = params.get("state", [None])[0]
        _result["error"] = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("인증 완료. 이 창은 닫으셔도 됩니다.".encode("utf-8"))

    def log_message(self, format, *args):
        pass


def _generate_pkce_pair() -> tuple[str, str]:
    # TikTok은 RFC 7636 표준(base64url)이 아니라 SHA256의 hex 인코딩을 code_challenge로 요구한다.
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = hashlib.sha256(code_verifier.encode("ascii")).hexdigest()
    return code_verifier, code_challenge


def main():
    if not (settings.TIKTOK_CLIENT_KEY and settings.TIKTOK_CLIENT_SECRET):
        raise SystemExit("config/.env에 TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET을 먼저 입력하세요.")

    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _generate_pkce_pair()
    auth_params = {
        "client_key": settings.TIKTOK_CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": settings.TIKTOK_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    port = urllib.parse.urlparse(settings.TIKTOK_REDIRECT_URI).port
    server = http.server.HTTPServer(("localhost", port), _CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    print("브라우저에서 틱톡 로그인/동의를 진행해주세요...")
    print("(캐시된 이전 탭이 있으면 반드시 닫고, 새 시크릿 창에서 아래 URL로 접속하세요)")
    print(url)
    webbrowser.open(url)
    server_thread.join()

    if _result.get("error"):
        raise SystemExit(f"인증 실패: {_result['error']}")
    if _result.get("state") != state:
        raise SystemExit("state 값이 일치하지 않습니다 (보안 검증 실패). 다시 시도해주세요.")

    print(f"[디버그] code_verifier   = {code_verifier}")
    print(f"[디버그] code_challenge  = {code_challenge}")
    print(f"[디버그] 수신된 code     = {_result['code']!r}")

    token_resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": settings.TIKTOK_CLIENT_KEY,
            "client_secret": settings.TIKTOK_CLIENT_SECRET,
            "code": _result["code"],
            "grant_type": "authorization_code",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()

    if "access_token" not in token_data:
        # 틱톡은 실패 시에도 HTTP 200과 함께 {"error": ...} 형태로 응답하는 경우가 있다.
        raise SystemExit(f"토큰 발급 실패: {token_data}")

    settings.TIKTOK_TOKEN_FILE.write_text(json.dumps(token_data, ensure_ascii=False, indent=2))
    print(f"저장 완료: {settings.TIKTOK_TOKEN_FILE}")


if __name__ == "__main__":
    main()
