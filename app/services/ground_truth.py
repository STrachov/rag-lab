from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import get_settings
from app.db import models
from app.services.hashing import stable_json_dumps, stable_sha256


GT_SCHEMA_VERSION = "raglab.chunk_qrels.v1"
GT_SET_SCHEMA_VERSION = "raglab.ground_truth_set.v1"


def new_ground_truth_set_id() -> str:
    return models.new_id()


def store_uploaded_ground_truth_set(
    *,
    file: UploadFile,
    ground_truth_set_id: str,
    data_asset: models.DataAsset | None,
    project_id: str,
) -> dict[str, Any]:
    base_dir = _ground_truth_base_dir(project_id, ground_truth_set_id)
    original_dir = base_dir / "original"
    base_dir.mkdir(parents=True, exist_ok=False)
    original_dir.mkdir(parents=True, exist_ok=True)

    try:
        original_name = file.filename or "ground_truth.json"
        original_path = original_dir / _safe_filename(original_name)
        content = file.file.read()
        if not content:
            raise ValueError("Ground truth file cannot be empty")
        original_path.write_bytes(content)

        parsed = _parse_json_or_jsonl(content)
        canonical = _canonicalize_ground_truth(parsed)
        validation = _validate_ground_truth(canonical)
        canonical_path = base_dir / "ground_truth.json"
        canonical_path.write_text(
            json.dumps(canonical, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        manifest = _build_manifest(
            canonical=canonical,
            content=content,
            content_type=file.content_type,
            data_asset=data_asset,
            ground_truth_set_id=ground_truth_set_id,
            original_name=original_name,
            original_path=original_path,
            project_id=project_id,
            validation=validation,
        )
        manifest_hash = stable_sha256(manifest)
        manifest["manifest_hash"] = manifest_hash
        (base_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        (base_dir / "validation.json").write_text(
            json.dumps(validation, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "manifest_hash": manifest_hash,
            "metadata_json": _metadata_from_manifest(manifest),
            "storage_path": str(canonical_path),
        }
    except Exception:
        if base_dir.exists():
            shutil.rmtree(base_dir)
        raise
    finally:
        file.file.close()


def _ground_truth_base_dir(project_id: str, ground_truth_set_id: str) -> Path:
    return get_settings().data_dir / "ground_truth" / project_id / "ground_truths" / ground_truth_set_id


def _parse_json_or_jsonl(content: bytes) -> Any:
    text = content.decode("utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        records: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ground truth file must be valid JSON or JSONL; invalid line {line_number}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Ground truth JSONL line {line_number} must be an object")
            records.append(value)
        if not records:
            raise ValueError("Ground truth file contains no records")
        return records


def _canonicalize_ground_truth(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("questions"), list):
        metadata = dict(value.get("metadata") or {})
        questions = [_canonical_question_from_qrels(item) for item in value["questions"]]
    elif isinstance(value, list):
        metadata = {"ground_truth_type": "chunk_level_qrels"}
        questions = [_canonical_question_from_authoring_record(item) for item in value]
    else:
        raise ValueError("Ground truth must be a JSON object with questions[] or JSONL records")

    question_ids = [question["question_id"] for question in questions]
    duplicate_ids = sorted({item for item in question_ids if question_ids.count(item) > 1})
    if duplicate_ids:
        raise ValueError(f"Duplicate ground truth question ids: {', '.join(duplicate_ids)}")
    if not questions:
        raise ValueError("Ground truth must include at least one question")

    return {
        "metadata": metadata,
        "questions": questions,
        "schema_version": GT_SCHEMA_VERSION,
    }


def _canonical_question_from_qrels(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Each ground truth question must be an object")
    question_id = _required_str(value, "question_id")
    question_text = _required_str(value, "question")
    expected_answer_type = str(value.get("expected_answer_type") or "found")
    relevant_chunks = [
        _canonical_relevant_chunk(item, fallback_rank=index)
        for index, item in enumerate(value.get("relevant_chunks") or [], start=1)
    ]
    if expected_answer_type == "not_found" and relevant_chunks:
        raise ValueError(f"{question_id}: not_found questions cannot include relevant_chunks")
    if expected_answer_type != "not_found" and not relevant_chunks:
        raise ValueError(f"{question_id}: found questions must include at least one relevant chunk")
    return {
        "expected_answer_brief": value.get("expected_answer_brief"),
        "expected_answer_type": expected_answer_type,
        "question": question_text,
        "question_id": question_id,
        "question_type": str(value.get("question_type") or "factual"),
        "relevant_chunks": relevant_chunks,
    }


def _canonical_question_from_authoring_record(value: dict[str, Any]) -> dict[str, Any]:
    question_id = _required_str(value, "question_id")
    not_found = bool(value.get("not_found"))
    expected_chunks = value.get("expected_chunks") or []
    relevant_chunks = [
        {
            "chunk_id": _required_str(item, "chunk_id"),
            "rank": index,
            "reason": None,
            "relevance": 3 if item.get("relevance") == "primary" else 2,
        }
        for index, item in enumerate(expected_chunks, start=1)
        if isinstance(item, dict)
    ]
    if not_found and relevant_chunks:
        raise ValueError(f"{question_id}: not_found records cannot include expected_chunks")
    if not not_found and not relevant_chunks:
        raise ValueError(f"{question_id}: records must include expected_chunks unless not_found is true")
    return {
        "expected_answer_brief": None,
        "expected_answer_type": "not_found" if not_found else "found",
        "question": _required_str(value, "question"),
        "question_id": question_id,
        "question_type": str(value.get("answer_type") or "factual"),
        "relevant_chunks": relevant_chunks,
    }


def _canonical_relevant_chunk(value: Any, *, fallback_rank: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Relevant chunk entries must be objects")
    relevance = int(value.get("relevance", 1))
    if relevance < 1 or relevance > 3:
        raise ValueError("Relevant chunk relevance must be 1, 2, or 3")
    return {
        "chunk_id": _required_str(value, "chunk_id"),
        "rank": int(value.get("rank") or fallback_rank),
        "reason": value.get("reason"),
        "relevance": relevance,
    }


def _validate_ground_truth(
    canonical: dict[str, Any],
) -> dict[str, Any]:
    relevant_chunk_ids = {
        str(chunk["chunk_id"])
        for question in canonical["questions"]
        for chunk in question["relevant_chunks"]
    }
    warnings = ["Chunk id compatibility is checked later against the retrieval chunks cache."]
    chunks_file_sha256 = canonical.get("metadata", {}).get("chunks_file_sha256")

    return {
        "declared_chunks_file_sha256": chunks_file_sha256,
        "referenced_chunk_count": len(relevant_chunk_ids),
        "status": "unvalidated",
        "warnings": warnings,
    }


def _build_manifest(
    *,
    canonical: dict[str, Any],
    content: bytes,
    content_type: str | None,
    data_asset: models.DataAsset | None,
    ground_truth_set_id: str,
    original_name: str,
    original_path: Path,
    project_id: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    questions = canonical["questions"]
    found_questions = [item for item in questions if item["expected_answer_type"] != "not_found"]
    not_found_questions = [item for item in questions if item["expected_answer_type"] == "not_found"]
    judgment_count = sum(len(question["relevant_chunks"]) for question in questions)
    return {
        "canonical_format": GT_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "data_asset_id": data_asset.id if data_asset else None,
        "found_count": len(found_questions),
        "ground_truth_set_id": ground_truth_set_id,
        "ground_truth_type": str(canonical["metadata"].get("ground_truth_type") or "chunk_level_qrels"),
        "not_found_count": len(not_found_questions),
        "original": {
            "content_type": content_type,
            "original_name": original_name,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "stored_path": str(original_path.relative_to(original_path.parents[1])),
        },
        "project_id": project_id,
        "question_count": len(questions),
        "relevance_judgment_count": judgment_count,
        "schema_version": GT_SET_SCHEMA_VERSION,
        "source_metadata": canonical["metadata"],
        "storage": {
            "canonical_path": "ground_truth.json",
            "manifest_path": "manifest.json",
            "validation_path": "validation.json",
        },
        "validation": validation,
        "chunks_file_sha256": canonical["metadata"].get("chunks_file_sha256"),
    }


def _metadata_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "canonical_format": manifest["canonical_format"],
        "chunks_file_sha256": manifest.get("chunks_file_sha256"),
        "found_count": manifest["found_count"],
        "ground_truth_type": manifest["ground_truth_type"],
        "not_found_count": manifest["not_found_count"],
        "original_filename": manifest["original"]["original_name"],
        "question_count": manifest["question_count"],
        "relevance_judgment_count": manifest["relevance_judgment_count"],
        "schema_version": manifest["schema_version"],
        "validation": manifest["validation"],
    }


def _required_str(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"Ground truth field {key} is required")
    return item.strip()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "ground_truth.json"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name[:180] or "ground_truth.json"
