from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.db import models
from app.services.ground_truth import list_ground_truth_questions, score_ground_truth_ranking
from app.services.runtime_cache import build_reranking_snapshot, retrieve_from_qdrant


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
    rows: list[dict[str, Any]] = []
    metric_values: dict[str, list[float]] = defaultdict(list)
    started_at = datetime.now(UTC)

    for question in questions:
        try:
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
                    "metrics": metrics,
                    "question": question["question"],
                    "question_id": question["question_id"],
                    "status": "completed",
                    "top_result": _top_result(result["retrieved_chunks"]),
                    "warnings": list(score.get("warnings") or []),
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "error_json": {
                        "message": str(exc),
                        "type": type(exc).__name__,
                    },
                    "expected_answer_brief": question.get("expected_answer_brief"),
                    "expected_answer_type": question.get("expected_answer_type"),
                    "metrics": {},
                    "question": question.get("question"),
                    "question_id": question.get("question_id"),
                    "status": "failed",
                    "top_result": None,
                    "warnings": [],
                }
            )

    completed_rows = [row for row in rows if row["status"] == "completed"]
    failed_rows = [row for row in rows if row["status"] == "failed"]
    warnings_count = sum(len(row.get("warnings") or []) for row in rows)
    finished_at = datetime.now(UTC)
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
    chunk = chunks[0]
    return {
        key: value
        for key, value in {
            "chunk_id": chunk.get("chunk_id"),
            "dense_score": chunk.get("dense_score"),
            "page": chunk.get("page"),
            "page_end": chunk.get("page_end"),
            "page_start": chunk.get("page_start"),
            "rerank_score": chunk.get("rerank_score"),
            "score": chunk.get("score"),
            "source_name": chunk.get("source_name"),
            "sparse_score": chunk.get("sparse_score"),
        }.items()
        if value is not None
    }
