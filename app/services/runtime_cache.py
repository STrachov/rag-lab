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

PIPELINE_VERSION = "runtime-v1"


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
            "pipeline_version": PIPELINE_VERSION,
        }
    )
    cache_key = f"qdrant_{short_hash(params_hash, 20)}"
    collection = collection_name or f"raglab_{cache_key}"
    embedder = create_embedder(embedding["model_id"], embedding["params"])
    texts = [str(chunk["text"]) for chunk in chunks]
    vectors = embedder.embed_passages(texts) if texts else []

    vector_store.ensure_collection(
        collection_name=collection,
        distance=distance,
        vector_size=int(embedding["vector_size"]),
    )
    points = [
        {
            "id": _point_id(str(chunk["chunk_id"])),
            "payload": {key: value for key, value in chunk.items() if key != "text"},
            "vector": vector,
        }
        for chunk, vector in zip(chunks, vectors, strict=True)
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
        "params_hash": params_hash,
        "pipeline_version": PIPELINE_VERSION,
        "qdrant_url": get_settings().qdrant_url,
        "schema_version": "raglab.qdrant_index.v1",
    }
    return {"cache_key": cache_key, "metadata_json": metadata, "params_hash": params_hash}


def retrieve_from_qdrant(
    *,
    index_cache: models.DerivedCache,
    query: str,
    top_k: int,
    vector_store: Any,
) -> dict[str, Any]:
    metadata = index_cache.metadata_json
    embedding = metadata["embedding"]
    embedder = create_embedder(embedding["model_id"], embedding["params"])
    query_vector = embedder.embed_query(query)
    results = vector_store.search(
        collection_name=str(metadata["collection_name"]),
        query_vector=query_vector,
        top_k=top_k,
    )
    retrieved = [
        {
            "chunk_id": result.get("payload", {}).get("chunk_id"),
            "score": result.get("score"),
            **dict(result.get("payload") or {}),
        }
        for result in results
    ]
    return {
        "index_cache_id": index_cache.id,
        "query": query,
        "retrieved_chunks": retrieved,
        "top_k": top_k,
    }


def _cache_root() -> Path:
    return get_settings().data_dir / "cache"


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
