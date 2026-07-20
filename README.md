# Shortform Auto Uploader (숏폼 멀티 플랫폼 자동 업로드 에이전트)

로컬(NAS) 폴더에 영상(mp4)과 메타데이터(json)를 넣으면 **YouTube 쇼츠 · Instagram 릴스 · TikTok**에
공식 API로 **비동기 동시 업로드**하는 개인용 백그라운드 에이전트입니다.

- 서드파티 자동화 툴 없이 Mac Mini 로컬에서 독립 데몬으로 동작
- 플랫폼별 **공식 API**만 사용 (장기 안정성)
- 업로드 완료 파일은 아카이브 폴더로 자동 이동
- 메타데이터(설명·해시태그) 자동 생성(LLM)은 전역 토글로 On/Off

---

## 폴더 구조

```
Shortform_Auto/
├── main.py                  # 백그라운드 데몬 (Upload_Queue 감시 → 업로드)
├── dashboard.py             # Streamlit 관리자 대시보드 (로그 조회 + LLM 토글)
├── authorize_youtube.py     # YouTube OAuth 1회 인증 스크립트
├── authorize_tiktok.py      # TikTok OAuth 1회 인증 스크립트
├── authorize_instagram.py   # Instagram 장기 토큰 발급 스크립트
├── core/
│   ├── monitor.py           # 폴더 감시 + mp4/json 쌍 감지
│   ├── llm_helper.py         # Claude API로 빈 메타데이터 보완
│   ├── uploader.py           # 플랫폼별 업로드 (+ asyncio 비동기 래퍼)
│   ├── pipeline.py           # 전체 처리 오케스트레이션
│   ├── database.py           # SQLite 업로드 로그
│   └── runtime_config.py     # 데몬-대시보드 공유 설정(LLM On/Off)
├── config/
│   ├── settings.py           # 경로·플랫폼·모델 등 전역 설정
│   ├── .env                  # API 키/토큰 (git 제외)
│   └── .env.example          # .env 템플릿
├── data/                     # SQLite DB, 런타임 설정 (git 제외)
├── Upload_Queue/             # 🚀 감시 대상 (여기에 mp4+json 투입)
├── Uploaded_Archive/         # 📦 전체 성공 시 이동
├── Failed_Uploads/           # ⚠️ 일부 실패 시 이동
├── samples/                  # JSON 메타데이터 템플릿 + 작성 가이드
└── deploy/                   # launchd LaunchAgent plist + 설치/제거 스크립트
```

---

## 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### API 키 설정
`config/.env.example`를 `config/.env`로 복사한 뒤 값을 채웁니다.

| 키 | 발급처 |
|----|--------|
| `ANTHROPIC_API_KEY` | console.anthropic.com (LLM 메타데이터 생성용) |
| `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` | Google Cloud Console (OAuth 데스크톱 앱) |
| `TIKTOK_CLIENT_KEY` / `TIKTOK_CLIENT_SECRET` | TikTok for Developers |
| `INSTAGRAM_APP_ID` / `INSTAGRAM_APP_SECRET` | Meta 앱 (메인 Facebook 앱 자격증명) |
| `INSTAGRAM_ACCESS_TOKEN` | Graph API Explorer에서 발급한 사용자 토큰 |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | 연결된 페이지의 instagram_business_account id |

### 플랫폼별 1회 인증
```bash
python authorize_youtube.py     # 브라우저 로그인 → config/youtube_token.json 생성
python authorize_tiktok.py      # 브라우저 로그인 → config/tiktok_token.json 생성
python authorize_instagram.py   # 단기 토큰 → 장기 토큰 교환 → config/instagram_token.json 생성
```

---

## 실행

```bash
# 1) 백그라운드 데몬 (폴더 감시 + 자동 업로드)
source venv/bin/activate && python main.py

# 2) 대시보드 (별도 터미널, 모니터링 + LLM 토글)
source venv/bin/activate && streamlit run dashboard.py
```

데몬이 실행 중일 때 `Upload_Queue`에 **같은 이름의 mp4 + json**을 넣으면 자동으로 업로드됩니다.
(자세한 JSON 형식은 [samples/README.md](samples/README.md) 참고)

