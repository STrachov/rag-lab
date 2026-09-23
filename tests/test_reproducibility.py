from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services import code_version, evaluation, experiment_snapshot, runtime_cache
from test_projects_api import FakeEmbedder, _patch_data_dirs


class IsolatedStore:
    def __init__(self):
        self.collections = {}
        self.calls = []
        self.on_search = None

    def ensure_collection(self, *, collection_name, **kwargs):
        assert collection_name not in self.collections
        self.collections[collection_name] = []

    def upsert_points(self, *, collection_name, points):
        self.collections[collection_name] = deepcopy(points)

    def search_dense(self, *, collection_name, query_vector, top_k):
        self.calls.append((collection_name, top_k))
        if self.on_search:
            self.on_search()
        return [{"payload": point["payload"], "score": 1 / (i + 1)}
                for i, point in enumerate(self.collections[collection_name][:top_k])]

    def search_sparse(self, **kwargs):
        return self.search_dense(**kwargs)


class Pipeline:
    def __init__(self, client, monkeypatch, tmp_path):
        self.client = client
        self.monkeypatch = monkeypatch
        _patch_data_dirs(monkeypatch, tmp_path)
        self.store = IsolatedStore()
        monkeypatch.setattr("app.api.runtime._qdrant_store", lambda: self.store)
        monkeypatch.setattr("app.api.projects._qdrant_store", lambda: self.store)
        monkeypatch.setattr(runtime_cache, "create_embedder", lambda *args: FakeEmbedder())
        monkeypatch.setattr(runtime_cache, "create_embedder_from_snapshot", lambda snapshot: FakeEmbedder())
        self.project = client.post("/v1/projects", json={"name": "Synthetic controlled series"}).json()["id"]
        self.base = f"/v1/projects/{self.project}"
        text = "# Policy\n\n" + " ".join(f"word{i}" for i in range(2000))
        self.source = self.post("/data-assets/raw/upload", data={"name": "Source", "data_format": "markdown"},
                                files={"files": ("policy.md", text.encode(), "text/markdown")})
        self.prepared = self.post(f"/data-assets/{self.source['id']}/prepare",
                                 json={"name": "Prepared", "method_id": "pymupdf_text", "params": {"page_breaks": True}})
        self.gt_payload = {
            "schema_version": "raglab.ground_truth.v1",
            "metadata": {"ground_truth_type": "page_level_qrels", "annotation_version": "synthetic-v1"},
            "questions": [{"question_id": f"q{i}", "question": f"What does policy {i} say?",
                           "expected_answer_type": "found", "relevant_pages": [{"pdf_sha1": "synthetic", "page_index": 0}],
                           "metadata": {"source": "synthetic", "difficulty": "easy", "tags": ["policy"]}}
                          for i in range(2)],
            "evaluation_slices": [{"id": "easy", "label": "Easy", "filter": {"difficulty": ["easy"]}}],
        }
        self.gt = self.upload_gt(self.gt_payload)
        self.chunks, self.index = self.build()

    def post(self, suffix, **kwargs):
        response = self.client.post(self.base + suffix, **kwargs)
        assert response.status_code in {200, 201}, response.text
        return response.json()

    def upload_gt(self, payload):
        return self.post("/ground-truth-sets/upload", data={"name": "GT", "data_asset_id": self.prepared["id"]},
                         files={"file": ("gt.json", json.dumps(payload).encode(), "application/json")})

    def build(self, size=300, overlap=50, mode="hybrid"):
        chunks = self.post("/chunks/materialize", json={"data_asset_id": self.prepared["id"],
                          "chunking": {"strategy": "recursive", "params": {"chunk_size": size, "chunk_overlap": overlap}}})
        index = self.post("/indexes/qdrant", json={"chunks_cache_id": chunks["id"], "index_mode": mode,
                         "collection_name": "same_logical_name"})
        return chunks, index

    def choices(self, **overrides):
        return {"name": "Controlled experiment", "index_cache_id": self.index["id"],
                "ground_truth_set_id": self.gt["id"], "retrieval": {"mode": "hybrid", "top_k": 5}, **overrides}

    def create(self, **overrides):
        return self.post("/saved-experiments", json=self.choices(**overrides))

    def evaluate(self, experiment):
        return self.client.post(self.base + f"/saved-experiments/{experiment['id']}/evaluate", json={})

    def get(self, experiment):
        return self.client.get(self.base + f"/saved-experiments/{experiment['id']}").json()


