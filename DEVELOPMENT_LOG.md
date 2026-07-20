# 개발 기록 (Development Log)

숏폼 자동 업로드 에이전트를 기획서 한 장에서 시작해 3개 플랫폼 실제 업로드까지 완성한 하루의 기록.
작업 방식, 주요 결정, 시행착오(특히 삽질 포인트)를 남겨 나중에 확장하거나 비슷한 작업을 할 때 참고하기 위함.

작업일: 2026-07-20 ~ 07-21

---

## 작업 방식 (전반적인 접근)

- **한 단계씩 만들고 즉시 실제로 검증**하는 방식으로 진행. 코드를 몰아서 쓰지 않고, 각 Step마다 실제 실행/테스트로 동작을 확인한 뒤 다음으로 넘어감.
- **외부 인증·심사가 필요한 작업은 병렬화**. 인스타/틱톡 개발자 등록·심사는 시간이 걸리므로 먼저 신청해두고, 그 사이에 코드를 진행.
- **공식 문서를 실시간으로 확인**하며 엔드포인트/파라미터를 맞춤. 기억에 의존하지 않고, API가 문서와 다르게 동작할 때마다 문서를 다시 뒤져 원인을 잡음.
- **위험한 기본값은 안전하게**. 실수로 공개 게시되지 않도록 업로드 기본 공개범위를 비공개(private/SELF_ONLY)로.
- **비밀정보는 커밋 금지**. `.env`, 토큰 파일은 처음부터 `.gitignore`에 넣고, 커밋 전 `git check-ignore`로 확인.

---

## 단계별 진행

### Step 1 — 폴더 구조 + 폴더 감시
- `watchdog`으로 `Upload_Queue`를 감시. `.mp4`와 같은 이름의 `.json`이 **쌍으로** 준비될 때만 트리거.
- **삽질 방지 포인트**: NAS로 큰 파일을 복사하는 도중 이벤트가 발생하면 부분 파일을 업로드할 위험 → 파일 크기가 안정될 때까지 대기하는 로직(`_is_file_stable`) 추가.
- 더미 mp4+json을 실제로 넣어 감지 → 안정화 대기 → 콜백 실행까지 확인.

### Step 2 — LLM 메타데이터 보완
- 모델 선택: 설명문·해시태그 생성은 정형 작업이라 **가성비 티어로 충분** → Claude Haiku 4.5.
- 구독(ChatGPT/Claude/Gemini)과 API는 별개 과금이라는 점 확인. 허깅페이스 로컬 모델은 이 볼륨에선 비용 이점이 없고 운영 복잡도만 늘어 제외.
- `LLM_ON` + "빈 필드만 채움" + "필드별 독립" 조건부 로직 구현. 실제 API 호출로 3가지 분기(생성 / LLM Off 스킵 / 이미 채워짐 스킵) 모두 검증.

### Step 3 — 플랫폼 업로더 (가장 오래 걸린 구간)

#### YouTube
- Google Cloud OAuth 데스크톱 앱. `authorize_youtube.py`로 1회 브라우저 인증 → refresh token 저장.
- **삽질**: OAuth 동의 화면에 계정을 "테스트 사용자"로 등록하지 않으면 `403 access_denied`. 등록 후 해결.
- 실제 비공개 업로드 성공 확인. (Studio에 안 보여서 당황했지만 비공개 영상은 링크로만 확인되는 정상 동작이었음.)

#### TikTok (삽질 최다)
- Content Posting API + Login Kit. 앱 심사 필요.
- **도메인/URL 소유권 인증**: ToS·Privacy를 GitHub Pages(`docs/`)로 호스팅하고, TikTok이 요구하는 인증 파일(`tiktok{code}.txt`)을 각 URL 접두사(`/`, `/tos/`, `/privacy/`)마다 배치.
- **삽질 1 — PKCE**: TikTok은 RFC 표준(base64url)이 아니라 **SHA256의 hex 인코딩**을 `code_challenge`로 요구. 표준 방식으로는 계속 `Code verifier or code challenge is invalid`. 공식 데스크톱 문서에서 "hex encoding of SHA256"을 발견해 해결.
- **삽질 2 — 개발자 계정 ≠ 실사용 계정**: 개발자 포털 로그인 계정으로는 로그인 불가. 실제 TikTok 사용자 계정을 별도로 만들고 Sandbox의 Target User로 등록해야 함.
- **삽질 3 — 미심사 앱 제약**: `unaudited_client_can_only_post_to_private_accounts`. 앱 심사 전에는 **TikTok 계정 자체를 비공개**로 바꿔야 게시 가능.
- 위 3개를 넘긴 뒤 실제 업로드 성공. 데모 영상 녹화해서 심사 제출까지 완료(승인 대기).

#### Instagram (구조적 갈림길)
- **핵심 발견**: 인스타 API는 두 방식이 있고 파일 업로드 방식이 다름.
  - **Instagram Login** (`graph.instagram.com`, IGAA 토큰): 페이지 불필요하지만 **공개 URL(video_url) 필수** → 로컬 파일 직접 업로드 불가.
  - **Facebook Login** (`graph.facebook.com`, EAA 토큰): **로컬 파일 직접 업로드 가능**(유튜브/틱톡과 동일). 단 인스타 계정이 Facebook 페이지에 연결돼야 함.
