from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.vectorstores.qdrant_store import QdrantVectorStore
from app.core.config import get_settings
from app.db import models
from app.db.session import get_db
from app.models.api import (
    ChunkMaterializeRequest,
    DerivedCacheResponse,
    EmbeddingModelListResponse,
    QdrantIndexRequest,
    RetrievalPreviewRequest,
    RetrievalPreviewResponse,
)
from app.services.embeddings import list_embedding_models
from app.services.runtime_cache import (
    build_chunking_snapshot,
    build_embedding_snapshot,
    index_chunks_in_qdrant,
    materialize_chunks,
    retrieve_from_qdrant,
)

router = APIRouter()


@router.get(
    "/projects/{project_id}/embedding/models",
    response_model=EmbeddingModelListResponse,
)
def list_project_embedding_models(
    project_id: str,
    db: Session = Depends(get_db),
) -> EmbeddingModelListResponse:
    _get_project_or_404(db, project_id)
    return EmbeddingModelListResponse.model_validate({"models": list_embedding_models()})


@router.post(
    "/projects/{project_id}/chunks/materialize",
    response_model=DerivedCacheResponse,
    status_code=status.HTTP_201_CREATED,
)
def materialize_project_chunks(
    project_id: str,
    payload: ChunkMaterializeRequest,
    db: Session = Depends(get_db),
) -> models.DerivedCache:
    _get_project_or_404(db, project_id)
    data_asset = _get_data_asset_or_404(db, project_id, payload.data_asset_id)
    _require_data_asset_type(data_asset, "prepared")
    manifest_json = _get_current_manifest_json(db, data_asset)

    try:
        chunking_snapshot = build_chunking_snapshot(payload.chunking.model_dump())
        materialized = materialize_chunks(
            project_id=project_id,
            data_asset=data_asset,
            manifest_json=manifest_json,
            chunking_snapshot=chunking_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_cache = _find_cache(
        db,
        project_id=project_id,
        cache_type="chunks",
        cache_key=materialized["cache_key"],
    )
    if existing_cache is not None:
        existing_cache.last_used_at = datetime.now(UTC)
        existing_cache.metadata_json = materialized["metadata_json"]
        existing_cache.params_hash = materialized["params_hash"]
        db.commit()
        db.refresh(existing_cache)
        return existing_cache

    cache = models.DerivedCache(
        project_id=project_id,
        data_asset_id=data_asset.id,
        params_hash=materialized["params_hash"],
        cache_type="chunks",
        cache_key=materialized["cache_key"],
        status="ready",
        metadata_json=materialized["metadata_json"],
        last_used_at=datetime.now(UTC),
    )
    db.add(cache)
    db.commit()
    db.refresh(cache)
    return cache


@router.post(
    "/projects/{project_id}/indexes/qdrant",
    response_model=DerivedCacheResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_qdrant_index(
    project_id: str,
    payload: QdrantIndexRequest,
    db: Session = Depends(get_db),
) -> models.DerivedCache:
    _get_project_or_404(db, project_id)
    chunks_cache = _get_cache_or_404(db, project_id, payload.chunks_cache_id)
    if chunks_cache.cache_type != "chunks":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chunks_cache_id must reference a chunks cache",
        )

    try:
        embedding_snapshot = build_embedding_snapshot(
            payload.embedding.model_id,
            payload.embedding.params,
        )
        indexed = index_chunks_in_qdrant(
            chunks_cache=chunks_cache,
            collection_name=payload.collection_name,
            distance=payload.distance,
            embedding_snapshot=embedding_snapshot,
            vector_store=_qdrant_store(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_cache = _find_cache(
        db,
        project_id=project_id,
        cache_type="qdrant_index",
        cache_key=indexed["cache_key"],
    )
    if existing_cache is not None:
        existing_cache.last_used_at = datetime.now(UTC)
        existing_cache.metadata_json = indexed["metadata_json"]
        existing_cache.params_hash = indexed["params_hash"]
        existing_cache.status = "ready"
        db.commit()
        db.refresh(existing_cache)
        return existing_cache

    cache = models.DerivedCache(
        project_id=project_id,
        data_asset_id=chunks_cache.data_asset_id,
        params_hash=indexed["params_hash"],
        cache_type="qdrant_index",
        cache_key=indexed["cache_key"],
        status="ready",
        metadata_json=indexed["metadata_json"],
        last_used_at=datetime.now(UTC),
    )
    db.add(cache)
    db.commit()
    db.refresh(cache)
    return cache


@router.post(
    "/projects/{project_id}/retrieve/preview",
    response_model=RetrievalPreviewResponse,
)
def preview_project_retrieval(
    project_id: str,
    payload: RetrievalPreviewRequest,
    db: Session = Depends(get_db),
) -> RetrievalPreviewResponse:
    _get_project_or_404(db, project_id)
    index_cache = _get_cache_or_404(db, project_id, payload.index_cache_id)
    if index_cache.cache_type != "qdrant_index":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="index_cache_id must reference a qdrant_index cache",
        )
    try:
        result = retrieve_from_qdrant(
            index_cache=index_cache,
            query=payload.query,
            top_k=payload.top_k,
            vector_store=_qdrant_store(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    index_cache.last_used_at = datetime.now(UTC)
    db.commit()
    return RetrievalPreviewResponse.model_validate(result)


def _qdrant_store() -> QdrantVectorStore:
    return QdrantVectorStore(get_settings().qdrant_url)


def _get_project_or_404(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_data_asset_or_404(db: Session, project_id: str, data_asset_id: str) -> models.DataAsset:
    asset = db.get(models.DataAsset, data_asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data asset not found")
    return asset


def _require_data_asset_type(asset: models.DataAsset, asset_type: str) -> None:
    if asset.asset_type != asset_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data asset must be {asset_type}",
        )


def _get_current_manifest_json(db: Session, asset: models.DataAsset) -> dict:
    if asset.manifest_hash is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data asset has no current manifest",
        )
    manifest = db.scalar(
        select(models.DataAssetManifest)
        .where(models.DataAssetManifest.data_asset_id == asset.id)
        .where(models.DataAssetManifest.manifest_hash == asset.manifest_hash)
        .order_by(models.DataAssetManifest.created_at.desc())
    )
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current data asset manifest snapshot not found",
        )
    return manifest.manifest_json


def _get_cache_or_404(db: Session, project_id: str, cache_id: str) -> models.DerivedCache:
    cache = db.get(models.DerivedCache, cache_id)
    if cache is None or cache.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Derived cache not found")
    return cache


def _find_cache(
    db: Session,
    *,
    project_id: str,
    cache_type: str,
    cache_key: str,
) -> models.DerivedCache | None:
    return db.scalar(
        select(models.DerivedCache)
        .where(models.DerivedCache.project_id == project_id)
        .where(models.DerivedCache.cache_type == cache_type)
        .where(models.DerivedCache.cache_key == cache_key)
    )
