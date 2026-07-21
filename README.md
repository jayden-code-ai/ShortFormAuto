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
├── main.py                  # 백그라운드 데몬 (Upload_Queue 감시 → 업로드 + 토큰 자동 갱신)
├── dashboard.py             # Streamlit 대시보드 (업로드 생성 · 로그 · 성과 · 재시도)
├── authorize_youtube.py     # YouTube OAuth 1회 인증 스크립트
├── authorize_tiktok.py      # TikTok OAuth 1회 인증 스크립트
├── authorize_instagram.py   # Instagram 장기 토큰 발급 스크립트
├── core/
│   ├── monitor.py           # 폴더 감시 + mp4/json 쌍 감지
│   ├── llm_helper.py         # Claude API로 빈 메타데이터 보완
│   ├── uploader.py           # 플랫폼별 업로드 (+ asyncio 비동기 래퍼)
│   ├── pipeline.py           # 전체 처리 오케스트레이션 + 실패 재시도
│   ├── queue_writer.py       # 대시보드 입력 → mp4/json 쌍을 큐에 안전 배치
│   ├── metrics.py            # 업로드 영상의 조회수/좋아요/댓글 조회
│   ├── status.py             # 데몬·대기열·토큰 상태 조회 (대시보드 상태 바)
│   ├── database.py           # SQLite 업로드 로그 + 성과 지표
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
├── .streamlit/
│   ├── config.toml           # 업로드 용량 상향 등 Streamlit 설정
│   └── secrets.toml          # 대시보드 접속 암호 (git 제외)
└── deploy/                   # LaunchAgent plist(데몬·대시보드) + 설치/제거 스크립트
    └── 대시보드 열기.app      # 클릭하면 대시보드를 켜고 브라우저를 여는 앱
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

평소에는 **데몬과 대시보드 모두 LaunchAgent로 자동 실행**되므로 터미널을 열 필요가 없습니다
(아래 "자동 실행 설정" 참고). 수동으로 띄우려면:

```bash
# 1) 백그라운드 데몬 (폴더 감시 + 자동 업로드)
source venv/bin/activate && python main.py

# 2) 대시보드 (별도 터미널)
source venv/bin/activate && streamlit run dashboard.py
```

### 대시보드 여는 방법
- `deploy/대시보드 열기.app` 을 **Dock이나 응용 프로그램 폴더에 두고 클릭** — 꺼져 있으면 자동으로 켜고 브라우저를 엽니다
- 또는 브라우저 북마크: `http://localhost:8501`

### 접속 암호
대시보드는 LAN·외부에서도 접근 가능하므로 암호로 잠겨 있습니다.
`.streamlit/secrets.toml` 의 `dashboard_password` 값을 바꾸면 암호가 변경됩니다 (이 파일은 git에서 제외됨).
값을 비우거나 파일을 지우면 잠금이 해제됩니다(로컬 전용으로만 쓸 때).

업로드를 시작하는 방법은 두 가지입니다.

**① 대시보드에서 만들기 (권장)** — `➕ 업로드 만들기` 탭에서 영상을 올리고 제목·설명·해시태그를 입력하면
mp4와 json을 **같은 이름으로 자동 생성**해 대기열에 넣습니다. 파일명을 직접 맞출 필요가 없어 실수가 없고,
`✨ LLM으로 초안 생성` 버튼으로 설명·해시태그를 자동 작성한 뒤 고칠 수도 있습니다.

**② 파일을 직접 넣기** — `Upload_Queue`에 **같은 이름의 mp4 + json**을 넣으면 자동으로 업로드됩니다.
(JSON 형식은 [samples/README.md](samples/README.md) 참고)

### 대시보드 구성
| 탭 | 내용 |
|----|------|
| ➕ 업로드 만들기 | 영상 업로드 + 메타데이터 입력/LLM 초안 → 대기열 배치 |
| 📊 대시보드 | 성공/실패 요약, 최근 로그(링크·실패 사유 펼쳐보기) |
| 📅 업로드 내역 | 기간 필터 + 일자별 그룹/그래프 |
| 📈 성과 | 영상별 조회수·좋아요·댓글 (YouTube/Instagram) |
| 🔁 실패 재시도 | `Failed_Uploads` 목록, 실패한 플랫폼만 재업로드 |

상단 상태 바에는 데몬 가동 여부, 대기열 현황, 플랫폼 토큰 유효성이 표시되며 주기적으로 자동 갱신됩니다.

