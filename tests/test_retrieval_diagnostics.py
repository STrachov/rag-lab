from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.services import runtime_cache
from app.services.retrieval_diagnostics import hybrid_diagnostics, parent_page_diagnostics


@pytest.mark.parametrize("parent_score", ["max", "sum", "mean"])
def test_preview_diagnostics_explain_actual_results_without_extra_search(monkeypatch, parent_score):
    def hit(chunk_id, page, score):
        return {"payload": {"chunk_id": chunk_id, "page": page,
                "parent_id": f"page_{page}", "parent_type": "page"}, "score": score}

    dense = [hit("a", 2, 0.9), hit("b", 1, 0.8), hit("d", 1, 0.7)]
    sparse = [hit("c", 1, 90), hit("b", 1, 80), hit("a", 2, 70)]
    originals = deepcopy((dense, sparse))
    calls = []
    class Store:
        def search_dense(self, **kwargs):
            calls.append("dense")
            return dense
        def search_sparse(self, **kwargs):
            calls.append("sparse")
            return sparse
    monkeypatch.setattr(runtime_cache, "create_embedder", lambda *args: SimpleNamespace(embed_query=lambda q: [1.0]))
    monkeypatch.setattr(runtime_cache, "_encode_sparse_query", lambda *args: {"indices": [1], "values": [1.0]})
    monkeypatch.setattr(runtime_cache, "_chunks_by_id", lambda *args: {
        key: {"text": key, "parent_text": key} for key in "abcd"})
    kwargs = dict(index_cache=SimpleNamespace(id="index", metadata_json={
        "embedding": {"model_id": "synthetic", "params": {}}, "index_mode": "hybrid", "collection_name": "collection"}),
        mode="hybrid", query="synthetic", strategy="parent_page_retrieval", parent_score=parent_score,
        candidate_k=30, top_k=5, vector_store=Store())
    baseline = runtime_cache.retrieve_from_qdrant(**kwargs)
    calls.clear()
    result = runtime_cache.retrieve_from_qdrant(**kwargs, include_diagnostics=True)
    assert calls == ["dense", "sparse"]
    assert (dense, sparse) == originals
    diagnostic = result.pop("diagnostics")
    assert result == baseline
    assert diagnostic["rrf_k"] == 60
    assert [(r["chunk_id"], r["dense_rank"], r["dense_score"]) for r in diagnostic["dense_candidates"]] == [
        ("a", 1, .9), ("b", 2, .8), ("d", 3, .7)]
    assert [(r["chunk_id"], r["sparse_rank"], r["sparse_score"]) for r in diagnostic["sparse_candidates"]] == [
        ("c", 1, 90), ("b", 2, 80), ("a", 3, 70)]
    fused = {r["chunk_id"]: r for r in diagnostic["fused_candidates"]}
    for key, dr, sr in [("a", 1, 3), ("b", 2, 2), ("c", None, 1), ("d", 3, None)]:
        row = fused[key]
        assert (row["dense_rank"], row["sparse_rank"]) == (dr, sr)
        assert row["dense_contribution"] == (1 / (60 + dr) if dr else 0)
        assert row["sparse_contribution"] == (1 / (60 + sr) if sr else 0)
        assert row["fused_score"] == pytest.approx(row["dense_contribution"] + row["sparse_contribution"])
    pages = diagnostic["parent_page_aggregation"]["pages"]
    for page, actual in zip(pages, result["retrieved_chunks"], strict=True):
        assert page["page_score"] == actual["score"]
        assert page["child_chunks"] == actual["evidence_chunks"]
        for child in page["child_chunks"]:
            assert child["score"] == fused[child["chunk_id"]]["fused_score"]
    first_page = next(page for page in pages if page["page"] == 1)
    assert first_page["max_child_chunk_ids"] == (["b"] if parent_score == "max" else [])


def test_diagnostic_display_limit_does_not_truncate_fusion_inputs():
    dense = [{"payload": {"chunk_id": str(i), "page": i}, "score": 1} for i in range(40)]
    sparse = list(reversed(dense))
    fused = runtime_cache._rrf_merge(dense, sparse)
    diagnostic = hybrid_diagnostics(dense, sparse, fused, rrf_k=60)
    assert diagnostic["candidate_counts"] == {"dense": 40, "sparse": 40, "fused": 40}
    assert all(len(diagnostic[key]) == 30 for key in ["dense_candidates", "sparse_candidates", "fused_candidates"])
    row = next(row for row in diagnostic["fused_candidates"] if row["chunk_id"] == "0")
    assert row["sparse_rank"] == 40
    assert row["fused_score"] == pytest.approx(1 / 61 + 1 / 100)


def test_hybrid_preview_api_exposes_diagnostics_only_in_preview(client, monkeypatch, tmp_path):
    from test_reproducibility import Pipeline
    pipeline = Pipeline(client, monkeypatch, tmp_path)
    response = client.post(pipeline.base + "/retrieve/preview", json={
        "index_cache_id": pipeline.index["id"], "query": "synthetic", "mode": "hybrid"})
    assert response.status_code == 200
    diagnostic = response.json()["diagnostics"]
    assert diagnostic["fusion"] == "rrf"
    assert diagnostic["parent_page_aggregation"]["applied"] is False
    assert diagnostic["parent_page_aggregation"]["pages"] == []
    experiment = pipeline.evaluate(pipeline.create()).json()
    assert "diagnostics" not in experiment["metrics_summary_json"]
    assert all("diagnostics" not in row for row in experiment["metrics_summary_json"]["questions"])


def test_page_diagnostics_limit_and_max_ties():
    results = [{"parent_id": f"page_{i}", "page": i, "score": 0.5,
                "evidence_chunks": [{"chunk_id": f"{i}a", "rank": 1, "score": .5},
                                    {"chunk_id": f"{i}b", "rank": 2, "score": .5}]}
               for i in range(1, 9)]
    diagnostic = parent_page_diagnostics(results, strategy="parent_page_retrieval", parent_score="max", top_k=8)
    assert len(diagnostic["pages"]) == 5
    assert diagnostic["pages"][0]["max_child_chunk_ids"] == ["1a", "1b"]
    assert len(parent_page_diagnostics(results, strategy="parent_page_retrieval",
                                      parent_score="max", top_k=2)["pages"]) == 2
