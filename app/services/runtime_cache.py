from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db import models
from app.services.chunking import ChunkingParams, chunk_prepared_asset
from app.services.embeddings import (
    create_embedder,
    get_embedding_model,
    normalize_embedding_params,
)
from app.services.hashing import short_hash, stable_json_dumps, stable_sha256
from app.services.sparse import (
    build_bm25_stats,
    encode_bm25_document,
    encode_bm25_query,
    get_sparse_model,
    normalize_sparse_params,
)
from app.services.rerankers import (
    get_reranker_model,
    normalize_reranker_params,
    rerank_chunks,
)

PIPELINE_VERSION = "runtime-v1"
RETRIEVAL_TEXT_PREVIEW_CHARS = 1200


def build_chunking_snapshot(chunking: dict[str, Any]) -> dict[str, Any]:
    params = ChunkingParams(**chunking).merged_params()
    return {"chunking": {"params": params, "strategy": chunking["strategy"]}}


def build_embedding_snapshot(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_embedding_model(model_id)
    normalized = normalize_embedding_params(model_id, params)
    return {
        "embedding": {
            "model": spec.model_name,
            "model_id": spec.id,
            "params": normalized,
            "provider": spec.provider,
            "vector_size": spec.vector_size,
        }
    }


def build_sparse_snapshot(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_sparse_model(model_id)
    normalized = normalize_sparse_params(model_id, params)
    return {
        "sparse": {
            "model_id": spec.id,
            "params": normalized,
            "provider": spec.provider,
        }
    }


def build_reranking_snapshot(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_reranker_model(model_id)
    normalized = normalize_reranker_params(model_id, params)
    return {
        "reranking": {
            "backend": spec.backend,
            "model": spec.model_name,
            "model_id": spec.id,
            "params": normalized,
            "provider": spec.provider,
        }
    }


def materialize_chunks(
    *,
    project_id: str,
    data_asset: models.DataAsset,
    manifest_json: dict[str, Any],
    chunking_snapshot: dict[str, Any],
) -> dict[str, Any]:
    if data_asset.storage_path is None:
        raise ValueError("Prepared data asset has no storage path")

    chunking = chunking_snapshot["chunking"]
    params_hash = stable_sha256(chunking_snapshot)
    cache_key = _chunk_cache_key(
        project_id=project_id,
        data_asset_id=data_asset.id,
        manifest_hash=str(data_asset.manifest_hash),
        params_hash=params_hash,
    )
    cache_dir = _cache_root() / "chunks" / cache_key
    cache_dir.mkdir(parents=True, exist_ok=True)

    materialized = chunk_prepared_asset(
        storage_path=data_asset.storage_path,
        manifest_json=manifest_json,
        chunking=ChunkingParams(strategy=chunking["strategy"], params=chunking["params"]),
    )
    chunks = [_normalize_chunk(chunk) for chunk in materialized["chunks"]]
    sidecars = _sidecar_files(manifest_json)
    manifest = {
        "cache_key": cache_key,
        "chunking": chunking,
        "data_asset_id": data_asset.id,
        "data_asset_manifest_hash": data_asset.manifest_hash,
        "params_hash": params_hash,
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": "raglab.chunks.v1",
        "sidecar_files": sidecars,
        "summary": materialized["summary"],
        "warnings": materialized["warnings"],
    }

    (cache_dir / "chunks.jsonl").write_text(
        "".join(f"{stable_json_dumps(chunk)}\n" for chunk in chunks),
        encoding="utf-8",
    )
    (cache_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "cache_key": cache_key,
        "metadata_json": {
            **manifest,
            "chunks_path": str(cache_dir / "chunks.jsonl"),
            "manifest_path": str(cache_dir / "manifest.json"),
        },
        "params_hash": params_hash,
    }


def read_chunks_cache(cache: models.DerivedCache) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata = cache.metadata_json
    chunks_path = Path(str(metadata["chunks_path"]))
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return metadata, chunks


def index_chunks_in_qdrant(
    *,
    chunks_cache: models.DerivedCache,
    embedding_snapshot: dict[str, Any],
    sparse_snapshot: dict[str, Any] | None,
    index_mode: str,
    collection_name: str | None,
    distance: str,
    vector_store: Any,
) -> dict[str, Any]:
    chunks_metadata, chunks = read_chunks_cache(chunks_cache)
    embedding = embedding_snapshot["embedding"]
    params_hash = stable_sha256(
        {
            "chunks_cache_key": chunks_cache.cache_key,
            "collection_name": collection_name,
            "distance": distance,
            "embedding": embedding,
            "index_mode": index_mode,
            "pipeline_version": PIPELINE_VERSION,
            "sparse": sparse_snapshot["sparse"] if sparse_snapshot else None,
        }
    )
    cache_key = f"qdrant_{short_hash(params_hash, 20)}"
    collection = collection_name or f"raglab_{cache_key}"
    embedder = create_embedder(embedding["model_id"], embedding["params"])
    texts = [str(chunk["text"]) for chunk in chunks]
    vectors = embedder.embed_passages(texts) if texts else []
    sparse_stats: dict[str, Any] | None = None
    sparse_stats_path: Path | None = None
    if index_mode in {"sparse", "hybrid"}:
        if sparse_snapshot is None:
            raise ValueError("Sparse settings are required for sparse or hybrid indexes")
        sparse_stats = build_bm25_stats(texts, sparse_snapshot["sparse"]["params"])
        sparse_stats_path = _write_sparse_stats(cache_key, sparse_stats)

    vector_store.ensure_collection(
        collection_name=collection,
        distance=distance,
        sparse=sparse_stats is not None,
        vector_size=int(embedding["vector_size"]),
    )
    points = [
        {
            "id": _point_id(str(chunk["chunk_id"])),
            "payload": _chunk_payload(chunk),
            "vector": _point_vectors(
                dense_vector=vector,
                doc_index=index,
                chunk=chunk,
                sparse_stats=sparse_stats,
            ),
        }
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    if points:
        vector_store.upsert_points(collection_name=collection, points=points)

    metadata = {
        "cache_key": cache_key,
        "chunk_count": len(chunks),
        "chunks_cache_id": chunks_cache.id,
        "chunks_cache_key": chunks_cache.cache_key,
        "collection_name": collection,
        "data_asset_id": chunks_cache.data_asset_id,
        "data_asset_manifest_hash": chunks_metadata.get("data_asset_manifest_hash"),
        "distance": distance,
        "embedding": embedding,
        "index_mode": index_mode,
        "params_hash": params_hash,
        "pipeline_version": PIPELINE_VERSION,
        "qdrant_url": get_settings().qdrant_url,
        "schema_version": "raglab.qdrant_index.v1",
        "sparse": sparse_snapshot["sparse"] if sparse_snapshot else None,
        "sparse_stats_path": str(sparse_stats_path) if sparse_stats_path else None,
    }
    return {"cache_key": cache_key, "metadata_json": metadata, "params_hash": params_hash}


def retrieve_from_qdrant(
    *,
    index_cache: models.DerivedCache,
    candidate_k: int | None = None,
    query: str,
    mode: str,
    reranking_snapshot: dict[str, Any] | None = None,
    top_k: int,
    vector_store: Any,
) -> dict[str, Any]:
    metadata = index_cache.metadata_json
    embedding = metadata["embedding"]
    index_mode = str(metadata.get("index_mode") or "dense")
    if mode in {"sparse", "hybrid"} and index_mode == "dense":
        raise ValueError("Selected index does not include sparse vectors")
    embedder = create_embedder(embedding["model_id"], embedding["params"])
    query_vector = embedder.embed_query(query)
    collection_name = str(metadata["collection_name"])
    base_candidate_k = candidate_k or (top_k * 5 if mode == "hybrid" else top_k)
    effective_candidate_k = min(100, max(top_k, base_candidate_k))
    if mode == "dense":
        retrieved = _format_results(
            vector_store.search_dense(
                collection_name=collection_name,
                query_vector=query_vector,
                top_k=effective_candidate_k,
            ),
            score_key="dense_score",
        )
    elif mode == "sparse":
        sparse_query = _encode_sparse_query(query, metadata)
        retrieved = _format_results(
            vector_store.search_sparse(
                collection_name=collection_name,
                query_vector=sparse_query,
                top_k=effective_candidate_k,
            ),
            score_key="sparse_score",
        )
    else:
        sparse_query = _encode_sparse_query(query, metadata)
        dense_results = vector_store.search_dense(
            collection_name=collection_name,
            query_vector=query_vector,
            top_k=effective_candidate_k,
        )
        sparse_results = vector_store.search_sparse(
            collection_name=collection_name,
            query_vector=sparse_query,
            top_k=effective_candidate_k,
        )
        retrieved = _rrf_merge(dense_results, sparse_results)
    candidate_chunks = retrieved
    if reranking_snapshot is not None:
        reranking = reranking_snapshot["reranking"]
        retrieved = rerank_chunks(
            chunks=retrieved,
            model_id=reranking["model_id"],
            params=reranking["params"],
            query=query,
            text_by_chunk_id=_full_text_by_chunk_id(metadata),
        )
    return {
        "candidate_chunks": candidate_chunks,
        "candidate_k": effective_candidate_k,
        "index_cache_id": index_cache.id,
        "mode": mode,
        "query": query,
        "reranking": reranking_snapshot["reranking"] if reranking_snapshot else None,
        "retrieved_chunks": retrieved[:top_k],
        "top_k": top_k,
    }


def build_retrieval_temp_payload(
    *,
    index_cache: models.DerivedCache,
    query: str,
    mode: str,
    candidate_k: int,
    candidate_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    params_hash = stable_sha256(
        {
            "candidate_k": candidate_k,
            "index_cache_key": index_cache.cache_key,
            "mode": mode,
            "pipeline_version": PIPELINE_VERSION,
            "query": query,
        }
    )
    cache_key = f"retrieval_{short_hash(params_hash, 20)}"
    metadata = {
        "cache_key": cache_key,
        "candidate_k": candidate_k,
        "collection_name": index_cache.metadata_json.get("collection_name"),
        "data_asset_id": index_cache.data_asset_id,
        "index_cache_id": index_cache.id,
        "index_cache_key": index_cache.cache_key,
        "mode": mode,
        "params_hash": params_hash,
        "pipeline_version": PIPELINE_VERSION,
        "query": query,
        "retrieved_chunks": candidate_chunks,
        "schema_version": "raglab.retrieval_temp.v1",
    }
    return {"cache_key": cache_key, "metadata_json": metadata, "params_hash": params_hash}


def rerank_retrieval_candidates(
    *,
    retrieval_cache: models.DerivedCache,
    index_cache: models.DerivedCache,
    reranking_snapshot: dict[str, Any],
    top_k: int,
) -> dict[str, Any]:
    metadata = retrieval_cache.metadata_json
    reranking = reranking_snapshot["reranking"]
    candidate_chunks = list(metadata.get("retrieved_chunks") or [])
    reranked = rerank_chunks(
        chunks=candidate_chunks,
        model_id=reranking["model_id"],
        params=reranking["params"],
        query=str(metadata["query"]),
        text_by_chunk_id=_full_text_by_chunk_id(index_cache.metadata_json),
    )
    return {
        "candidate_k": int(metadata.get("candidate_k") or len(candidate_chunks)),
        "index_cache_id": str(metadata["index_cache_id"]),
        "mode": str(metadata["mode"]),
        "query": str(metadata["query"]),
        "reranking": reranking,
        "retrieval_cache_id": retrieval_cache.id,
        "retrieved_chunks": reranked[:top_k],
        "top_k": top_k,
    }


def _cache_root() -> Path:
    return get_settings().data_dir / "cache"


def _write_sparse_stats(cache_key: str, sparse_stats: dict[str, Any]) -> Path:
    cache_dir = _cache_root() / "sparse" / cache_key
    cache_dir.mkdir(parents=True, exist_ok=True)
    stats_path = cache_dir / "bm25_stats.json"
    stats_path.write_text(json.dumps(sparse_stats, indent=2, sort_keys=True), encoding="utf-8")
    return stats_path


def _chunk_cache_key(
    *,
    project_id: str,
    data_asset_id: str,
    manifest_hash: str,
    params_hash: str,
) -> str:
    return "chunks_" + short_hash(
        stable_sha256(
            {
                "data_asset_id": data_asset_id,
                "manifest_hash": manifest_hash,
                "params_hash": params_hash,
                "pipeline_version": PIPELINE_VERSION,
                "project_id": project_id,
            }
        ),
        20,
    )


def _normalize_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "char_count": int(chunk["char_count"]),
        "chunk_id": str(chunk["chunk_id"]),
        "heading_path": list(chunk.get("heading_path") or []),
        "page": chunk.get("page"),
        "section": chunk.get("section"),
        "source_name": str(chunk["source_name"]),
        "stored_path": str(chunk["stored_path"]),
        "text": str(chunk["text"]),
        "token_count": int(chunk["token_count"]),
    }


def _chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            **{item_key: item_value for item_key, item_value in chunk.items() if item_key != "text"},
            "text_preview": _clip_text(str(chunk["text"]), RETRIEVAL_TEXT_PREVIEW_CHARS),
        }.items()
        if value is not None
    }


def _point_vectors(
    *,
    dense_vector: list[float],
    doc_index: int,
    chunk: dict[str, Any],
    sparse_stats: dict[str, Any] | None,
) -> dict[str, Any]:
    vectors: dict[str, Any] = {"dense": dense_vector}
    if sparse_stats is not None:
        vectors["sparse"] = encode_bm25_document(str(chunk["text"]), sparse_stats, doc_index)
    return vectors


def _encode_sparse_query(query: str, metadata: dict[str, Any]) -> dict[str, list[float] | list[int]]:
    stats_path = metadata.get("sparse_stats_path")
    if not stats_path:
        raise ValueError("Selected index does not include sparse statistics")
    sparse_stats = json.loads(Path(str(stats_path)).read_text(encoding="utf-8"))
    return encode_bm25_query(query, sparse_stats)


def _full_text_by_chunk_id(metadata: dict[str, Any]) -> dict[str, str]:
    chunks_cache_key = metadata.get("chunks_cache_key")
    if not chunks_cache_key:
        return {}
    chunks_path = _cache_root() / "chunks" / str(chunks_cache_key) / "chunks.jsonl"
    if not chunks_path.exists():
        return {}
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {str(chunk["chunk_id"]): str(chunk["text"]) for chunk in chunks}


def _format_results(results: list[dict[str, Any]], *, score_key: str) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for result in results:
        payload = dict(result.get("payload") or {})
        score = result.get("score")
        formatted.append(
            {
                "chunk_id": payload.get("chunk_id"),
                "score": score,
                score_key: score,
                **payload,
            }
        )
    return formatted


def _rrf_merge(
    dense_results: list[dict[str, Any]],
    sparse_results: list[dict[str, Any]],
    *,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rank, result in enumerate(dense_results, start=1):
        payload = dict(result.get("payload") or {})
        chunk_id = str(payload.get("chunk_id") or result.get("id"))
        item = merged.setdefault(
            chunk_id,
            {"chunk_id": chunk_id, "payload": payload, "score": 0.0},
        )
        item["dense_score"] = result.get("score")
        item["score"] += 1.0 / (rrf_k + rank)

    for rank, result in enumerate(sparse_results, start=1):
        payload = dict(result.get("payload") or {})
        chunk_id = str(payload.get("chunk_id") or result.get("id"))
        item = merged.setdefault(
            chunk_id,
            {"chunk_id": chunk_id, "payload": payload, "score": 0.0},
        )
        item["payload"] = {**item["payload"], **payload}
        item["sparse_score"] = result.get("score")
        item["score"] += 1.0 / (rrf_k + rank)

    return [
        {
            "chunk_id": item["chunk_id"],
            "dense_score": item.get("dense_score"),
            "score": item["score"],
            "sparse_score": item.get("sparse_score"),
            **item["payload"],
        }
        for item in sorted(merged.values(), key=lambda value: value["score"], reverse=True)
    ]


def _clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _sidecar_files(manifest_json: dict[str, Any]) -> list[dict[str, Any]]:
    sidecars: list[dict[str, Any]] = []
    for file_entry in manifest_json.get("files", []):
        role = str(file_entry.get("role") or "")
        original_name = str(file_entry.get("original_name") or "")
        if role == "docling_document_json" or original_name.endswith(".docling.json"):
            sidecars.append(
                {
                    "content_type": file_entry.get("content_type"),
                    "original_name": original_name,
                    "role": role or "docling_document_json",
                    "sha256": file_entry.get("sha256"),
                    "stored_path": file_entry.get("stored_path"),
                }
            )
    return sidecars


def _point_id(chunk_id: str) -> str:
    digest = stable_sha256(chunk_id).replace("sha256:", "")
    return str(uuid.UUID(hex=digest[:32]))
