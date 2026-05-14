from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def stable_sha256(value: Any) -> str:
    return f"sha256:{hashlib.sha256(stable_json_dumps(value).encode('utf-8')).hexdigest()}"


def short_hash(value: str, length: int = 12) -> str:
    return value.replace("sha256:", "")[:length]