@pytest.fixture
def pipeline(client, monkeypatch, tmp_path):
    return Pipeline(client, monkeypatch, tmp_path)


def test_historical_lineage_and_snapshot_survive_current_changes(pipeline):
    p = pipeline
    p.post(f"/data-assets/{p.prepared['id']}/files", files={"files": ("new.md", b"New content", "text/markdown")})
    p.post(f"/data-assets/{p.source['id']}/files", files={"files": ("new-source.md", b"New source", "text/markdown")})
    experiment = p.create()
    snapshot = experiment["params_snapshot_json"]
    assert snapshot["data"]["prepared"]["manifest_hash"] == p.prepared["manifest_hash"]
    assert snapshot["data"]["source"]["manifest_hash"] == p.source["manifest_hash"]
    assert experiment["data_asset_manifest_hash"] == p.prepared["manifest_hash"]
    assert [f["original_name"] for f in snapshot["data"]["source"]["files"]] == ["policy.md"]
    assert len(snapshot["data"]["prepared"]["files"]) == 1
    p.monkeypatch.setattr(experiment_snapshot, "build_reranking_snapshot", lambda *args: pytest.fail("catalog reread"))
    assert p.get(experiment)["params_snapshot_json"] == snapshot


@pytest.mark.parametrize("field,value", [
    ("params_hash", "forged"), ("params_snapshot_json", {}), ("code_commit", "forged"),
    ("data_asset_manifest_hash", "forged"), ("data_asset_id", "forged"), ("metrics_summary_json", {"hit": 1}),
])
def test_client_cannot_supply_provenance(pipeline, field, value):
    response = pipeline.client.post(pipeline.base + "/saved-experiments", json=pipeline.choices(**{field: value}))
    assert response.status_code == 422


def test_materialization_hash_and_index_input_binding(pipeline):
    p = pipeline
    metadata = p.chunks["metadata_json"]
    path = Path(metadata["chunks_path"])
    original = path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    assert metadata["chunks_file_sha256"] == digest == p.index["metadata_json"]["input_chunks_sha256"]
    assert metadata["chunk_count"] == len(original.splitlines())
    path.write_bytes(original + b"\n")
    assert hashlib.sha256(path.read_bytes()).hexdigest() != digest
    assert p.client.post(p.base + "/indexes/qdrant", json={"chunks_cache_id": p.chunks["id"]}).status_code == 400
    assert p.client.post(p.base + "/saved-experiments", json=p.choices()).status_code == 400
    fresh_chunks, fresh_index = p.build()
    assert fresh_chunks["id"] != p.chunks["id"]
    assert fresh_chunks["metadata_json"]["chunks_path"] != str(path)
    assert fresh_index["metadata_json"]["chunks_cache_id"] == fresh_chunks["id"]


def test_index_isolation_and_rebuild_after_deletion(pipeline):
    p = pipeline
    old_collection = p.index["metadata_json"]["collection_name"]
    old_points = deepcopy(p.store.collections[old_collection])
    _, second = p.build(700, 100)
    assert second["metadata_json"]["collection_name"] != old_collection
    assert p.store.collections[old_collection] == old_points
    assert p.client.delete(p.base + f"/derived-cache/{p.index['id']}").status_code == 200
    rebuilt = p.post("/indexes/qdrant", json={"chunks_cache_id": p.chunks["id"], "collection_name": "same_logical_name"})
    assert rebuilt["metadata_json"]["collection_name"] not in {old_collection, second["metadata_json"]["collection_name"]}
    assert rebuilt["params_hash"] == p.index["params_hash"]
    assert rebuilt["cache_key"] != p.index["cache_key"]


