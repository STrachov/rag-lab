from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


def new_data_asset_id() -> str:
    return uuid4().hex


def store_uploaded_data_asset_files(
    *,
    project_id: str,
    asset_id: str,
    asset_type: str,
    files: list[UploadFile],
) -> dict[str, Any]:
    if not files:
        raise ValueError("At least one file is required")

    base_dir = get_settings().data_dir / "projects" / project_id / asset_type / asset_id
    base_dir.mkdir(parents=True, exist_ok=False)

    manifest_entries: list[dict[str, Any]] = []
    total_bytes = 0

    try:
        for upload in files:
            relative_path = _safe_relative_path(upload.filename or "uploaded_file")
            target_path = base_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            file_hash = hashlib.sha256()
            size = 0
            with target_path.open("wb") as output:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    file_hash.update(chunk)
                    output.write(chunk)

            manifest_entries.append(
                {
                    "path": relative_path.as_posix(),
                    "size_bytes": size,
                    "sha256": file_hash.hexdigest(),
                }
            )
            total_bytes += size
        manifest_entries.sort(key=lambda item: item["path"])

        manifest = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "file_count": len(manifest_entries),
            "files": manifest_entries,
            "project_id": project_id,
            "total_bytes": total_bytes,
        }
        manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        manifest_hash = f"sha256:{hashlib.sha256(manifest_json.encode('utf-8')).hexdigest()}"
        manifest_path = base_dir / "_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

        return {
            "file_count": len(manifest_entries),
            "manifest_hash": manifest_hash,
            "manifest_path": str(manifest_path),
            "storage_path": str(base_dir),
            "total_bytes": total_bytes,
        }
    except Exception:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        raise
    finally:
        for upload in files:
            upload.file.close()


def _safe_relative_path(filename: str) -> PurePosixPath:
    normalized = filename.replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"Unsafe upload filename: {filename}")
    return PurePosixPath(*parts)
