from __future__ import annotations

from typing import Any

import httpx


class QdrantVectorStore:
    """Small REST adapter around Qdrant so Qdrant never becomes application state."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def ensure_collection(
        self,
        *,
        collection_name: str,
        vector_size: int,
        distance: str = "Cosine",
        sparse: bool = False,
    ) -> None:
        existing = httpx.get(f"{self.url}/collections/{collection_name}", timeout=30.0)
        if existing.status_code == 200:
            return
        if existing.status_code != 404:
            existing.raise_for_status()

        payload: dict[str, Any] = {
            "vectors": {"dense": {"distance": distance, "size": vector_size}}
        }
        if sparse:
            payload["sparse_vectors"] = {"sparse": {}}
        response = httpx.put(
            f"{self.url}/collections/{collection_name}",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()

    def upsert_points(
        self,
        *,
        collection_name: str,
        points: list[dict[str, Any]],
    ) -> None:
        response = httpx.put(
            f"{self.url}/collections/{collection_name}/points",
            params={"wait": "true"},
            json={"points": points},
            timeout=120.0,
        )
        response.raise_for_status()

    def search_dense(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        response = httpx.post(
            f"{self.url}/collections/{collection_name}/points/search",
            json={
                "limit": top_k,
                "vector": {"name": "dense", "vector": query_vector},
                "with_payload": True,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("result") or [])

    def search_sparse(
        self,
        *,
        collection_name: str,
        query_vector: dict[str, list[float] | list[int]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        response = httpx.post(
            f"{self.url}/collections/{collection_name}/points/search",
            json={
                "limit": top_k,
                "vector": {"name": "sparse", "vector": query_vector},
                "with_payload": True,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload.get("result") or [])