@pytest.mark.parametrize("change", ["question", "qrel", "source", "difficulty", "tag", "slice"])
def test_exact_canonical_hash_covers_all_gt_content(pipeline, change):
    p = pipeline
    path = Path(p.gt["storage_path"])
    assert p.gt["metadata_json"]["canonical_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    payload = deepcopy(p.gt_payload)
    question = payload["questions"][0]
    if change == "question": question["question"] += " Changed"
    elif change == "qrel": question["relevant_pages"][0]["page_index"] = 2
    elif change in {"source", "difficulty"}: question["metadata"][change] = "changed"
    elif change == "tag": question["metadata"]["tags"].append("changed")
    else: payload["evaluation_slices"][0]["filter"]["difficulty"] = ["hard"]
    changed = p.upload_gt(payload)
    assert changed["metadata_json"]["canonical_sha256"] != p.gt["metadata_json"]["canonical_sha256"]


def test_single_gt_read_and_frozen_chunks_statistics(pipeline):
    p = pipeline
    experiment = p.create()
    watched = {Path(p.gt["storage_path"]), Path(p.chunks["metadata_json"]["chunks_path"]),
               Path(p.index["metadata_json"]["sparse_stats_path"])}
    counts = {path: 0 for path in watched}
    read = Path.read_bytes
    def counted(path):
        if path in counts: counts[path] += 1
        return read(path)
    p.monkeypatch.setattr(Path, "read_bytes", counted)
    def mutate():
        for path in watched:
            if path.exists(): path.unlink()
    p.store.on_search = mutate
    response = p.evaluate(experiment)
    assert response.status_code == 200, response.text
    summary = response.json()["metrics_summary_json"]
    assert set(counts.values()) == {1}
    assert summary["evaluation"]["completed_question_count"] == 2
    assert summary["slice_metrics"]["easy"]["question_count"] == 2
    assert summary["questions"][0]["question_metadata"]["difficulty"] == "easy"
    assert summary["questions"][0]["ground_truth"]["relevant_pages"][0]["page_index"] == 0


@pytest.mark.parametrize("target,operation", [("gt", "remove"), ("gt", "change"), ("chunks", "remove"),
                                              ("chunks", "change"), ("sparse", "remove"), ("sparse", "change")])
def test_missing_or_changed_inputs_consume_failed_attempt(pipeline, target, operation):
    p = pipeline
    experiment = p.create()
    path = Path({"gt": p.gt["storage_path"], "chunks": p.chunks["metadata_json"]["chunks_path"],
                 "sparse": p.index["metadata_json"]["sparse_stats_path"]}[target])
    if operation == "remove": path.unlink()
    else: path.write_bytes(path.read_bytes() + b"\n")
    assert p.evaluate(experiment).status_code == 400
    failed = p.get(experiment)
    assert failed["status"] == "failed"
    assert failed["finished_at"] and failed["error_json"]
    assert "code" in failed["metrics_summary_json"]["evaluation"]
    assert p.evaluate(experiment).status_code == 409
    assert p.get(experiment) == failed


def test_index_substitution_rejected_and_success_is_immutable(pipeline):
    p = pipeline
    experiment = p.create()
    _, other = p.build(500, 75)
    url = p.base + f"/saved-experiments/{experiment['id']}/evaluate"
    assert p.client.post(url, json={"index_cache_id": other["id"]}).status_code == 422
    response = p.evaluate(experiment)
    assert response.status_code == 200, response.text
    completed = response.json()
    assert {collection for collection, _ in p.store.calls} == {p.index["metadata_json"]["collection_name"]}
    assert p.evaluate(experiment).status_code == 409
    assert p.get(experiment) == completed


def test_cache_deletion_preserves_snapshot_and_metrics(pipeline):
    p = pipeline
    experiment = p.create()
    pending = p.create()
    assert p.evaluate(experiment).status_code == 200
    completed = p.get(experiment)
    assert p.client.delete(p.base + f"/derived-cache/{p.chunks['id']}?cascade_dependents=true").status_code == 200
    assert p.get(experiment) == completed
    assert p.evaluate(pending).status_code == 400
    assert p.get(pending)["status"] == "failed"


def test_effective_settings_and_no_future_catalog_resolution(pipeline):
    p = pipeline
    seen = []
    class Reranker:
        def score(self, query, passages):
            assert all(len(text) > 1200 for text in passages)
            return [1.0] * len(passages)
    def make_reranker(snapshot):
        seen.append(snapshot)
        return Reranker()
    p.monkeypatch.setattr(runtime_cache, "create_reranker_from_snapshot", make_reranker)
    experiment = p.create(retrieval={"mode": "dense", "top_k": 2, "candidate_k": 1000},
                          reranking={"enabled": True, "model_id": "ms_marco_minilm_l6_v2", "params": {}})
    snapshot = experiment["params_snapshot_json"]
    assert snapshot["retrieval"]["candidate_k"] == 1000
    assert snapshot["retrieval"]["effective_candidate_k"] == 100
    assert snapshot["reranking"]["params"]
    p.monkeypatch.setattr("app.services.embeddings.get_embedding_model", lambda *args: pytest.fail("Embedding catalog reread"))
    p.monkeypatch.setattr("app.services.rerankers.get_reranker_model", lambda *args: pytest.fail("Reranker catalog reread"))
    def remove_chunks():
        Path(p.chunks["metadata_json"]["chunks_path"]).unlink(missing_ok=True)
    p.store.on_search = remove_chunks
    assert p.evaluate(experiment).status_code == 200
    assert seen == [snapshot["reranking"]]
    assert {count for _, count in p.store.calls} == {100}


def test_parameter_hash_excludes_provenance_and_requested_candidate_alias(pipeline):
    p = pipeline
    first = p.create(retrieval={"mode": "dense", "top_k": 5, "candidate_k": 500})
    _, second_index = p.build()
    second = p.create(index_cache_id=second_index["id"], retrieval={"mode": "dense", "top_k": 5, "candidate_k": 100})
    assert first["params_hash"] == second["params_hash"]
    changed = p.create(retrieval={"mode": "dense", "top_k": 4, "candidate_k": 100})
    assert first["params_hash"] != changed["params_hash"]


def test_same_recipe_builds_have_independent_preview_cache_dependencies(pipeline):
    p = pipeline
    second = p.post("/indexes/qdrant", json={"chunks_cache_id": p.chunks["id"], "collection_name": "same_logical_name"})
    first_preview = p.post("/retrieve/preview", json={"index_cache_id": p.index["id"], "query": "word1", "mode": "dense"})
    second_preview = p.post("/retrieve/preview", json={"index_cache_id": second["id"], "query": "word1", "mode": "dense"})
    assert first_preview["retrieval_cache_id"] != second_preview["retrieval_cache_id"]
    deleted = p.client.delete(p.base + f"/derived-cache/{p.index['id']}?cascade_dependents=true").json()["deleted_derived_cache_ids"]
    assert first_preview["retrieval_cache_id"] in deleted
    assert second_preview["retrieval_cache_id"] not in deleted
    remaining = p.client.get(p.base + "/derived-cache").json()["derived_caches"]
    assert second_preview["retrieval_cache_id"] in {cache["id"] for cache in remaining}


def test_wheeler_controlled_series(pipeline):
    p = pipeline
    p.monkeypatch.setenv("RAG_LAB_CODE_COMMIT", "a" * 40)
    snapshots = []
    for size, overlap in [(300, 50), (500, 75), (700, 100)]:
        _, index = p.build(size, overlap)
        experiment = p.create(index_cache_id=index["id"])
        response = p.evaluate(experiment)
        assert response.status_code == 200, response.text
        assert response.json()["code_commit"] == "a" * 40
        snapshots.append(response.json()["params_snapshot_json"])
    for stage in ["data", "embedding", "ground_truth", "retrieval", "reranking", "semantics"]:
        assert all(s[stage] == snapshots[0][stage] for s in snapshots)
    assert len({s["chunking"]["chunks_file_sha256"] for s in snapshots}) == 3
    assert len({s["chunking"]["cache_id"] for s in snapshots}) == 3
    assert len({s["index"]["cache_id"] for s in snapshots}) == 3
    assert [(s["chunking"]["params"]["chunk_size"], s["chunking"]["params"]["chunk_overlap"]) for s in snapshots] == [(300, 50), (500, 75), (700, 100)]


@pytest.mark.parametrize("mode", ["environment", "clean", "dirty", "missing", "not_checkout", "timeout"])
def test_code_capture(monkeypatch, mode):
    monkeypatch.delenv("RAG_LAB_CODE_COMMIT", raising=False)
    monkeypatch.setattr(code_version, "get_settings", lambda: SimpleNamespace(code_commit=None))
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        assert kwargs["timeout"] == 2
        if mode == "environment": pytest.fail("Git must not be called")
        if mode == "missing": raise FileNotFoundError()
        if mode == "not_checkout": raise subprocess.CalledProcessError(128, args)
        if mode == "timeout": raise subprocess.TimeoutExpired(args, 2)
        return SimpleNamespace(stdout="b" * 40 if args[1] == "rev-parse" else " M app/main.py" if mode == "dirty" else "")
    monkeypatch.setattr(code_version.subprocess, "run", run)
    if mode == "environment": monkeypatch.setenv("RAG_LAB_CODE_COMMIT", "deployed-sha")
    result = code_version.capture_code_version()
    if mode == "environment": assert result == {"commit": "deployed-sha", "dirty": None, "commit_source": "environment"}
    elif mode in {"missing", "not_checkout", "timeout"}: assert result == {"commit": None, "dirty": None, "commit_source": "unavailable"}
    else: assert result == {"commit": "b" * 40, "dirty": mode == "dirty", "commit_source": "git"}


def test_code_revision_can_come_from_environment_file_settings(monkeypatch):
    monkeypatch.delenv("RAG_LAB_CODE_COMMIT", raising=False)
    monkeypatch.setattr(code_version, "get_settings", lambda: SimpleNamespace(code_commit="deployment-sha"))
    monkeypatch.setattr(code_version.subprocess, "run", lambda *args, **kwargs: pytest.fail("Git accessed"))
    assert code_version.capture_code_version() == {
        "commit": "deployment-sha", "dirty": None, "commit_source": "environment",
    }


@pytest.mark.parametrize("target,field", [
    ("gt", "canonical_sha256"), ("chunks", "chunks_file_sha256"), ("index", "input_chunks_sha256"),
    ("index", "sparse_stats_sha256"), ("index", "build_id"),
])
def test_unverified_inputs_are_rejected_without_legacy_fallback(pipeline, target, field):
    p = pipeline
    record_info = {"gt": p.gt, "chunks": p.chunks, "index": p.index}[target]
    model = models.GroundTruthSet if target == "gt" else models.DerivedCache
    session_generator = app.dependency_overrides[get_db]()
    db = next(session_generator)
    try:
        record = db.get(model, record_info["id"])
        metadata = dict(record.metadata_json)
        del metadata[field]
        record.metadata_json = metadata
        db.commit()
    finally:
        session_generator.close()
    response = p.client.post(p.base + "/saved-experiments", json=p.choices())
    assert response.status_code == 400
    assert "rebuild" in response.text.lower() or "re-import" in response.text.lower()


@pytest.mark.parametrize("change", ["status", "project", "type", "chunks", "manifest", "source", "hash"])
def test_creation_validates_index_and_historical_lineage(pipeline, change):
    p = pipeline
    sessions = app.dependency_overrides[get_db]()
    db = next(sessions)
    try:
        record = db.get(models.DerivedCache, p.index["id"])
        metadata = deepcopy(record.metadata_json)
        if change == "status": record.status = "failed"
        elif change == "project": record.project_id = "different-project"
        elif change == "type": record.cache_type = "chunks"
        elif change == "chunks": metadata["chunks_cache_id"] = "missing"
        elif change == "manifest": metadata["data_asset_manifest_hash"] = "wrong"
        elif change == "hash": metadata["input_chunks_sha256"] = "wrong"
        else:
            manifest = db.query(models.DataAssetManifest).filter_by(data_asset_id=p.source["id"]).one()
            db.delete(manifest)
        record.metadata_json = metadata
        db.commit()
    finally:
        sessions.close()
    assert p.client.post(p.base + "/saved-experiments", json=p.choices()).status_code == 400


def test_runtime_failure_is_consumed_and_no_git_does_not_break_evaluation(pipeline):
    p = pipeline
    p.monkeypatch.delenv("RAG_LAB_CODE_COMMIT", raising=False)
    p.monkeypatch.setattr(code_version, "get_settings", lambda: SimpleNamespace(code_commit=None))
    def no_git(*args, **kwargs):
        raise FileNotFoundError()
    p.monkeypatch.setattr(code_version.subprocess, "run", no_git)
    success = p.evaluate(p.create())
    assert success.status_code == 200
    assert success.json()["code_commit"] is None
    assert success.json()["metrics_summary_json"]["evaluation"]["code"]["commit_source"] == "unavailable"
    experiment = p.create()
    def failed_model(snapshot):
        raise RuntimeError("Model initialization failed")
    p.monkeypatch.setattr(runtime_cache, "create_embedder_from_snapshot", failed_model)
    assert p.evaluate(experiment).status_code == 502
    failed = p.get(experiment)
    assert failed["status"] == "failed"
    assert p.evaluate(experiment).status_code == 409
    assert p.get(experiment) == failed


def test_resolved_model_factories_ignore_catalogs(monkeypatch):
    from app.services import embeddings, rerankers
    embedding = runtime_cache.build_embedding_snapshot("intfloat_multilingual_e5_small")["embedding"]
    reranker = runtime_cache.build_reranking_snapshot("ms_marco_minilm_l6_v2", {"batch_size": "2"})["reranking"]
    monkeypatch.setattr(embeddings, "get_embedding_model", lambda *args: pytest.fail("Catalog accessed"))
    monkeypatch.setattr(rerankers, "get_reranker_model", lambda *args: pytest.fail("Catalog accessed"))
    captured = []
    def capture(spec, params):
        captured.append((spec, params))
        return object()
    monkeypatch.setattr(embeddings, "_cached_sentence_transformer_embedder", capture)
    monkeypatch.setattr(rerankers, "_cached_cross_encoder_reranker", capture)
    embeddings.create_embedder_from_snapshot(embedding)
    rerankers.create_reranker_from_snapshot(reranker)
    assert captured[0][0].query_prefix == embedding["query_prefix"]
    assert captured[0][0].model_name == embedding["model"]
    assert captured[1][0].model_name == reranker["model"]
    assert captured[1][1]["batch_size"] == 2


def test_qdrant_adapter_refuses_existing_physical_collection(monkeypatch):
    from app.adapters.vectorstores.qdrant_store import QdrantVectorStore
    monkeypatch.setattr("app.adapters.vectorstores.qdrant_store.httpx.get", lambda *args, **kwargs: SimpleNamespace(status_code=200))
    monkeypatch.setattr("app.adapters.vectorstores.qdrant_store.httpx.put", lambda *args, **kwargs: pytest.fail("Existing collection written"))
    with pytest.raises(ValueError, match="already exists"):
        QdrantVectorStore("http://synthetic").ensure_collection(collection_name="existing", vector_size=384)


def test_concurrent_evaluate_claim(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'concurrent.sqlite').as_posix()}", connect_args={"check_same_thread": False})
    sessions = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    def db_override():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = db_override
    barrier = Barrier(2)
    try:
        with TestClient(app) as client:
            p = Pipeline(client, monkeypatch, tmp_path)
            experiment = p.create()
            from app.api import projects
            read_experiment = projects._get_saved_experiment_or_404
            def simultaneous_read(*args):
                record = read_experiment(*args)
                assert record.status == "created"
                barrier.wait(timeout=10)
                return record
            monkeypatch.setattr(projects, "_get_saved_experiment_or_404", simultaneous_read)
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(p.evaluate, experiment)
                second = pool.submit(p.evaluate, experiment)
                responses = [first.result(timeout=15), second.result(timeout=15)]
            assert sorted(response.status_code for response in responses) == [200, 409]
            assert len(p.store.calls) == 4  # two queries, dense + sparse; one evaluation
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize("operation", ["mutate", "remove"])
def test_prepared_input_drift_cannot_create_ready_chunks(pipeline, operation):
    p = pipeline
    snapshot = p.create()["params_snapshot_json"]
    path = Path(p.prepared["storage_path"]) / snapshot["data"]["prepared"]["files"][0]["stored_path"]
    before = p.client.get(p.base + "/derived-cache").json()
    if operation == "mutate":
        path.write_bytes(b"different prepared input")
    else:
        path.unlink()
    response = p.client.post(p.base + "/chunks/materialize", json={
        "data_asset_id": p.prepared["id"], "chunking": {"strategy": "recursive"}})
    assert response.status_code == 400
    assert p.client.get(p.base + "/derived-cache").json() == before


