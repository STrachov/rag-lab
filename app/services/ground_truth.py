from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.core.config import get_settings
from app.db import models
from app.services.hashing import stable_json_dumps, stable_sha256


GT_SCHEMA_VERSION = "raglab.ground_truth.v1"
LEGACY_GT_SCHEMA_VERSION = "raglab.chunk_qrels.v1"
GT_SET_SCHEMA_VERSION = "raglab.ground_truth_set.v1"
GT_TYPE_CHUNK_QRELS = "chunk_level_qrels"
GT_TYPE_PAGE_QRELS = "page_level_qrels"


def new_ground_truth_set_id() -> str:
    return models.new_id()


def list_ground_truth_questions(ground_truth_set: models.GroundTruthSet) -> list[dict[str, Any]]:
    canonical = read_canonical_ground_truth(ground_truth_set)
    questions = []
    for question in canonical["questions"]:
        questions.append(
            {
                "expected_answer_type": question["expected_answer_type"],
                "question": question["question"],
                "question_id": question["question_id"],
                "question_type": question["question_type"],
                "relevant_chunk_count": len(question["relevant_chunks"]),
                "relevant_page_count": len(question.get("relevant_pages") or []),
                "relevant_pages": question.get("relevant_pages") or [],
            }
        )
    return questions


def score_ground_truth_ranking(
    *,
    ground_truth_set: models.GroundTruthSet,
    index_cache: models.DerivedCache | None,
    k: int,
    question_id: str,
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical = read_canonical_ground_truth(ground_truth_set)
    question = next(
        (item for item in canonical["questions"] if item["question_id"] == question_id),
        None,
    )
    if question is None:
        raise ValueError("Ground truth question not found")

    ground_truth_type = _ground_truth_type(canonical)
    warnings = _ranking_warnings(canonical, index_cache)
    top_chunks = retrieved_chunks[:k]
    if question["expected_answer_type"] == "not_found":
        top_score = _top_score(top_chunks)
        return {
            "expected_answer_type": "not_found",
            "k": k,
            "metrics": {
                "expected_not_found": 1.0,
                "returned_count": float(len(top_chunks)),
                "top_score": top_score if top_score is not None else 0.0,
            },
            "question_id": question_id,
            "warnings": warnings,
        }

    if ground_truth_type == GT_TYPE_PAGE_QRELS:
        return _score_page_ground_truth_question(
            k=k,
            question=question,
            retrieved_chunks=top_chunks,
            warnings=warnings,
        )

    relevance_by_chunk_id = {
        str(chunk["chunk_id"]): int(chunk["relevance"])
        for chunk in question["relevant_chunks"]
    }
    retrieved_ids = [str(chunk.get("chunk_id")) for chunk in top_chunks if chunk.get("chunk_id")]
    found_relevant_ids = [chunk_id for chunk_id in retrieved_ids if chunk_id in relevance_by_chunk_id]
    first_relevant_rank = next(
        (rank for rank, chunk_id in enumerate(retrieved_ids, start=1) if chunk_id in relevance_by_chunk_id),
        None,
    )
    relevant_count = len(relevance_by_chunk_id)
    dcg = sum(
        _dcg_gain(relevance_by_chunk_id.get(chunk_id, 0), rank)
        for rank, chunk_id in enumerate(retrieved_ids, start=1)
    )
    ideal_relevances = sorted(relevance_by_chunk_id.values(), reverse=True)[:k]
    idcg = sum(_dcg_gain(relevance, rank) for rank, relevance in enumerate(ideal_relevances, start=1))
    return {
        "expected_answer_type": "found",
        "k": k,
        "metrics": {
            "hit_at_k": 1.0 if found_relevant_ids else 0.0,
            "mrr_at_k": (1.0 / first_relevant_rank) if first_relevant_rank else 0.0,
            "ndcg_at_k": (dcg / idcg) if idcg else 0.0,
            "precision_at_k": len(found_relevant_ids) / k if k else 0.0,
            "recall_at_k": len(set(found_relevant_ids)) / relevant_count if relevant_count else 0.0,
        },
        "question_id": question_id,
        "warnings": warnings,
    }


def read_canonical_ground_truth(ground_truth_set: models.GroundTruthSet) -> dict[str, Any]:
    if ground_truth_set.storage_path is None:
        raise ValueError("Ground truth set has no storage path")
    path = Path(ground_truth_set.storage_path)
    if not path.exists():
        raise ValueError("Ground truth canonical file is missing")
    try:
        canonical = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Ground truth canonical file is invalid") from exc
    if canonical.get("schema_version") not in {
        GT_SCHEMA_VERSION,
        LEGACY_GT_SCHEMA_VERSION,
    } or not isinstance(canonical.get("questions"), list):
        raise ValueError("Ground truth canonical file has an unsupported format")
    return canonical


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
    if isinstance(value, dict) and _looks_like_page_ground_truth_records(value.get("questions")):
        metadata = {
            **dict(value.get("metadata") or {}),
            "ground_truth_type": GT_TYPE_PAGE_QRELS,
            "source_format": str(value.get("source_format") or "rag_challenge_answers"),
        }
        questions = [
            _canonical_question_from_page_answer(item, fallback_index=index)
            for index, item in enumerate(value["questions"], start=1)
        ]
    elif isinstance(value, dict) and _looks_like_page_ground_truth_records(value.get("answers")):
        metadata = {
            **dict(value.get("metadata") or {}),
            "ground_truth_type": GT_TYPE_PAGE_QRELS,
            "source_format": str(value.get("source_format") or "rag_challenge_answers"),
        }
        questions = [
            _canonical_question_from_page_answer(item, fallback_index=index)
            for index, item in enumerate(value["answers"], start=1)
        ]
    elif isinstance(value, dict) and isinstance(value.get("questions"), list):
        metadata = dict(value.get("metadata") or {})
        metadata["ground_truth_type"] = str(metadata.get("ground_truth_type") or GT_TYPE_CHUNK_QRELS)
        questions = [_canonical_question_from_qrels(item) for item in value["questions"]]
    elif isinstance(value, list):
        metadata = {"ground_truth_type": GT_TYPE_CHUNK_QRELS}
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
        "relevant_pages": [],
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
        "relevant_pages": [],
        "relevant_chunks": relevant_chunks,
    }


