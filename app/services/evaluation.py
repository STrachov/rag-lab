from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.db import models
from app.services.ground_truth import (
    list_ground_truth_questions,
    read_canonical_ground_truth,
    score_ground_truth_ranking,
)
from app.services.runtime_cache import build_reranking_snapshot, retrieve_from_qdrant

logger = logging.getLogger(__name__)


def evaluate_ground_truth_questions(
    *,
    ground_truth_set: models.GroundTruthSet,
    index_cache: models.DerivedCache,
    saved_experiment: models.SavedExperiment,
    vector_store: Any,
) -> dict[str, Any]:
    snapshot = dict(saved_experiment.params_snapshot_json or {})
    retrieval = _retrieval_params(snapshot)
    reranking_snapshot = _reranking_snapshot(snapshot)
    questions = list_ground_truth_questions(ground_truth_set)
    canonical_questions = {
        str(question["question_id"]): question
        for question in read_canonical_ground_truth(ground_truth_set).get("questions", [])
    }
    rows: list[dict[str, Any]] = []
    metric_values: dict[str, list[float]] = defaultdict(list)
    started_at = datetime.now(UTC)
    reranking = reranking_snapshot["reranking"] if reranking_snapshot else None
    logger.info(
        "gt evaluation start saved_experiment_id=%s ground_truth_set_id=%s index_cache_id=%s "
        "question_count=%s retrieval_strategy=%s retrieval_mode=%s top_k=%s candidate_k=%s "
        "reranker_model_id=%s",
        saved_experiment.id,
        ground_truth_set.id,
        index_cache.id,
        len(questions),
        retrieval["strategy"],
        retrieval["mode"],
        retrieval["top_k"],
        retrieval["candidate_k"],
        reranking.get("model_id") if reranking else None,
    )

    for question_index, question in enumerate(questions, start=1):
        failed_stage = "start"
        try:
            failed_stage = "retrieve"
            result = retrieve_from_qdrant(
                candidate_k=retrieval["candidate_k"],
                index_cache=index_cache,
                mode=retrieval["mode"],
                parent_score=retrieval["parent_score"],
                query=str(question["question"]),
                reranking_snapshot=reranking_snapshot,
                strategy=retrieval["strategy"],
                top_k=retrieval["top_k"],
                vector_store=vector_store,
            )
            failed_stage = "score_ground_truth"
            score = score_ground_truth_ranking(
                ground_truth_set=ground_truth_set,
                index_cache=index_cache,
                k=retrieval["top_k"],
                question_id=str(question["question_id"]),
                retrieved_chunks=list(result["retrieved_chunks"]),
            )
            metrics = {name: float(value) for name, value in score["metrics"].items()}
            for name, value in metrics.items():
                metric_values[name].append(value)
            rows.append(
                {
                    "error_json": None,
                    "expected_answer_brief": question.get("expected_answer_brief"),
                    "expected_answer_type": score["expected_answer_type"],
                    "ground_truth": _ground_truth_summary(
                        canonical_questions.get(str(question["question_id"]), question)
                    ),
                    "metrics": metrics,
                    "question": question["question"],
                    "question_id": question["question_id"],
                    "retrieved": _retrieved_results(result["retrieved_chunks"]),
                    "status": "completed",
                    "top_result": _top_result(result["retrieved_chunks"]),
                    "warnings": list(score.get("warnings") or []),
                }
            )
        except Exception as exc:
            logger.exception(
                "gt evaluation question failed saved_experiment_id=%s ground_truth_set_id=%s "
                "index_cache_id=%s question_id=%s question_index=%s question_count=%s "
                "failed_stage=%s retrieval_strategy=%s retrieval_mode=%s top_k=%s candidate_k=%s "
                "reranker_model_id=%s error_type=%s error_message=%s",
                saved_experiment.id,
                ground_truth_set.id,
                index_cache.id,
                question.get("question_id"),
                question_index,
                len(questions),
                failed_stage,
                retrieval["strategy"],
                retrieval["mode"],
                retrieval["top_k"],
                retrieval["candidate_k"],
                reranking.get("model_id") if reranking else None,
                type(exc).__name__,
                str(exc),
            )
            rows.append(
                {
                    "error_json": {
                        "failed_stage": failed_stage,
                        "message": str(exc),
                        "type": type(exc).__name__,
                    },
                    "expected_answer_brief": question.get("expected_answer_brief"),
                    "expected_answer_type": question.get("expected_answer_type"),
                    "ground_truth": _ground_truth_summary(
                        canonical_questions.get(str(question.get("question_id")), question)
                    ),
                    "metrics": {},
                    "question": question.get("question"),
                    "question_id": question.get("question_id"),
                    "retrieved": [],
                    "status": "failed",
                    "top_result": None,
                    "warnings": [],
                }
            )

    completed_rows = [row for row in rows if row["status"] == "completed"]
    failed_rows = [row for row in rows if row["status"] == "failed"]
    warnings_count = sum(len(row.get("warnings") or []) for row in rows)
    finished_at = datetime.now(UTC)
    first_error = failed_rows[0].get("error_json") if failed_rows else None
    logger.info(
        "gt evaluation finished saved_experiment_id=%s ground_truth_set_id=%s index_cache_id=%s "
        "status=%s completed=%s failed=%s question_count=%s warning_count=%s duration_seconds=%.3f "
        "metric_keys=%s first_error_type=%s first_error_stage=%s first_error_message=%s",
        saved_experiment.id,
        ground_truth_set.id,
        index_cache.id,
        "completed" if not failed_rows else "completed_with_errors",
        len(completed_rows),
        len(failed_rows),
        len(rows),
        warnings_count,
        (finished_at - started_at).total_seconds(),
        ",".join(sorted(metric_values.keys())),
        first_error.get("type") if isinstance(first_error, dict) else None,
        first_error.get("failed_stage") if isinstance(first_error, dict) else None,
        first_error.get("message") if isinstance(first_error, dict) else None,
    )
    return {
        "evaluation": {
            "completed_question_count": len(completed_rows),
            "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
            "error_count": len(failed_rows),
            "ground_truth_set_id": ground_truth_set.id,
            "index_cache_id": index_cache.id,
            "question_count": len(rows),
            "reranking": snapshot.get("reranking"),
            "retrieval": retrieval,
            "schema_version": "raglab.gt_evaluation.v1",
            "status": "completed" if not failed_rows else "completed_with_errors",
            "warning_count": warnings_count,
        },
        "metric_averages": {
            name: sum(values) / len(values)
            for name, values in sorted(metric_values.items())
            if values
        },
        "questions": rows,
    }