def test_materialization_consumes_one_verified_buffer(pipeline):
    p = pipeline
    snapshot = p.create()["params_snapshot_json"]
    path = Path(p.prepared["storage_path"]) / snapshot["data"]["prepared"]["files"][0]["stored_path"]
    read = Path.read_bytes
    reads = []
    def capture(file):
        content = read(file)
        if file == path:
            reads.append(content)
            file.unlink()
        return content
    p.monkeypatch.setattr(Path, "read_bytes", capture)
    chunks, index = p.build()
    assert len(reads) == 1
    assert chunks["metadata_json"]["chunks_file_sha256"] == hashlib.sha256(read(Path(chunks["metadata_json"]["chunks_path"]))).hexdigest()
    assert index["metadata_json"]["input_chunks_sha256"] == chunks["metadata_json"]["chunks_file_sha256"]


@pytest.mark.parametrize("method", ["pymupdf_text", "docling"])
@pytest.mark.parametrize("operation", ["mutate", "remove"])
def test_source_drift_fails_before_conversion(pipeline, method, operation):
    from app.services import preparation
    p = pipeline
    snapshot = p.create()["params_snapshot_json"]
    path = Path(p.source["storage_path"]) / snapshot["data"]["source"]["files"][0]["stored_path"]
    if operation == "mutate": path.write_bytes(b"different source")
    else: path.unlink()
    p.monkeypatch.setattr(preparation, "_text_file_to_markdown", lambda *a, **kw: pytest.fail("Unverified input processed"))
    p.monkeypatch.setattr(preparation, "_convert_with_docling_async", lambda **kw: pytest.fail("Unverified input submitted"))
    response = p.client.post(p.base + f"/data-assets/{p.source['id']}/prepare", json={"method_id": method, "params": {"base_url": "http://synthetic"}})
    assert response.status_code == 400
    assert "Source input" in response.text