---

## 자동 실행 설정 (launchd, 항상 켜진 Mac 권장)

Mac을 항상 켜두고 외부에서 NAS에 파일만 던져 자동 업로드하려면, 데몬을 LaunchAgent로 등록합니다.
(부팅/로그인 시 자동 시작 + 크래시 자동 재시작. 대시보드는 필요할 때만 별도로 실행.)

데몬(업로드 처리)과 대시보드(Streamlit) 두 개를 LaunchAgent로 등록합니다.

```bash
bash deploy/install_launchagent.sh            # 둘 다 설치 + 즉시 기동
bash deploy/install_launchagent.sh daemon     # 데몬만
bash deploy/install_launchagent.sh dashboard  # 대시보드만

launchctl list | grep shortformauto           # 상태 확인
tail -f ~/Library/Logs/shortformauto.err.log            # 데몬 로그
tail -f ~/Library/Logs/shortformauto.dashboard.err.log  # 대시보드 로그

bash deploy/uninstall_launchagent.sh          # 제거
```

> ⚠️ plist에서 **스크립트(`venv/bin/streamlit`)를 직접 실행하면 안 됩니다.** launchd가 스크립트를
> 실행하면 전체 디스크 접근 권한이 적용되지 않아 `pyvenv.cfg` 읽기부터 `Operation not permitted`로
> 실패합니다. 권한이 부여된 python 바이너리로 `-m streamlit` 을 호출해야 합니다(저장소 plist에 반영됨).

### ⚠️ 필수 사전 조건 3가지 (macOS 제약)
1. **`~/Library/LaunchAgents` 쓰기 권한** — 이 폴더가 root 소유이면 설치가 실패합니다. 아래로 되돌리세요:
   ```bash
   sudo chown $(whoami):staff ~/Library/LaunchAgents && chmod 755 ~/Library/LaunchAgents
   ```
2. **Python에 전체 디스크 접근 권한(Full Disk Access)** — launchd 백그라운드 프로세스는 기본적으로
   NAS(네트워크 볼륨) 접근이 TCC로 차단됩니다(`Operation not permitted`). 아래 앱을 허용 목록에 추가하세요:
   - **시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 권한** → `+` →
     `Cmd+Shift+G`로 `/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app` 이동 → 추가 → 토글 ON
   - 추가 후 데몬 재시작: `launchctl kickstart -k gui/$(id -u)/com.shortformauto.daemon`
3. **plist의 `ProcessType`은 반드시 `Standard`** — `Background`로 두면 launchd가 강한 I/O 스로틀링을
   걸어, NAS에서 모듈 import가 사실상 진행되지 않습니다(측정: `Background` 4분+ 미완료 → `Standard` 약 75초).
   저장소의 plist에는 이미 반영되어 있습니다.

> 이 조건들을 만족하지 않으면 데몬은 떠 있어도 NAS 파일을 감지/처리하지 못합니다.
> (터미널에서 `python main.py`를 직접 실행하는 경우엔 터미널이 이미 권한을 가지므로 정상 동작합니다.)

### 증상별 진단 요령
프로세스는 살아있는데 로그도 없고 반응도 없다면, **권한 문제로 단정하기 전에** 아래로 구분하세요.
- `lsof -p <PID>` — NAS 파일이 열려 있으면 차단이 아니라 **느린 것**입니다(스로틀링 의심).
- `sample <PID>` — 특정 `open()`에서 멈춰 있으면 권한(TCC), `stat`/`close`에 시간이 분산되면 I/O 스로틀링입니다.
- 권한 거부(EPERM)는 즉시 실패로 나타나고, 스로틀링은 무한 대기처럼 보입니다.

---

## 외부(집 밖)에서 접근하기

대시보드는 **데몬과 같은 기계에서 실행되어야** 합니다. NAS의 `Upload_Queue`에 파일을 쓰고,
로그 DB를 읽고, 데몬 프로세스 상태를 확인하기 때문입니다. 따라서 Streamlit Cloud 같은 곳에는 배포할 수 없습니다.
대신 **집 네트워크에 안전하게 들어오는 방식**으로 외부에서 사용합니다.

| 범위 | 접속 주소 |
|------|-----------|
| 맥미니 본체 | `http://localhost:8501` |
| 같은 와이파이 (폰·노트북) | `http://<맥미니 LAN IP>:8501` |
| 집 밖 | Tailscale 연결 후 `http://<맥미니 Tailscale IP>:8501` |

