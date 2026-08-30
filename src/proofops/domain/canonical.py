from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any


def _default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return value.__dict__
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        default=_default,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_hex(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def redact_secrets(value: Any) -> Any:
    sensitive = {"private_key", "api_key", "authorization", "token", "secret", "password"}
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key.lower() in sensitive else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value