def _retrieval_params(snapshot: dict[str, Any]) -> dict[str, Any]:
    retrieval = dict(snapshot.get("retrieval") or {})
    return {
        "candidate_k": _optional_int(retrieval.get("candidate_k")),
        "mode": str(retrieval.get("mode") or "hybrid"),
        "parent_score": str(retrieval.get("parent_score") or "max"),
        "strategy": str(retrieval.get("strategy") or "chunk_retrieval"),
        "top_k": max(1, int(retrieval.get("top_k") or 5)),
    }


def _reranking_snapshot(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    reranking = snapshot.get("reranking")
    if not isinstance(reranking, dict) or not bool(reranking.get("enabled")):
        return None
    return build_reranking_snapshot(str(reranking["model_id"]), dict(reranking.get("params") or {}))


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _top_result(chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not chunks:
        return None
    return _retrieved_result(chunks[0], rank=1)


def _retrieved_results(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_retrieved_result(chunk, rank=index) for index, chunk in enumerate(chunks, start=1)]


def _retrieved_result(chunk: dict[str, Any], *, rank: int) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "char_count": chunk.get("char_count"),
            "chunk_id": chunk.get("chunk_id"),
            "dense_score": chunk.get("dense_score"),
            "original_rank": chunk.get("original_rank"),
            "original_score": chunk.get("original_score"),
            "page": chunk.get("page"),
            "page_end": chunk.get("page_end"),
            "page_start": chunk.get("page_start"),
            "rank": rank,
            "rerank_score": chunk.get("rerank_score"),
            "score": chunk.get("score"),
            "source_name": chunk.get("source_name"),
            "sparse_score": chunk.get("sparse_score"),
            "token_count": chunk.get("token_count"),
        }.items()
        if value is not None
    }


def _ground_truth_summary(question: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            "expected_answer": question.get("expected_answer"),
            "expected_answer_brief": question.get("expected_answer_brief"),
            "expected_answer_type": question.get("expected_answer_type"),
            "relevant_chunks": list(question.get("relevant_chunks") or []),
            "relevant_pages": [
                {
                    **page,
                    "page_number": int(page["page_index"]) + 1,
                }
                for page in question.get("relevant_pages", [])
                if isinstance(page, dict) and isinstance(page.get("page_index"), int)
            ],
        }.items()
        if value not in (None, [], {})
    }
