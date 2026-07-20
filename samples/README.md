# 업로드용 JSON 메타데이터 작성 가이드

## 기본 규칙
- `Upload_Queue` 폴더에 **영상(.mp4)과 JSON(.json)을 같은 이름으로 한 쌍** 넣습니다.
  - 예: `cooking01.mp4` + `cooking01.json`
- 두 파일이 모두 준비되면 데몬이 자동으로 업로드를 시작합니다.
- (확장자 대소문자는 `.mp4`/`.MP4` 모두 인식합니다.)

## JSON 필드

| 필드 | 설명 | 사용 플랫폼 |
|------|------|------------|
| `title` | 제목 | YouTube, TikTok |
| `description` | 설명문 (인스타에서는 캡션으로 사용) | YouTube, Instagram |
| `hashtags` | 해시태그 배열 (예: `["#요리", "#레시피"]`) | YouTube, TikTok, Instagram |
| `privacy_status` | (선택) 공개 범위 — 아래 "공개 범위" 참고 | YouTube, TikTok |

## LLM 자동 생성은 어떻게 동작하나
- **전역 스위치**: 대시보드(`streamlit run dashboard.py`)의 "LLM 메타데이터 자동 생성" 토글로 켜고 끕니다. JSON에 LLM 관련 키를 넣을 필요는 없습니다.
- **빈 칸만 채웁니다** (토글이 켜져 있을 때):
  - `description`이 비어 있으면(`""`) → LLM이 `title`을 보고 설명문 생성
  - `hashtags`가 비어 있으면(`[]`) → LLM이 해시태그 생성
  - 이미 값이 있으면 그대로 두고 LLM을 건너뜁니다.
- **필드별로 독립적**입니다. 예를 들어 설명은 직접 쓰고 해시태그만 LLM에 맡기려면 `description`은 채우고 `hashtags`는 `[]`로 두세요.
- 토글이 꺼져 있으면 JSON에 적힌 값을 그대로만 사용합니다.

## 예시 파일
- `example.json` — 메타데이터를 직접 다 채운 경우 (LLM 미개입)
- `example_autofill.json` — `description`/`hashtags`를 비워 LLM이 채우게 하는 경우

## 공개 범위 (privacy_status)
안전을 위해 기본값은 **비공개**입니다. 생략하면:
- YouTube → `private` (비공개)
- TikTok → `SELF_ONLY` (나만 보기)
- Instagram → API 특성상 **항상 즉시 공개 게시** (비공개 옵션 없음)

공개로 올리려면 플랫폼별로 값 체계가 달라 주의가 필요합니다:
- YouTube 값: `public`, `unlisted`, `private`
- TikTok 값: `PUBLIC_TO_EVERYONE`, `MUTUAL_FOLLOW_FRIENDS`, `SELF_ONLY`
  - (단, TikTok은 앱 심사 승인 전에는 무엇을 넣어도 비공개로만 게시됩니다.)

> 하나의 `privacy_status` 값을 두 플랫폼이 공유하기 때문에, 지금은 한 번에 한쪽 체계에 맞는 값만 넣을 수 있습니다.
> 플랫폼별로 공개 범위를 따로 지정하고 싶으면 알려주세요 — `visibility: "public" | "private"` 같은 통합 키로 개선해 드리겠습니다.
