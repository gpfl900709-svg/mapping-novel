from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SECRET_KEY_RE = re.compile(
    r"(authorization|access[_-]?token|refresh[_-]?token|api[_-]?token|password|passwd|cookie|secret|api[_-]?key|jwt)",
    re.IGNORECASE,
)
SECRET_VALUE_RES = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bpk_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
    re.compile(r"\bAT[A-Z0-9]{8,}_[A-Za-z0-9_-]{16,}\b"),
)
REDACTED = "[REDACTED]"


def redact_string(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_RES:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact_secrets(payload: Any, *, parent_key: str = "") -> Any:
    if isinstance(payload, dict):
        result: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                result[key] = REDACTED
            else:
                result[key] = redact_secrets(value, parent_key=key_text)
        return result
    if isinstance(payload, list):
        return [redact_secrets(value, parent_key=parent_key) for value in payload]
    if isinstance(payload, str):
        if SECRET_KEY_RE.search(parent_key):
            return REDACTED
        return redact_string(payload)
    return payload


def dumps_redacted(payload: Any, **kwargs: Any) -> str:
    options = {"ensure_ascii": False, "indent": 2}
    options.update(kwargs)
    return json.dumps(redact_secrets(payload), **options)


def write_json_redacted(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps_redacted(payload), encoding="utf-8")
    return target
