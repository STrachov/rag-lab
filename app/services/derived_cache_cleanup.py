from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models


def collect_derived_caches_for_data_assets(
    db: Session,
    project_id: str,
    data_asset_ids: list[str],
) -> list[models.DerivedCache]:
    if not data_asset_ids:
        return []
    return db.scalars(
        select(models.DerivedCache)
        .where(models.DerivedCache.project_id == project_id)
        .where(models.DerivedCache.data_asset_id.in_(data_asset_ids))
    ).all()


def collect_derived_cache_dependents(
    db: Session,
    project_id: str,
    cache: models.DerivedCache,
) -> list[models.DerivedCache]:
    caches = db.scalars(
        select(models.DerivedCache).where(models.DerivedCache.project_id == project_id)
    ).all()
    by_id: dict[str, models.DerivedCache] = {cache.id: cache}
    queue = [cache]
    while queue:
        current = queue.pop(0)
        for candidate in caches:
            if candidate.id in by_id:
                continue
            if _depends_on_cache(candidate, current):
                by_id[candidate.id] = candidate
                queue.append(candidate)
    return [item for item in by_id.values() if item.id != cache.id]


def order_derived_caches_for_delete(
    caches: list[models.DerivedCache],
) -> list[models.DerivedCache]:
    priority = {
        "answer_temp": 0,
        "retrieval_temp": 1,
        "qdrant_index": 2,
        "embeddings": 3,
        "chunks": 4,
    }
    return sorted(caches, key=lambda cache: priority.get(cache.cache_type, 10))


def delete_derived_cache_storage(cache: models.DerivedCache) -> None:
    for path in _derived_cache_storage_paths(cache):
        _delete_cache_path(path)


def _depends_on_cache(candidate: models.DerivedCache, dependency: models.DerivedCache) -> bool:
    metadata = candidate.metadata_json or {}
    dependency_keys = {
        "chunks": ("chunks_cache_id", "chunks_cache_key"),
        "qdrant_index": ("index_cache_id", "index_cache_key"),
        "retrieval_temp": ("retrieval_cache_id", "retrieval_cache_key"),
    }.get(dependency.cache_type, ())
    if not dependency_keys:
        return False
    id_key, key_key = dependency_keys
    return (
        str(metadata.get(id_key) or "") == dependency.id
        or str(metadata.get(key_key) or "") == dependency.cache_key
    )


def _derived_cache_storage_paths(cache: models.DerivedCache) -> list[Path]:
    metadata = cache.metadata_json or {}
    paths: list[Path] = []
    for key in ("chunks_path", "manifest_path", "sparse_stats_path"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            path = Path(value)
            paths.append(path.parent if path.name else path)
    return list(dict.fromkeys(paths))


def _delete_cache_path(path: Path) -> None:
    cache_root = (get_settings().data_dir / "cache").resolve()
    try:
        resolved_path = path.resolve()
    except OSError:
        return
    if resolved_path != cache_root and cache_root not in resolved_path.parents:
        return
    if not resolved_path.exists():
        return
    if resolved_path.is_dir():
        shutil.rmtree(resolved_path)
    else:
        resolved_path.unlink()
