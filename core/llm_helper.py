"""JSON 메타데이터를 파싱하고, LLM_ON 설정에 따라 빈 description/hashtags를 채운다."""

import json
import logging
from pathlib import Path

from anthropic import Anthropic

from config import settings
from core import runtime_config

logger = logging.getLogger(__name__)

_client = None

PROMPT_TEMPLATE = """다음은 숏폼 영상(유튜브 쇼츠/인스타 릴스/틱톡)의 제목이야: "{title}"

이 영상에 어울리는 설명문과 해시태그를 만들어줘.
다른 설명 없이 아래 JSON 형식으로만 응답해:
{{"description": "...", "hashtags": ["...", "..."]}}
"""


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _parse_json_response(raw_text: str) -> dict:
    # 모델이 지시를 무시하고 ```json 코드블록으로 감싸는 경우가 있어 방어적으로 처리한다.
    text = raw_text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    return json.loads(text)


def _generate_metadata(title: str) -> dict:
    client = _get_client()
    message = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(title=title)}],
    )
    return _parse_json_response(message.content[0].text)


def enrich_metadata(json_path: Path) -> dict:
    """json_path의 메타데이터를 읽어 필요 시 LLM으로 보완하고, 파일에 다시 저장한 뒤 반환한다."""
    with open(json_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    needs_description = not metadata.get("description")
    needs_hashtags = not metadata.get("hashtags")

    if not runtime_config.get_llm_on():
        logger.info("LLM Off, 원본 메타데이터 그대로 사용: %s", json_path.name)
        return metadata

    if not (needs_description or needs_hashtags):
        logger.info("메타데이터 이미 채워짐, LLM 호출 생략: %s", json_path.name)
        return metadata

    logger.info("LLM 메타데이터 보완 호출 중 (%s): %s", settings.LLM_MODEL, json_path.name)
    generated = _generate_metadata(metadata.get("title", ""))

    if needs_description:
        metadata["description"] = generated.get("description", "")
    if needs_hashtags:
        metadata["hashtags"] = generated.get("hashtags", [])

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata
