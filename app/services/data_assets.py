from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings
from app.services.file_inspection import inspect_file


def new_data_asset_id() -> str:
    return uuid4().hex


def store_uploaded_data_asset_files(
    *,
    project_id: str,
    asset_id: str,
    asset_type: str,
    files: list[UploadFile],
    parent_id: str | None = None,
    preparation_params_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not files:
        raise ValueError("At least one file is required")

    base_dir = _asset_base_dir(project_id, asset_type, asset_id)
    files_dir = base_dir / "files"
    base_dir.mkdir(parents=True, exist_ok=False)
    files_dir.mkdir(parents=True, exist_ok=True)

    manifest = _new_manifest(
        asset_id=asset_id,
        asset_type=asset_type,
        parent_id=parent_id,
        project_id=project_id,
        preparation_params_json=preparation_params_json,
    )

    try:
        _append_uploads(files_dir, manifest, files)
        manifest_hash = write_current_manifest(base_dir, manifest)
        return {
            "manifest_hash": manifest_hash,
            "manifest_json": manifest,
            "storage_path": str(base_dir),
        }
    except Exception:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        raise
    finally:
        _close_uploads(files)


def append_uploaded_data_asset_files(
    *,
    storage_path: str,
    current_manifest: dict[str, Any],
    files: list[UploadFile],
) -> dict[str, Any]:
    if not files:
        raise ValueError("At least one file is required")

    base_dir = Path(storage_path)
    files_dir = base_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(json.dumps(current_manifest))
    try:
        _append_uploads(files_dir, manifest, files)
        manifest_hash = write_current_manifest(base_dir, manifest)
        return {"manifest_hash": manifest_hash, "manifest_json": manifest}
    finally:
        _close_uploads(files)


def store_generated_data_asset_files(
    *,
    project_id: str,
    asset_id: str,
    asset_type: str,
    generated_files: list[dict[str, Any]],
    parent_id: str | None = None,
    preparation_params_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not generated_files:
        raise ValueError("At least one generated file is required")

    base_dir = _asset_base_dir(project_id, asset_type, asset_id)
    files_dir = base_dir / "files"
    base_dir.mkdir(parents=True, exist_ok=False)
    files_dir.mkdir(parents=True, exist_ok=True)

    manifest = _new_manifest(
        asset_id=asset_id,
        asset_type=asset_type,
        parent_id=parent_id,
        project_id=project_id,
        preparation_params_json=preparation_params_json,
    )

    try:
        manifest_files = manifest["files"]
        for index, generated in enumerate(generated_files, start=1):
            original_name = str(generated["original_name"])
            content = generated["content"]
            content_type = generated.get("content_type")
            suffix = _safe_suffix(original_name)
            stored_name = f"f_{index:06d}{suffix}"
            target_path = files_dir / stored_name
            target_path.write_bytes(content)
            manifest_entry = {
                "content_type": content_type,
                "inspection": inspect_file(
                    target_path,
                    content_type=content_type,
                    original_name=original_name,
                ),
                "original_name": original_name,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "stored_path": f"files/{stored_name}",
            }
            if generated.get("role"):
                manifest_entry["role"] = generated["role"]
            if generated.get("source"):
                manifest_entry["source"] = generated["source"]
            manifest_files.append(manifest_entry)

        manifest_hash = write_current_manifest(base_dir, manifest)
        return {
            "manifest_hash": manifest_hash,
            "manifest_json": manifest,
            "storage_path": str(base_dir),
        }
    except Exception:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        raise


def delete_data_asset_file(
    *,
    storage_path: str,
    current_manifest: dict[str, Any],
    stored_path: str,
) -> dict[str, Any]:
    base_dir = Path(storage_path)
    manifest = json.loads(json.dumps(current_manifest))
    files = manifest.get("files", [])
    if not isinstance(files, list):
        raise ValueError("Manifest files must be a list")

    file_entry = next((item for item in files if item.get("stored_path") == stored_path), None)
    if file_entry is None:
        raise ValueError("File not found in current manifest")

    target_path = base_dir / stored_path
    if target_path.exists():
        target_path.unlink()

    manifest["files"] = [item for item in files if item.get("stored_path") != stored_path]
    manifest_hash = write_current_manifest(base_dir, manifest)
    return {"manifest_hash": manifest_hash, "manifest_json": manifest}


def resolve_manifest_file_path(
    *,
    storage_path: str,
    current_manifest: dict[str, Any],
    stored_path: str,
) -> tuple[Path, dict[str, Any]]:
    files = current_manifest.get("files", [])
    if not isinstance(files, list):
        raise ValueError("Manifest files must be a list")

    file_entry = next((item for item in files if item.get("stored_path") == stored_path), None)
    if file_entry is None:
        raise ValueError("File not found in current manifest")

    path = Path(storage_path) / stored_path
    if not path.exists():
        raise ValueError("File is missing from storage")
    return path, file_entry


def write_current_manifest(base_dir: Path, manifest: dict[str, Any]) -> str:
    hash_manifest = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    manifest_json = json.dumps(hash_manifest, sort_keys=True, separators=(",", ":"))
    manifest_hash = f"sha256:{hashlib.sha256(manifest_json.encode('utf-8')).hexdigest()}"
    manifest["manifest_hash"] = manifest_hash
    manifest_path = base_dir / "_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_hash


def _asset_base_dir(project_id: str, asset_type: str, asset_id: str) -> Path:
    storage_type = "source" if asset_type == "raw" else "prepared"
    return get_settings().data_dir / "projects" / project_id / storage_type / asset_id


def _new_manifest(
    *,
    asset_id: str,
    asset_type: str,
    parent_id: str | None,
    project_id: str,
    preparation_params_json: dict[str, Any] | None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "files": [],
        "project_id": project_id,
    }
    if preparation_params_json is not None:
        manifest["preparation_params_json"] = preparation_params_json
    if parent_id is not None:
        manifest["parent_id"] = parent_id
    return manifest


def _append_uploads(files_dir: Path, manifest: dict[str, Any], files: list[UploadFile]) -> None:
    manifest_files = manifest.setdefault("files", [])
    if not isinstance(manifest_files, list):
        raise ValueError("Manifest files must be a list")

    next_index = len(manifest_files) + 1
    for upload in files:
        original_name = upload.filename or "uploaded_file"
        suffix = _safe_suffix(original_name)
        stored_name = f"f_{next_index:06d}{suffix}"
        while (files_dir / stored_name).exists():
            next_index += 1
            stored_name = f"f_{next_index:06d}{suffix}"
        stored_path = f"files/{stored_name}"
        target_path = files_dir / stored_name

        file_hash = hashlib.sha256()
        size = 0
        with target_path.open("wb") as output:
            while chunk := upload.file.read(1024 * 1024):
                size += len(chunk)
                file_hash.update(chunk)
                output.write(chunk)

        manifest_files.append(
            {
                "content_type": upload.content_type,
                "inspection": inspect_file(
                    target_path,
                    content_type=upload.content_type,
                    original_name=original_name,
                ),
                "original_name": original_name,
                "sha256": file_hash.hexdigest(),
                "size_bytes": size,
                "stored_path": stored_path,
            }
        )
        next_index += 1


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if len(suffix) > 16 or any(char in suffix for char in ("/", "\\", ":", "\x00")):
        return ""
    return suffix


def _close_uploads(files: list[UploadFile]) -> None:
    for upload in files:
        upload.file.close()
