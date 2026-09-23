from copy import deepcopy
from types import SimpleNamespace
import json

import pytest

from app.services import runtime_cache, rerankers
from app.services.hashing import bytes_sha256
from app.services.reranking_inputs import rerank_candidates, reranking_input_policy


class RecordingReranker:
    def __init__(self):
        self.pairs = []

    def score(self, query, passages):
        self.pairs.extend((query, passage) for passage in passages)
        return [0.9 if "evidence" in text else 0.1 for text in passages]


def config(strategy):
    return {"model_id": "synthetic", "params": {}, "text_input": reranking_input_policy(strategy)}


@pytest.mark.parametrize("strategy", ["parent_page_retrieval", "parent_chapter_retrieval"])
def test_best_child_selection_is_deterministic_and_retains_full_parent(strategy):
    selected_text = "retrieved context " * 100 + " evidence at the end"
    parent_text = "irrelevant prefix " * 150 + selected_text
    children = {key: {"parent_id": "parent", "parent_text": parent_text,
                      "text": selected_text if key == "a" else "other"} for key in "abcd"}
    parent = {"chunk_id": "parent", "parent_id": "parent", "score": 5.0,
              "text_preview": parent_text[:1200], "evidence_chunks": [
                  {"chunk_id": "d", "score": .8, "rank": 1},
                  {"chunk_id": "c", "score": .9, "rank": 3},
                  {"chunk_id": "b", "score": .9, "rank": 2},
                  {"chunk_id": "a", "score": .9, "rank": 2}]}
    original = deepcopy(parent)
    for evidence in [parent["evidence_chunks"], list(reversed(parent["evidence_chunks"]))]:
        adapter = RecordingReranker()
        result = rerank_candidates(candidates=[{**parent, "evidence_chunks": evidence}],
            chunks_by_id=children, strategy=strategy, query="question", reranking=config(strategy),
            resolved_reranker=adapter)["chunks"][0]
        assert adapter.pairs == [("question", selected_text)]
        assert result["rerank_child_id"] == "a"
        assert result["parent_text"] == parent_text
        assert result["score"] == result["rerank_score"] == .9
        assert result["original_score"] == 5.0
    assert parent == original


@pytest.mark.parametrize("missing", ["child", "text", "parent_text", "wrong_parent"])
def test_missing_required_input_fails_without_preview_fallback(missing):
    child = {"text": "evidence", "parent_text": "full parent", "parent_id": "p"}
    children = {"c": child}
    if missing == "child": children.clear()
    elif missing == "wrong_parent": child["parent_id"] = "other"
    else: del child[missing]
    adapter = RecordingReranker()
    with pytest.raises(ValueError):
        rerank_candidates(candidates=[{"chunk_id": "p", "parent_id": "p", "text_preview": "fallback",
            "evidence_chunks": [{"chunk_id": "c", "rank": 1, "score": 1}]}], chunks_by_id=children,
            strategy="parent_page_retrieval", query="q", reranking=config("parent_page_retrieval"),
            resolved_reranker=adapter)
    assert adapter.pairs == []


def test_chunk_retrieval_keeps_full_chunk_input():
    adapter = RecordingReranker()
    text = "complete text " * 200
    result = rerank_candidates(candidates=[{"chunk_id": "c", "score": .2}],
        chunks_by_id={"c": {"text": text}}, strategy="chunk_retrieval", query="q",
        reranking=config("chunk_retrieval"), resolved_reranker=adapter)
    assert adapter.pairs == [("q", text)]
    assert "rerank_child_id" not in result["chunks"][0]


