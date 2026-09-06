"""Backend-owned pipeline configuration and compact historical data references."""
from copy import deepcopy
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.models.api import SavedExperimentCreate
from app.services.ground_truth import read_canonical_ground_truth
from app.services.hashing import read_verified_bytes, stable_sha256
from app.services.runtime_cache import build_reranking_snapshot, read_chunks_cache
from app.services.semantics import EVALUATION_VERSION, RETRIEVAL_VERSION, SNAPSHOT_VERSION


def required(metadata: dict, *keys: str) -> None:
    for key in keys:
        if key not in metadata or metadata[key] is None:
            raise ValueError(f"Missing verified lineage field {key}; rebuild or re-import the input")


def ready_cache(db: Session, project_id: str, cache_id: str, cache_type: str) -> models.DerivedCache:
    cache = db.get(models.DerivedCache, cache_id)
    if cache is None or cache.project_id != project_id or cache.cache_type != cache_type:
        raise ValueError(f"Invalid project {cache_type} cache")
    if cache.status != "ready":
        raise ValueError(f"{cache_type} cache must be ready")
    return cache


def historical_manifest(db: Session, project_id: str, asset_id: str, manifest_hash: str,
                        asset_type: str) -> models.DataAssetManifest:
    asset = db.get(models.DataAsset, asset_id)
    if asset is None or asset.project_id != project_id or asset.asset_type != asset_type:
        raise ValueError(f"Invalid {asset_type} data lineage")
    manifest = db.scalar(select(models.DataAssetManifest).where(
        models.DataAssetManifest.data_asset_id == asset_id,
        models.DataAssetManifest.manifest_hash == manifest_hash,
    ))
    if manifest is None:
        raise ValueError(f"Historical {asset_type} manifest is unavailable")
    return manifest


def manifest_snapshot(manifest: models.DataAssetManifest) -> dict:
    fields = ("stored_path", "original_name", "sha256", "size_bytes", "role", "source", "content_type")
    files = manifest.manifest_json.get("files", [])
    if not files:
        raise ValueError("Historical manifest has no files")
    for file in files:
        required(file, "stored_path", "original_name", "sha256", "size_bytes")
    return {
        "asset_id": manifest.data_asset_id, "manifest_id": manifest.id,
        "manifest_hash": manifest.manifest_hash,
        "files": [{key: deepcopy(file[key]) for key in fields if key in file} for file in files],
    }


def resolve_retrieval(params: dict[str, Any], index_mode: str) -> dict[str, Any]:
    result = deepcopy(params)
    if result["mode"] in {"sparse", "hybrid"} and index_mode == "dense":
        raise ValueError("Selected index does not include sparse vectors")
    top_k = result["top_k"]
    candidates = result["candidate_k"] or (top_k * 5 if result["mode"] == "hybrid" else top_k)
    result["effective_candidate_k"] = min(100, max(top_k, candidates))
    result["fusion"] = "rrf" if result["mode"] == "hybrid" else None
    result["rrf_k"] = 60 if result["mode"] == "hybrid" else None
    result["parent_restoration"] = None
    if result["strategy"] != "chunk_retrieval":
        result["parent_restoration"] = {
            "text_source": "chunks.parent_text", "preview_chars": 1200,
            "chapter_page_fallback": result["strategy"] == "parent_chapter_retrieval",
        }
    return result