### Tailscale 설정 (권장)
포트포워딩 없이 기기끼리 암호화된 사설망을 만듭니다. 공유기 설정을 건드리지 않아 안전합니다.

1. 맥미니에 설치: `brew install --cask tailscale` (또는 [tailscale.com/download](https://tailscale.com/download))
2. 실행 후 로그인 → 맥미니가 tailnet에 등록됨
3. 아이폰/노트북에도 Tailscale 앱 설치 후 **같은 계정으로** 로그인
4. 맥미니의 Tailscale IP 확인: `tailscale ip -4`
5. 외부에서 `http://<그 IP>:8501` 로 접속

> **하지 말아야 할 것**: 공유기 포트포워딩으로 8501을 인터넷에 직접 여는 방식.
> Streamlit 로그에 표시되는 `External URL`은 포트포워딩이 되어 있을 때만 동작하는 주소이며,
> 그 상태는 인증이 뚫리면 곧바로 계정 탈취로 이어지므로 권장하지 않습니다.

---

## 동작 흐름

1. **감시** — `Upload_Queue`에서 `이름.mp4` + `이름.json` 쌍이 준비되면 트리거 (NAS 복사 완료까지 파일 크기 안정화 대기). NAS에서 이벤트를 안정적으로 받기 위해 `PollingObserver`(주기적 폴링) 사용. 확장자·파일명의 대소문자는 구분하지 않습니다.
2. **메타데이터 보완** — LLM 토글이 켜져 있고 `description`/`hashtags`가 비어 있으면 Claude가 생성
3. **비동기 멀티 업로드** — 활성 플랫폼에 동시 전송 (한 곳이 실패해도 나머지는 계속 진행)
4. **후처리** — 결과를 SQLite에 기록, 전체 성공 시 `Uploaded_Archive`로, 일부 실패 시 `Failed_Uploads`로 이동

데몬은 6시간마다 인스타그램 장기 토큰(60일)의 만료를 점검해, 만료 7일 전이면 자동 갱신합니다.
따라서 한동안 업로드가 없어도 토큰이 만료되지 않습니다.

---

## 플랫폼별 참고사항

- **YouTube**: 기본 공개범위 `private`. OAuth 동의 화면이 **"테스트 중"이면 refresh token이 7일마다 만료**되므로,
  계속 쓰려면 **프로덕션으로 게시**해야 합니다. 성과 지표(조회수/댓글)에는 `youtube.readonly` 스코프가 필요하며,
  스코프를 바꾼 뒤에는 `python authorize_youtube.py`로 재인증해야 합니다.
- **TikTok**: PKCE는 표준(base64url)이 아니라 **SHA256 hex** 인코딩 사용. 앱 심사 승인 전에는 **비공개 계정에만 비공개 게시**만 가능.
- **Instagram**: **Facebook Login 방식** 사용 (로컬 파일 직접 업로드 지원). 인스타 계정이 Facebook 페이지에 연결된 프로페셔널 계정이어야 함. **API상 항상 즉시 공개 게시** (비공개 옵션 없음).

---

## 알려진 제한 / 확장 여지

- `privacy_status`가 YouTube/TikTok 간 값 체계가 달라, 지금은 한쪽 기준 값만 넣을 수 있음 → `visibility: public|private` 통합 키로 개선 여지
- Threads는 콘텐츠 성격이 달라(텍스트 위주) 현재 범위에서 제외
- 데몬과 대시보드가 별도 프로세스 → 단일 프로세스/실행 버튼으로 간소화 여지
- **TikTok 성과 지표 미지원** — `video.list` 스코프가 필요하나 앱 심사 중이라 보류. 또한 저장되는 값은
  `publish_id`(게시 요청 ID)라 영상 ID와 매핑하려면 해당 스코프가 필요함
- **Instagram 조회수 미지원** — `instagram_manage_insights` 권한이 없어 좋아요·댓글수만 조회 가능
- 실패 재시도는 대시보드에서 **수동 실행** (자동 재시도는 없음)
- 영상 내용 기반 자동 제목 생성 없음 → 프레임 추출 + 비전 모델로 확장 여지

> 오늘 처음부터 완성까지의 개발 과정과 시행착오는 [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md)에 정리되어 있습니다.
