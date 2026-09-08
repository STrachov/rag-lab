"""Read-only explanations of already computed retrieval preview results."""
from typing import Any


def hybrid_diagnostics(dense: list[dict], sparse: list[dict], fused: list[dict], *, rrf_k: int) -> dict:
    def candidates(results: list[dict], stage: str) -> list[dict]:
        return [{
            "chunk_id": str(item.get("payload", {}).get("chunk_id") or item.get("id")),
            "page": item.get("payload", {}).get("page"),
            f"{stage}_rank": rank, f"{stage}_score": item.get("score"),
        } for rank, item in enumerate(results, 1)]

    dense_rows = candidates(dense, "dense")
    sparse_rows = candidates(sparse, "sparse")
    dense_by_id = {row["chunk_id"]: row for row in dense_rows}
    sparse_by_id = {row["chunk_id"]: row for row in sparse_rows}
    rows = []
    for rank, item in enumerate(fused[:30], 1):
        chunk_id = str(item["chunk_id"])
        dense_rank = dense_by_id.get(chunk_id, {}).get("dense_rank")
        sparse_rank = sparse_by_id.get(chunk_id, {}).get("sparse_rank")
        rows.append({
            "chunk_id": chunk_id, "page": item.get("page"), "fused_rank": rank,
            "dense_rank": dense_rank, "sparse_rank": sparse_rank,
            "dense_contribution": 1 / (rrf_k + dense_rank) if dense_rank is not None else 0.0,
            "sparse_contribution": 1 / (rrf_k + sparse_rank) if sparse_rank is not None else 0.0,
            "fused_score": item["score"],
        })
    return {
        "fusion": "rrf", "rrf_k": rrf_k, "candidate_display_limit": 30,
        "candidate_counts": {"dense": len(dense), "sparse": len(sparse), "fused": len(fused)},
        "dense_candidates": dense_rows[:30], "sparse_candidates": sparse_rows[:30],
        "fused_candidates": rows,
    }


def parent_page_diagnostics(results: list[dict[str, Any]], *, strategy: str,
                            parent_score: str, top_k: int) -> dict:
    applied = strategy == "parent_page_retrieval"
    pages = []
    if applied:
        for rank, item in enumerate(results[:min(5, top_k)], 1):
            children = [dict(child) for child in item["evidence_chunks"]]
            maximum = max(child["score"] for child in children)
            pages.append({
                "rank": rank, "page": item.get("page"), "parent_id": item["parent_id"],
                "page_score": item["score"], "child_chunks": children,
                "max_child_chunk_ids": [child["chunk_id"] for child in children
                                        if child["score"] == maximum] if parent_score == "max" else [],
            })
    return {"applied": applied, "strategy": strategy, "parent_score": parent_score,
            "page_display_limit": 5, "pages": pages}


def dense_diagnostics(results: list[dict]) -> dict:
    return {
        "fusion": None, "rrf_k": None, "candidate_display_limit": 30,
        "candidate_counts": {"dense": len(results)},
        "dense_candidates": [{"chunk_id": item["chunk_id"], "page": item.get("page"),
            "parent_id": item.get("parent_id"), "dense_rank": rank,
            "dense_score": item["score"]} for rank, item in enumerate(results[:30], 1)],
        "sparse_candidates": [], "fused_candidates": [],
    }


def reranking_diagnostics(results: list[dict], *, top_k: int) -> list[dict]:
    rows = []
    for rank, item in enumerate(results[:min(5, top_k)], 1):
        child_id = item.get("rerank_child_id")
        if child_id is None:
            continue
        child = next(child for child in item["evidence_chunks"] if child["chunk_id"] == child_id)
        rows.append({"page": item.get("page"), "parent_id": item.get("parent_id"),
            "rerank_child_id": child_id, "selected_child_rank": child["rank"],
            "selected_child_score": child["score"], "original_parent_score": item["original_score"],
            "pre_rerank_parent_rank": item["original_rank"],
            "rerank_score": item["rerank_score"], "final_parent_rank": rank})
    return rows
