# 프로젝트 명: 숏폼 멀티 플랫폼 자동 업로드 에이전트 (Short-form Auto Uploader)

## 1. 프로젝트 개요 및 목표
- **목적:** 특정 로컬(NAS) 폴더에 영상(mp4)과 메타데이터(json)를 넣으면 유튜브 쇼츠, 인스타그램 릴스, 틱톡에 비동기적으로 동시 업로드되는 에이전트 구축.
- **핵심 요구사항:**
  - 서드파티 자동화 툴 없이 Mac Mini 로컬 환경에서 독립적인 백그라운드 프로세스(Daemon)로 동작할 것.
  - 플랫폼별 **공식 API**를 사용하여 장기적인 안정성을 확보할 것.
  - 업로드가 완료된 파일은 로컬 스토리지 확보를 위해 NAS의 지정된 아카이브 폴더로 자동 이동할 것.
  - **LLM On/Off 제어:** 메타데이터 자동 생성(LLM) 기능은 전역 설정에 따라 원할 때만 작동하도록 토글(Toggle) 기능 구현.

## 2. 작업 환경 및 VS Code 초기 세팅 가이드
- **작업 경로:** `/Volumes/01_Main_Workspace/10_Projects/12_Dev_Personal/Shortform_Auto`
- **실행 환경:** Mac Mini에 마운트된 16TB NAS 경로를 VS Code에서 직접 열어 작업 진행.
- **터미널 실행 명령어:** 
  ```bash
  code /Volumes/01_Main_Workspace/10_Projects/12_Dev_Personal/Shortform_Auto
  ```
- **가상환경(venv) 참고:** I/O 위주의 작업이므로 우선 NAS 폴더 내부에 `venv`를 세팅하여 진행하되, 라이브러리 로드 속도가 저하될 경우 가상환경 폴더만 Mac Mini 로컬(`~/`)로 분리하는 방안 고려.

## 3. 폴더 및 파일 구조 (Directory Structure)
프로젝트 루트 폴더 하위에 다음과 같은 모듈화 구조를 구성합니다.

```text
Shortform_Auto/
├── main.py                        # (1) 백그라운드 데몬 실행 파일 (Watchdog 실행)
├── dashboard.py                   # (2) Streamlit 관리자 화면 실행 파일
├── core/                          # (3) 핵심 로직 폴더
│   ├── __init__.py
│   ├── monitor.py                 # 폴더 감시 및 이벤트 트리거 로직
│   ├── llm_helper.py              # OpenAI/Claude API 호출 (메타데이터 자동완성)
│   └── uploader.py                # YouTube, Instagram, TikTok 비동기 업로드 로직
├── config/                        # (4) 설정 폴더
│   ├── settings.py                # LLM On/Off 기본값, 경로 등 전역 변수
│   └── .env                       # 각종 API 키 보관 (★절대 외부 노출 금지)
├── data/                          # (5) 로컬 데이터베이스
│   └── upload_logs.db             # 업로드 성공/실패 기록 (SQLite)
├── Upload_Queue/                  # (6) 🚀 감시 대상 폴더 (여기에 mp4, json을 넣음)
├── Uploaded_Archive/              # (7) 📦 업로드 완료 후 이동될 아카이브 폴더
├── requirements.txt               # 파이썬 라이브러리 목록
└── Shortform_Auto_Uploader_Spec.md # 현재 기획 문서
```

## 4. 기술 스택 (Tech Stack)
- **Language:** Python 3.10+
- **Core Engine (백그라운드 데몬):**
  - `watchdog`: 파일 시스템 감시 및 이벤트 트리거
  - `asyncio` / `aiohttp`: 다중 플랫폼 비동기 동시 업로드 처리
  - `openai` or `anthropic`: 메타데이터(설명, 해시태그) LLM 보완 기능
- **API 연동:**
  - `google-api-python-client`: YouTube Data API v3 
  - `requests`: Instagram Graph API, TikTok Content Posting API
- **Dashboard (모니터링 & 제어):** `Streamlit`

## 5. 핵심 워크플로우 (Workflow)
1. **모니터링:** `Upload_Queue` 폴더를 감시하며 `.mp4`와 동일한 이름의 `.json` 파일이 한 쌍으로 준비될 때 트리거 작동.
2. **검증 및 LLM 연동 (Metadata Enrichment - On/Off 가능):**
   - Streamlit 대시보드의 'LLM 자동 생성 옵션'이 활성화(On)되어 있고, JSON의 `description`이나 `hashtags`가 비어있을 경우에만 LLM API를 호출.
   - LLM 옵션이 비활성화(Off)되어 있다면, JSON 파일에 입력된 텍스트만 그대로 사용하여 다음 단계로 넘어감.
3. **비동기 멀티 업로드 (Async Upload):** 3개 플랫폼 공식 API를 통해 영상과 메타데이터를 비동기로 동시 전송.
4. **후처리 및 로깅 (Post-processing):**
   - 성공 시 영상을 `Uploaded_Archive` 폴더로 이동하여 대기열 정리.
   - 업로드 결과 및 에러 내역은 로컬 DB(SQLite)에 기록하여 Streamlit 대시보드에서 실시간 확인 가능하도록 구성.

## 6. AI 어시스턴트를 위한 개발 단계별 프롬프트 가이드 (Step-by-Step)
이 문서를 읽고 있는 AI는 다음 Step에 따라 순차적으로 코드를 작성하고 설명해 주세요.
- **Step 1:** 주어진 폴더 구조를 생성하고, `watchdog`을 이용해 `Upload_Queue` 폴더를 감시하여 `.mp4`와 `.json` 쌍이 확인되었을 때만 이벤트를 발생시키는 `main.py` 및 `core/monitor.py` 뼈대 스크립트 작성.
- **Step 2:** `core/llm_helper.py`를 작성하여 JSON 데이터를 파싱하고, 상태 변수(LLM_ON=True/False)에 따라 빈 메타데이터를 LLM API로 채우거나 건너뛰는 조건부 로직 구현.
- **Step 3:** `core/uploader.py`에 각 플랫폼(YouTube, Instagram, TikTok) 공식 API 연동 모듈을 분리하고, `asyncio` 기반의 비동기 멀티 업로드 로직 작성.
- **Step 4:** 파일 업로드 성공 여부에 따라 `Uploaded_Archive`로 파일을 이동시키고 SQLite에 로그를 남기는 후처리 로직 구현.
- **Step 5:** DB 로그를 읽어와 업로드 상태를 보여주고, **LLM On/Off 토글 버튼**이 포함된 `dashboard.py` (Streamlit UI) 코드 작성.