@pytest.mark.parametrize("mode", ["dense", "hybrid"])
def test_preview_and_evaluation_use_same_pairs_scores_and_top_k(tmp_path, monkeypatch, mode):
    rows = [{"chunk_id": key, "text": text, "parent_id": parent, "parent_type": "page",
             "page": page, "parent_text": "prefix " * 300 + text}
            for key, text, parent, page in [("a", "other", "p1", 1), ("b", "evidence", "p2", 2)]]
    content = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    directory = tmp_path / "chunks" / "key"
    directory.mkdir(parents=True)
    (directory / "chunks.jsonl").write_bytes(content)
    monkeypatch.setattr(runtime_cache, "_cache_root", lambda: tmp_path)
    metadata = {"embedding": {}, "index_mode": mode, "collection_name": "collection",
                "chunks_cache_key": "key", "input_chunks_sha256": bytes_sha256(content)}
    index = SimpleNamespace(id="index", metadata_json=metadata)
    adapter = RecordingReranker()
    inputs = runtime_cache.EvaluationInputs(metadata=metadata, chunks={r["chunk_id"]: r for r in rows},
        sparse_stats=None, embedder=SimpleNamespace(embed_query=lambda q: [1]), reranker=adapter,
        retrieval={"effective_candidate_k": 30, "rrf_k": 60})
    store = SimpleNamespace(search_dense=lambda **kw: [
        {"payload": {k: v for k, v in r.items() if k not in {"text", "parent_text"}}, "score": score}
        for r, score in zip(rows, [.8, .7])])
    store.search_sparse = store.search_dense
    monkeypatch.setattr(runtime_cache, "encode_bm25_query", lambda *args: {})
    evaluated = runtime_cache.retrieve_from_qdrant(index_cache=index, inputs=inputs, mode=mode, query="q",
        strategy="parent_page_retrieval", parent_score="max", candidate_k=30, top_k=1,
        include_diagnostics=True, vector_store=store, reranking_snapshot={"reranking": config("parent_page_retrieval")})
    expected_pairs = list(adapter.pairs)
    adapter.pairs.clear()
    monkeypatch.setattr(rerankers, "create_reranker", lambda *args: adapter)
    cache = SimpleNamespace(id="preview", metadata_json={"query": "q", "strategy": "parent_page_retrieval",
        "candidate_k": 30, "mode": mode, "index_cache_id": "index",
        "diagnostics": {k: v for k, v in evaluated["diagnostics"].items() if k != "reranking"},
        "retrieved_chunks": evaluated["candidate_chunks"]})
    preview = runtime_cache.rerank_retrieval_candidates(index_cache=index, retrieval_cache=cache,
        reranking_snapshot={"reranking": config("parent_page_retrieval")}, top_k=1)
    assert adapter.pairs == expected_pairs == [("q", "other"), ("q", "evidence")]
    assert preview["diagnostics"] == evaluated["diagnostics"]
    assert "reranking" not in cache.metadata_json["diagnostics"]
    row = preview["diagnostics"]["reranking"][0]
    actual = preview["retrieved_chunks"][0]
    assert row["rerank_child_id"] == actual["rerank_child_id"]
    assert row["selected_child_rank"] == 2
    assert row["selected_child_score"] == (.7 if mode == "dense" else 2 / 62)
    assert row["original_parent_score"] == (.7 if mode == "dense" else 2 / 62)
    assert row["rerank_score"] == actual["rerank_score"]
    assert row["pre_rerank_parent_rank"] == actual["original_rank"] == 2
    assert row["final_parent_rank"] == 1
    assert preview["retrieved_chunks"] == evaluated["retrieved_chunks"]
    assert preview["retrieved_chunks"][0]["parent_id"] == "p2"
    assert "parent_text" not in cache.metadata_json["retrieved_chunks"][0]


def test_snapshot_policy_and_hash_cover_parent_input_semantics(client, monkeypatch, tmp_path):
    from test_reproducibility import Pipeline
    from app.services.experiment_snapshot import pipeline_params_hash
    p = Pipeline(client, monkeypatch, tmp_path)
    result = p.create(retrieval={"strategy": "parent_page_retrieval", "mode": "dense"},
        reranking={"enabled": True, "model_id": "ms_marco_minilm_l6_v2", "params": {}})
    snapshot = result["params_snapshot_json"]
    assert snapshot["reranking"]["text_input"] == reranking_input_policy("parent_page_retrieval")
    assert snapshot["semantics"]["retrieval_version"] == "raglab.retrieval.v2"
    assert result["params_hash"] == pipeline_params_hash(snapshot)
    changed = deepcopy(snapshot)
    changed["reranking"]["text_input"]["character_clip"] = 1200
    assert pipeline_params_hash(changed) != result["params_hash"]