def build_experiment_snapshot(db: Session, project_id: str, request: SavedExperimentCreate) -> dict:
    index = ready_cache(db, project_id, request.index_cache_id, "qdrant_index")
    im = index.metadata_json
    required(im, "build_id", "input_chunks_sha256", "chunks_cache_id", "chunks_cache_key",
             "data_asset_manifest_hash", "data_asset_id", "embedding", "collection_name",
             "index_mode", "distance", "params_hash", "chunk_count")
    if im["build_id"] != index.id:
        raise ValueError("Index build identity mismatch; rebuild index")
    chunks = ready_cache(db, project_id, im["chunks_cache_id"], "chunks")
    cm, content = read_chunks_cache(chunks)
    required(cm, "chunks_file_sha256", "chunk_count", "size_unit", "data_asset_manifest_hash", "chunking")
    if (cm["chunks_file_sha256"] != im["input_chunks_sha256"] or len(content) != cm["chunk_count"]
            or chunks.cache_key != im["chunks_cache_key"] or index.data_asset_id != chunks.data_asset_id
            or im["data_asset_manifest_hash"] != cm["data_asset_manifest_hash"]
            or im["data_asset_id"] != chunks.data_asset_id or cm.get("data_asset_id") != chunks.data_asset_id
            or im["chunk_count"] != len(content) or im["params_hash"] != index.params_hash):
        raise ValueError("Index and chunks lineage do not match; rebuild index")
    prepared = historical_manifest(db, project_id, chunks.data_asset_id,
                                   cm["data_asset_manifest_hash"], "prepared")
    pm = prepared.manifest_json
    required(pm, "parent_id", "preparation_params_json")
    preparation = deepcopy(pm["preparation_params_json"])
    required(preparation, "source_manifest_hash", "params")
    if not (preparation.get("method_id") or preparation.get("method")):
        raise ValueError("Preparation method is missing")
    source = historical_manifest(db, project_id, pm["parent_id"], preparation["source_manifest_hash"], "raw")
    gt = db.get(models.GroundTruthSet, request.ground_truth_set_id)
    if gt is None or gt.project_id != project_id:
        raise ValueError("Invalid project ground truth set")
    if gt.data_asset_id is not None and gt.data_asset_id != chunks.data_asset_id:
        raise ValueError("Ground truth is linked to different prepared data")
    canonical = read_canonical_ground_truth(gt)
    sparse = None
    if im["index_mode"] in {"sparse", "hybrid"}:
        required(im, "sparse", "sparse_stats_path", "sparse_stats_sha256")
        stats = json.loads(read_verified_bytes(im["sparse_stats_path"], im["sparse_stats_sha256"], "BM25 statistics"))
        if stats["params"] != im["sparse"]["params"] or stats["doc_count"] != len(content):
            raise ValueError("Sparse statistics do not match the index configuration")
        sparse = {**deepcopy(im["sparse"]), "stats_file_sha256": im["sparse_stats_sha256"],
                  "schema_version": stats["schema_version"]}
    retrieval = resolve_retrieval(request.retrieval.model_dump(), im["index_mode"])
    reranking = None
    if request.reranking and request.reranking.enabled:
        reranking = build_reranking_snapshot(request.reranking.model_id, request.reranking.params)["reranking"]
        reranking["text_input"] = "full_chunk_text" if retrieval["strategy"] == "chunk_retrieval" else "parent_preview_1200_chars"
    required(im["embedding"], "provider", "model_id", "model", "params", "vector_size", "passage_prefix", "query_prefix")
    metadata = canonical.get("metadata", {})
    return {
        "schema_version": SNAPSHOT_VERSION,
        "data": {"source": manifest_snapshot(source), "prepared": manifest_snapshot(prepared), "preparation": preparation},
        "chunking": {**deepcopy(cm["chunking"]), "cache_id": chunks.id, "cache_key": chunks.cache_key,
                     "size_unit": cm["size_unit"], "chunks_file_sha256": cm["chunks_file_sha256"], "chunk_count": cm["chunk_count"]},
        "embedding": deepcopy(im["embedding"]), "sparse": sparse,
        "index": {"cache_id": index.id, "cache_key": index.cache_key, "collection_name": im["collection_name"],
                  "mode": im["index_mode"], "distance": im["distance"], "params_hash": index.params_hash,
                  "input_chunks_sha256": im["input_chunks_sha256"]},
        "retrieval": retrieval, "reranking": reranking,
        "ground_truth": {"ground_truth_set_id": gt.id, "manifest_hash": gt.manifest_hash,
                         "canonical_sha256": gt.metadata_json["canonical_sha256"],
                         "schema_version": canonical["schema_version"],
                         "ground_truth_type": metadata.get("ground_truth_type", "chunk_level_qrels"),
                         "question_count": len(canonical["questions"]),
                         "annotation_schema_version": metadata.get("annotation_schema_version"),
                         "annotation_version": metadata.get("annotation_version"),
                         "evaluation_slices": deepcopy(canonical.get("evaluation_slices", []))},
        "semantics": {"retrieval_version": RETRIEVAL_VERSION, "evaluation_version": EVALUATION_VERSION},
    }


def pipeline_params_hash(snapshot: dict) -> str:
    """Hash parameter choices only. IDs, content hashes, GT population and code are separate."""
    preparation = snapshot["data"]["preparation"]
    return stable_sha256({
        "preparation": {key: preparation[key] for key in (
            "method_id", "method", "tool", "source_format", "output_format", "output_formats", "params", "service"
        ) if key in preparation},
        "chunking": {key: snapshot["chunking"][key] for key in ("strategy", "params", "size_unit")},
        "embedding": snapshot["embedding"],
        "sparse": {key: value for key, value in snapshot["sparse"].items()
                   if key != "stats_file_sha256"} if snapshot["sparse"] else None,
        "index": {key: snapshot["index"][key] for key in ("mode", "distance")},
        "retrieval": {key: value for key, value in snapshot["retrieval"].items() if key != "candidate_k"},
        "reranking": snapshot["reranking"],
        "evaluation": {"ground_truth_type": snapshot["ground_truth"]["ground_truth_type"]},
        "semantics": snapshot["semantics"],
    })