- 우리 파이프라인(NAS 로컬 파일)에는 Facebook Login이 맞아 그쪽으로 전환.
- **삽질 1 — 토큰 종류**: 처음 받은 게 IGAA(Instagram Login) 토큰이라 교환 엔드포인트가 안 맞았음. 방식을 Facebook Login으로 통일.
- **삽질 2 — Facebook 페이지 없음**: `me/accounts`가 비어 있어 진단. 인스타를 붙일 **Facebook 페이지가 아예 없었음** → 페이지(노마디디) 생성 후 인스타 계정 연결.
- **삽질 3 — 앱 자격증명**: 장기 토큰 교환 시 `.env`에 인스타 앱 ID/시크릿이 들어 있어 실패(코드 101). **메인 Facebook 앱**의 ID/시크릿으로 교체해야 했음.
- 연결 후 페이지 직접 조회로 `instagram_business_account` 확인 → 실제 릴스 업로드 성공 → 60일 장기 토큰 발급(만료 7일 전 자동 갱신 로직 포함).

### 추가 — NAS 대응 + 자동 실행(launchd)
"항상 켜둔 Mac Mini + 외부에서 파일만 던지면 자동 업로드" 시나리오를 위해 데몬을 LaunchAgent로 상시 가동하려다 macOS 특유의 벽을 두 개 만남.

- **삽질 1 — watchdog + NAS**: 기본 Observer(FSEvents)는 네트워크 마운트(NAS)에서 파일 생성 이벤트를 놓침. `PollingObserver`(주기적 폴링)로 바꿔 해결. 파일시스템 종류에 무관하게 동작.
- **삽질 2 — launchd 하에서 로그가 안 보임**: launchd가 stdout/stderr를 파일로 리다이렉트하면 블록 버퍼링됨. `python -u`(언버퍼드)로 즉시 flush.
- **삽질 3 — TCC가 백그라운드 NAS 접근 차단 (핵심)**: launchd 에이전트로 데몬을 띄우면 프로세스는 살아있는데 로그도 없고 파일도 감지 못 함. 스택을 떠보니(`sample`) `import` 중 NAS 파일 `open()`에서 멈춰 있었음. 단순 `ls`만 하는 에이전트로 격리 테스트하니 `Operation not permitted`(EPERM) → **macOS TCC가 백그라운드 프로세스의 네트워크 볼륨 접근을 차단**하는 것. 터미널/직접 실행은 이미 권한이 있어 됨. 해결: Python 실행 파일에 **전체 디스크 접근 권한(Full Disk Access)** 부여 (사용자 GUI 1회 작업).
- **삽질 4 — `~/Library/LaunchAgents`가 root 소유**: 일반 사용자로 설치 불가 → `sudo chown`으로 소유권 복구 필요.
- **검증 방식**: 데몬+파이프라인 자체는 수동 실행(`ENABLED_PLATFORMS="" python -u main.py`)으로 감지→처리→아카이브 이동까지 실제 확인(업로드는 비활성화해 실게시 방지). launchd 자동 실행의 최종 확인은 위 GUI/sudo 사전조건 충족 후 진행.

### Step 4~5 — 파이프라인 통합 + 대시보드
- `core/pipeline.py`: 메타데이터 보완 → `asyncio.gather`로 3개 플랫폼 동시 업로드(`return_exceptions=True`로 한 곳 실패가 전체를 막지 않음) → SQLite 로깅 → 전체 성공은 `Uploaded_Archive`, 일부 실패는 `Failed_Uploads`로 이동.
- LLM On/Off는 데몬과 대시보드가 `data/runtime_config.json`으로 공유(대시보드에서 토글하면 다음 처리부터 반영).
- **테스트 안전장치**: 개별 업로드는 이미 실제 검증했으므로, 파이프라인 배선 테스트는 업로드 함수를 **모킹**해서 계정에 재게시 없이 로깅·파일 이동·실패 분류만 검증.
- 대시보드는 headless로 실제 부팅(HTTP 200)까지 확인.

---

## 주요 결정 로그

| 결정 | 이유 |
|------|------|
| LLM = Claude Haiku 4.5 | 정형 작업엔 가성비 티어로 충분, 볼륨상 비용 미미 |
| 로컬 모델(허깅페이스) 미채택 | 비용 이점 거의 없음 + 운영 복잡도/품질 손해 |
| Instagram = Facebook Login 방식 | 로컬 파일 직접 업로드 지원(공개 URL 호스팅 불필요) |
| 업로드 기본 비공개 | 실수 공개 방지 |
| 실패해도 다른 플랫폼 계속 | 한 곳 장애가 전체를 막지 않도록 |
| Threads 제외 | 텍스트 위주라 영상 파이프라인과 콘텐츠 모델이 상이 |

---

## 앞으로 확장할 만한 아이디어

- **실행 간소화**: 데몬 + 대시보드 2개 프로세스를 하나로. Streamlit에 감시 스레드를 넣거나 "지금 업로드" 버튼 추가.
- **venv 로컬 분리**: 라이브러리 로딩이 느리면 venv만 Mac 로컬(`~/`)로 옮기는 방안 (기획서에서 이미 언급). 단, 데몬은 어차피 NAS 접근이 필요하므로 TCC(Full Disk Access) 문제는 별개.
- **공개 범위 통합 키**: `visibility: public|private`를 플랫폼별 값으로 매핑.
- **실패 자동 재시도**: `Failed_Uploads` 항목을 재시도하거나, 성공한 플랫폼은 건너뛰고 실패분만 재업로드.
- **예약 업로드**: 특정 시각에 게시.
- **Mac 부팅 시 자동 실행**: launchd 등록으로 데몬 상시 가동.
- **Threads 별도 모듈**: 영상+짧은 캡션 첨부 방식으로 나중에 추가.
- **알림**: 업로드 성공/실패를 Slack·이메일 등으로 통지.