@pytest.mark.parametrize("instruction", ["Use this instruction", ""])
def test_reranker_never_drops_requested_prompt(monkeypatch, instruction):
    from app.services import rerankers
    snapshot = runtime_cache.build_reranking_snapshot("qwen3_reranker_0_6b", {"instruction": instruction})["reranking"]
    calls = []
    def backend(model, **kwargs):
        calls.append(kwargs)
        if "prompts" in kwargs: raise TypeError("Unsupported prompts")
        return object()
    monkeypatch.setitem(__import__("sys").modules, "sentence_transformers", SimpleNamespace(CrossEncoder=backend))
    monkeypatch.setattr(rerankers, "_LOCAL_RERANKER_CACHE", {})
    if instruction:
        with pytest.raises(ValueError, match="resolved configuration"):
            rerankers.create_reranker_from_snapshot(snapshot)
    else:
        rerankers.create_reranker_from_snapshot(snapshot)
    assert len(calls) == 1


@pytest.mark.parametrize("params", [{"batch_size": 1001}, {"batch_size": 0}, {"timeout_seconds": 601}, {"timeout_seconds": 0}])
def test_embedding_resolution_rejects_out_of_range_before_snapshot(params):
    with pytest.raises(ValueError):
        runtime_cache.build_embedding_snapshot("voyage_4_lite", params)


