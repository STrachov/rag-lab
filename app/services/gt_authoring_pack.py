from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.db import models
from app.services.hashing import stable_json_dumps


TEXT_SUFFIXES = {".json", ".md", ".markdown", ".txt"}


def build_gt_authoring_pack(
    *,
    chunks_cache: models.DerivedCache,
    data_asset: models.DataAsset,
    manifest_json: dict,
) -> bytes:
    metadata = chunks_cache.metadata_json
    chunks_path = Path(str(metadata["chunks_path"]))
    manifest_path = Path(str(metadata["manifest_path"]))
    if not chunks_path.exists() or not manifest_path.exists():
        raise ValueError("Chunks cache files are missing")

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(_pack_manifest(chunks_cache, data_asset), indent=2, sort_keys=True))
        archive.write(chunks_path, "chunks.jsonl")
        archive.write(manifest_path, "chunks_manifest.json")
        archive.writestr("ground_truth.schema.json", json.dumps(_ground_truth_schema(), indent=2, sort_keys=True))
        archive.writestr("ground_truth.template.jsonl", stable_json_dumps(_ground_truth_template()) + "\n")
        archive.writestr("instructions.md", _instructions())
        _write_prepared_files(archive, data_asset, manifest_json)
    return buffer.getvalue()


def _pack_manifest(chunks_cache: models.DerivedCache, data_asset: models.DataAsset) -> dict:
    metadata = chunks_cache.metadata_json
    return {
        "chunks_cache_id": chunks_cache.id,
        "chunks_cache_key": chunks_cache.cache_key,
        "chunking": metadata.get("chunking"),
        "created_at": datetime.now(UTC).isoformat(),
        "data_asset_id": data_asset.id,
        "data_asset_manifest_hash": data_asset.manifest_hash,
        "data_asset_name": data_asset.name,
        "prepared_files_dir": "prepared_text",
        "project_id": chunks_cache.project_id,
        "schema_version": "raglab.gt_authoring_pack.v1",
    }


def _write_prepared_files(archive: ZipFile, data_asset: models.DataAsset, manifest_json: dict) -> None:
    if data_asset.storage_path is None:
        return
    base_dir = Path(data_asset.storage_path)
    used_names: set[str] = set()
    for file_entry in manifest_json.get("files", []):
        stored_path = file_entry.get("stored_path")
        if not isinstance(stored_path, str):
            continue
        path = base_dir / stored_path
        if not path.exists() or not _is_text_file(path, file_entry):
            continue
        original_name = _safe_archive_name(str(file_entry.get("original_name") or path.name))
        archive_name = _unique_name(f"prepared_text/{original_name}", used_names)
        archive.write(path, archive_name)


def _is_text_file(path: Path, file_entry: dict) -> bool:
    content_type = str(file_entry.get("content_type") or "")
    if content_type.startswith("text/") or content_type in {"application/json", "application/x-ndjson"}:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def _safe_archive_name(filename: str) -> str:
    name = Path(filename).name.strip() or "prepared_file"
    return re.sub(r"[^A-Za-z0-9._ -]+", "_", name)


def _unique_name(name: str, used_names: set[str]) -> str:
    if name not in used_names:
        used_names.add(name)
        return name
    directory, _, filename = name.rpartition("/")
    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem = filename
        suffix = ""
    for index in range(2, 10_000):
        candidate_filename = f"{stem}_{index}.{suffix}" if suffix else f"{stem}_{index}"
        candidate = f"{directory}/{candidate_filename}" if directory else candidate_filename
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
    raise ValueError("Too many duplicate prepared filenames")


def _ground_truth_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": False,
        "properties": {
            "acceptable_answer_patterns": {"items": {"type": "string"}, "type": "array"},
            "answer_type": {
                "enum": [
                    "factual",
                    "multi_hop",
                    "comparison",
                    "definition",
                    "table_lookup",
                    "negative_not_found",
                    "summary",
                    "policy_interpretation",
                ],
                "type": "string",
            },
            "difficulty": {"enum": ["easy", "medium", "hard"], "type": "string"},
            "expected_chunks": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "heading_path": {"items": {"type": "string"}, "type": "array"},
                        "page": {"type": ["integer", "null"]},
                        "relevance": {"enum": ["primary", "supporting"], "type": "string"},
                        "source_name": {"type": "string"},
                    },
                    "required": ["chunk_id", "source_name", "relevance"],
                    "type": "object",
                },
                "type": "array",
            },
            "expected_facts": {"items": {"type": "string"}, "type": "array"},
            "expected_sources": {
                "items": {
                    "additionalProperties": False,
                    "properties": {
                        "heading_path": {"items": {"type": "string"}, "type": "array"},
                        "page": {"type": ["integer", "null"]},
                        "source_name": {"type": "string"},
                    },
                    "required": ["source_name"],
                    "type": "object",
                },
                "type": "array",
            },
            "not_found": {"type": "boolean"},
            "notes": {"type": "string"},
            "question": {"type": "string"},
            "question_id": {"type": "string"},
            "schema_version": {"const": "raglab.ground_truth.v1"},
        },
        "required": [
            "schema_version",
            "question_id",
            "question",
            "answer_type",
            "expected_chunks",
            "expected_sources",
            "expected_facts",
            "not_found",
        ],
        "type": "object",
    }


def _ground_truth_template() -> dict:
    return {
        "acceptable_answer_patterns": [],
        "answer_type": "factual",
        "difficulty": "easy",
        "expected_chunks": [
            {
                "chunk_id": "chunk_000001",
                "heading_path": [],
                "page": None,
                "relevance": "primary",
                "source_name": "example.md",
            }
        ],
        "expected_facts": ["Replace with a fact supported by the selected chunk."],
        "expected_sources": [
            {
                "heading_path": [],
                "page": None,
                "source_name": "example.md",
            }
        ],
        "not_found": False,
        "notes": "",
        "question": "Replace with an evaluation question.",
        "question_id": "q_001",
        "schema_version": "raglab.ground_truth.v1",
    }


def _instructions() -> str:
    return """# Ground Truth Authoring Pack

Use `prepared_text/` and `chunks.jsonl` to create `ground_truth.jsonl`.

Rules:

- Write one JSON object per line.
- Use `ground_truth.schema.json` as the output contract.
- Prefer questions that can be answered from one or more listed chunks.
- Reference chunks by `chunk_id` and `source_name`.
- Use `not_found: true` only when the prepared text does not contain supporting evidence.
- Do not invent facts that are not supported by the prepared text.
- Keep `expected_facts` short and atomic.

Suggested prompt:

```text
Using the prepared text and chunks in this pack, create a ground_truth.jsonl file that follows ground_truth.schema.json. Include factual questions, a few harder multi-hop questions when justified, and a few negative_not_found questions. Use only chunk ids from chunks.jsonl.
```
"""
