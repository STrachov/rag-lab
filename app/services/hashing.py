from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def stable_sha256(value: Any) -> str:
    return f"sha256:{hashlib.sha256(stable_json_dumps(value).encode('utf-8')).hexdigest()}"


def short_hash(value: str, length: int = 12) -> str:
    return value.replace("sha256:", "")[:length]


def bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def read_verified_bytes(path: str | Path, expected_hash: str, label: str) -> bytes:
    if not expected_hash:
        raise ValueError(f"{label} has no content hash; rebuild or re-import it")
    try:
        content = Path(path).read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} file is unavailable") from exc
    if bytes_sha256(content) != expected_hash:
        raise ValueError(f"{label} content hash mismatch; rebuild or re-import it")
    return content