def test_voyage_executes_saved_batch_size(monkeypatch):
    from app.services import embeddings
    snapshot = runtime_cache.build_embedding_snapshot("voyage_4_lite", {"batch_size": 1000})["embedding"]
    monkeypatch.setattr(embeddings, "get_settings", lambda: SimpleNamespace(voyage_api_key="synthetic"))
    adapter = embeddings.create_embedder_from_snapshot(snapshot)
    observed = []
    def batches(texts, **kwargs):
        observed.append(kwargs["batch_size"])
        return []
    monkeypatch.setattr(embeddings, "_voyage_batches", batches)
    adapter.embed_passages(["synthetic"])
    assert observed == [snapshot["params"]["batch_size"]] == [1000]


@pytest.mark.parametrize("kind", ["text", "pdf", "docling"])
def test_preparation_consumes_verified_buffer_after_source_removed(tmp_path, monkeypatch, kind):
    from app.services import preparation
    import base64
    if kind == "pdf":
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Verified source text")
        content = doc.tobytes()
        doc.close()
    else:
        content = b"Verified source text\r\n"
    filename = "source.pdf" if kind == "pdf" else "source.txt"
    path = tmp_path / filename
    path.write_bytes(content)
    manifest = {"files": [{"stored_path": filename, "original_name": filename,
                            "sha256": hashlib.sha256(content).hexdigest()}]}
    read = Path.read_bytes
    calls = []
    def once(file):
        result = read(file)
        if file == path:
            calls.append(result)
            file.unlink()
        return result
    monkeypatch.setattr(Path, "read_bytes", once)
    if kind == "docling":
        class Client:
            def __init__(self, **kw): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def post(self, url, json):
                assert base64.b64decode(json["sources"][0]["base64_string"]) == content
                return SimpleNamespace(raise_for_status=lambda: None,
                    json=lambda: {"document": {"md_content": "Verified source text"}})
        monkeypatch.setattr(preparation.httpx, "Client", Client)
        output = preparation.prepare_docling(source_storage_path=str(tmp_path), source_manifest=manifest)
    else:
        output = preparation.prepare_pymupdf_text(source_storage_path=str(tmp_path), source_manifest=manifest)
    assert calls == [content]
    assert b"Verified source text" in output[0]["content"]


def test_chunking_verifies_only_selected_strategy_inputs(tmp_path):
    from app.services.chunking import ChunkingParams, chunk_prepared_asset
    path = tmp_path / "document.md"
    content = b"Selected Markdown input"
    path.write_bytes(content)
    manifest = {"files": [
        {"stored_path": path.name, "original_name": path.name, "sha256": hashlib.sha256(content).hexdigest()},
        {"stored_path": "missing.pages.jsonl", "original_name": "missing.pages.jsonl", "role": "prepared_parent_pages"},
        {"stored_path": "missing.json", "original_name": "missing.json", "role": "docling_document_json"},
    ]}
    result = chunk_prepared_asset(storage_path=str(tmp_path), manifest_json=manifest,
                                 chunking=ChunkingParams(strategy="recursive"))
    assert result["chunks"][0]["text"] == content.decode()
