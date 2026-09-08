"""Shared input semantics for preview and controlled evaluation."""
from copy import deepcopy

from app.services.rerankers import rerank_chunks_with_usage


def reranking_input_policy(strategy: str):
    if strategy == "chunk_retrieval":
        return "full_chunk_text"
    return {
        "policy": "best_retrieved_child.v1",
        "text_source": "chunks.text",
        "children_per_parent": 1,
        "selection": "retrieval_score_desc",
        "tie_break": ["retrieval_rank_asc", "chunk_id_asc"],
        "character_clip": None,
        "token_truncation": "backend_pair_max_length",
        "parent_score_assignment": "selected_child_rerank_score",
    }


def rerank_candidates(*, candidates, chunks_by_id, strategy, query, reranking, resolved_reranker=None):
    if reranking["text_input"] != reranking_input_policy(strategy):
        raise ValueError("Unsupported reranking input semantics")
    prepared = []
    texts = {}
    for candidate in candidates:
        item = deepcopy(candidate)
        if strategy == "chunk_retrieval":
            child_id = str(item["chunk_id"])
        else:
            evidence = item.get("evidence_chunks") or []
            if not evidence:
                raise ValueError("Parent candidate has no retrieved evidence children")
            selected = min(evidence, key=lambda child: (
                -float(child["score"]), int(child["rank"]), str(child["chunk_id"])))
            child_id = str(selected["chunk_id"])
        child = chunks_by_id.get(child_id)
        if child is None or not isinstance(child.get("text"), str) or not child["text"].strip():
            raise ValueError("Required full reranking chunk text is missing")
        if strategy != "chunk_retrieval":
            if child.get("parent_id") != item.get("parent_id"):
                raise ValueError("Selected reranking child belongs to a different parent")
            if not isinstance(child.get("parent_text"), str) or not child["parent_text"].strip():
                raise ValueError("Required full parent text is missing")
            item["parent_text"] = child["parent_text"]
            item["rerank_child_id"] = child_id
        texts[str(item["chunk_id"])] = child["text"]
        prepared.append(item)
    return rerank_chunks_with_usage(
        chunks=prepared, query=query, model_id=reranking["model_id"], params=reranking["params"],
        text_by_chunk_id=texts,
        **({"resolved_reranker": resolved_reranker} if resolved_reranker is not None else {}),
    )
