"""데몬과 대시보드가 공유하는 런타임 설정(LLM On/Off).

data/runtime_config.json 파일에 저장하여, 대시보드에서 토글하면 데몬이 다음 처리 시
즉시 반영되도록 한다.
"""

import json

from config import settings


def _read() -> dict:
    if settings.RUNTIME_CONFIG_PATH.exists():
        try:
            return json.loads(settings.RUNTIME_CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _write(data: dict) -> None:
    settings.RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings.RUNTIME_CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_llm_on() -> bool:
    return _read().get("llm_on", settings.LLM_ON)


def set_llm_on(value: bool) -> None:
    data = _read()
    data["llm_on"] = bool(value)
    _write(data)