def _canonical_question_from_page_answer(value: Any, *, fallback_index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Each page-level ground truth question must be an object")
    question_id = str(value.get("question_id") or f"q{fallback_index:06d}").strip()
    if not question_id:
        raise ValueError("Page-level ground truth question_id cannot be empty")
    references = value.get("references") or []
    if not isinstance(references, list):
        raise ValueError(f"{question_id}: references must be a list")
    relevant_pages = [
        _canonical_relevant_page(item)
        for item in references
        if isinstance(item, dict)
    ]
    expected_answer_type = "found" if relevant_pages else "not_found"
    return {
        "expected_answer": value.get("value"),
        "expected_answer_brief": None if value.get("value") is None else str(value.get("value")),
        "expected_answer_type": expected_answer_type,
        "question": _required_str(value, "question_text"),
        "question_id": question_id,
        "question_type": str(value.get("kind") or "factual"),
        "reasoning_process": value.get("reasoning_process"),
        "relevant_chunks": [],
        "relevant_pages": relevant_pages,
    }


def _canonical_relevant_page(value: dict[str, Any]) -> dict[str, Any]:
    pdf_sha1 = _required_str(value, "pdf_sha1")
    page_index = value.get("page_index")
    if not isinstance(page_index, int) or page_index < 0:
        raise ValueError("Page-level ground truth references require non-negative integer page_index")
    return {"page_index": page_index, "pdf_sha1": pdf_sha1}


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
    chunks_file_sha256 = canonical.get("metadata", {}).get("chunks_file_sha256")
    relevant_page_keys = {
        (str(page["pdf_sha1"]), int(page["page_index"]))
        for question in canonical["questions"]
        for page in question.get("relevant_pages", [])
    }

    return {
        "declared_chunks_file_sha256": chunks_file_sha256,
        "compatibility_status": "not_checked",
        "referenced_chunk_count": len(relevant_chunk_ids),
        "referenced_page_count": len(relevant_page_keys),
        "referenced_pdf_count": len({pdf_sha1 for pdf_sha1, _ in relevant_page_keys}),
        "status": "format_valid",
        "warnings": [],
    }


def _ranking_warnings(
    canonical: dict[str, Any],
    index_cache: models.DerivedCache | None,
) -> list[str]:
    declared_hash = canonical.get("metadata", {}).get("chunks_file_sha256")
    if not declared_hash or index_cache is None:
        return []
    chunks_cache_key = index_cache.metadata_json.get("chunks_cache_key")
    if not chunks_cache_key:
        return ["Selected index has no chunks cache key; GT chunk hash was not checked."]
    chunks_path = get_settings().data_dir / "cache" / "chunks" / str(chunks_cache_key) / "chunks.jsonl"
    if not chunks_path.exists():
        return ["Selected index chunks file is missing; GT chunk hash was not checked."]
    actual_hash = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    if str(declared_hash) != actual_hash:
        return ["GT chunks_file_sha256 does not match the selected index chunks cache."]
    return []


def _dcg_gain(relevance: int, rank: int) -> float:
    if relevance <= 0:
        return 0.0
    return (math.pow(2, relevance) - 1.0) / math.log2(rank + 1)


def _top_score(chunks: list[dict[str, Any]]) -> float | None:
    scores = [
        float(chunk["score"])
        for chunk in chunks
        if chunk.get("score") is not None
    ]
    return max(scores) if scores else None


def _score_page_ground_truth_question(
    *,
    k: int,
    question: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    relevant_page_indexes = {
        int(page["page_index"])
        for page in question.get("relevant_pages", [])
    }
    retrieved_page_sets = [_retrieved_page_indexes(item) for item in retrieved_chunks]
    if retrieved_chunks and not any(retrieved_page_sets):
        warnings = [
            *warnings,
            "Retrieved items do not include page metadata; page-level GT scoring may be incomplete.",
        ]
    found_items = [
        index
        for index, page_indexes in enumerate(retrieved_page_sets, start=1)
        if relevant_page_indexes.intersection(page_indexes)
    ]
    found_relevant_pages = set().union(
        *[
            relevant_page_indexes.intersection(page_indexes)
            for page_indexes in retrieved_page_sets
        ]
    ) if retrieved_page_sets else set()
    first_relevant_rank = found_items[0] if found_items else None
    return {
        "expected_answer_type": "found",
        "k": k,
        "metrics": {
            "page_hit_at_k": 1.0 if found_items else 0.0,
            "page_mrr_at_k": (1.0 / first_relevant_rank) if first_relevant_rank else 0.0,
            "page_precision_at_k": len(found_items) / k if k else 0.0,
            "page_recall_at_k": (
                len(found_relevant_pages) / len(relevant_page_indexes)
                if relevant_page_indexes
                else 0.0
            ),
        },
        "question_id": question["question_id"],
        "warnings": warnings,
    }


def _retrieved_page_indexes(item: dict[str, Any]) -> set[int]:
    start = _runtime_page_to_index(item.get("page_start") or item.get("page"))
    end = _runtime_page_to_index(item.get("page_end") or item.get("page"))
    if start is None and end is None:
        return set()
    if start is None:
        start = end
    if end is None:
        end = start
    if start is None or end is None:
        return set()
    low = min(start, end)
    high = max(start, end)
    return set(range(low, high + 1))


def _runtime_page_to_index(value: Any) -> int | None:
    if not isinstance(value, int):
        return None
    if value < 1:
        return None
    return value - 1


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
    chunk_judgment_count = sum(len(question["relevant_chunks"]) for question in questions)
    page_judgment_count = sum(len(question.get("relevant_pages") or []) for question in questions)
    return {
        "canonical_format": GT_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "data_asset_id": data_asset.id if data_asset else None,
        "found_count": len(found_questions),
        "ground_truth_set_id": ground_truth_set_id,
        "ground_truth_type": _ground_truth_type(canonical),
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
        "page_judgment_count": page_judgment_count,
        "relevance_judgment_count": chunk_judgment_count,
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
        "page_judgment_count": manifest["page_judgment_count"],
        "relevance_judgment_count": manifest["relevance_judgment_count"],
        "referenced_page_count": manifest["validation"].get("referenced_page_count", 0),
        "referenced_pdf_count": manifest["validation"].get("referenced_pdf_count", 0),
        "schema_version": manifest["schema_version"],
        "validation": manifest["validation"],
    }


def _ground_truth_type(canonical: dict[str, Any]) -> str:
    return str(canonical.get("metadata", {}).get("ground_truth_type") or GT_TYPE_CHUNK_QRELS)


def _looks_like_page_ground_truth_records(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    first = value[0]
    return (
        isinstance(first, dict)
        and "question_text" in first
        and "references" in first
        and ("kind" in first or "value" in first)
    )


def _required_str(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"Ground truth field {key} is required")
    return item.strip()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "ground_truth.json"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name[:180] or "ground_truth.json"