---

## 자동 실행 설정 (launchd, 항상 켜진 Mac 권장)

Mac을 항상 켜두고 외부에서 NAS에 파일만 던져 자동 업로드하려면, 데몬을 LaunchAgent로 등록합니다.
(부팅/로그인 시 자동 시작 + 크래시 자동 재시작. 대시보드는 필요할 때만 별도로 실행.)

```bash
bash deploy/install_launchagent.sh          # 설치 + 즉시 기동
launchctl print gui/$(id -u)/com.shortformauto.daemon | grep state   # 상태 확인
tail -f ~/Library/Logs/shortformauto.err.log # 데몬 로그
bash deploy/uninstall_launchagent.sh         # 제거
```

### ⚠️ 필수 사전 조건 2가지 (macOS 제약)
1. **`~/Library/LaunchAgents` 쓰기 권한** — 이 폴더가 root 소유이면 설치가 실패합니다. 아래로 되돌리세요:
   ```bash
   sudo chown $(whoami):staff ~/Library/LaunchAgents && chmod 755 ~/Library/LaunchAgents
   ```
2. **Python에 전체 디스크 접근 권한(Full Disk Access)** — launchd 백그라운드 프로세스는 기본적으로
   NAS(네트워크 볼륨) 접근이 TCC로 차단됩니다(`Operation not permitted`). 아래 앱을 허용 목록에 추가하세요:
   - **시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한** → `+` →
     `Cmd+Shift+G`로 `/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app` 이동 → 추가 → 토글 ON
   - 추가 후 데몬 재시작: `launchctl kickstart -k gui/$(id -u)/com.shortformauto.daemon`

> 이 두 조건을 만족하지 않으면 데몬은 떠 있어도 NAS 파일을 감지/처리하지 못합니다.
> (터미널에서 `python main.py`를 직접 실행하는 경우엔 터미널이 이미 권한을 가지므로 정상 동작합니다.)

---

## 동작 흐름

1. **감시** — `Upload_Queue`에서 `이름.mp4` + `이름.json` 쌍이 준비되면 트리거 (NAS 복사 완료까지 파일 크기 안정화 대기). NAS에서 이벤트를 안정적으로 받기 위해 `PollingObserver`(주기적 폴링) 사용.
2. **메타데이터 보완** — LLM 토글이 켜져 있고 `description`/`hashtags`가 비어 있으면 Claude가 생성
3. **비동기 멀티 업로드** — 활성 플랫폼에 동시 전송 (한 곳이 실패해도 나머지는 계속 진행)
4. **후처리** — 결과를 SQLite에 기록, 전체 성공 시 `Uploaded_Archive`로, 일부 실패 시 `Failed_Uploads`로 이동

---

## 플랫폼별 참고사항

- **YouTube**: OAuth 테스트 사용자 등록 필요. 기본 공개범위 `private`.
- **TikTok**: PKCE는 표준(base64url)이 아니라 **SHA256 hex** 인코딩 사용. 앱 심사 승인 전에는 **비공개 계정에만 비공개 게시**만 가능.
- **Instagram**: **Facebook Login 방식** 사용 (로컬 파일 직접 업로드 지원). 인스타 계정이 Facebook 페이지에 연결된 프로페셔널 계정이어야 함. **API상 항상 즉시 공개 게시** (비공개 옵션 없음).

---

## 알려진 제한 / 확장 여지

- `privacy_status`가 YouTube/TikTok 간 값 체계가 달라, 지금은 한쪽 기준 값만 넣을 수 있음 → `visibility: public|private` 통합 키로 개선 여지
- Threads는 콘텐츠 성격이 달라(텍스트 위주) 현재 범위에서 제외
- 데몬과 대시보드가 별도 프로세스 → 단일 프로세스/실행 버튼으로 간소화 여지
- 실패 항목 자동 재시도 없음 (수동으로 `Failed_Uploads`에서 다시 넣어야 함)

> 오늘 처음부터 완성까지의 개발 과정과 시행착오는 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)에 정리되어 있습니다.
