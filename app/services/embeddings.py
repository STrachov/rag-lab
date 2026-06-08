from __future__ import annotations

from dataclasses import dataclass
import math
from threading import Lock
import time
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class EmbeddingParamField:
    name: str
    label: str
    field_type: str
    default: Any
    help_text: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    step: int | None = None
    options: list[dict[str, str]] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "default": self.default,
            "label": self.label,
            "name": self.name,
            "type": self.field_type,
        }
        if self.help_text:
            payload["help_text"] = self.help_text
        if self.min_value is not None:
            payload["min"] = self.min_value
        if self.max_value is not None:
            payload["max"] = self.max_value
        if self.step is not None:
            payload["step"] = self.step
        if self.options is not None:
            payload["options"] = self.options
        return payload


@dataclass(frozen=True)
class EmbeddingModelSpec:
    id: str
    label: str
    description: str
    provider: str
    model_name: str
    vector_size: int
    fields: list[EmbeddingParamField]
    passage_prefix: str = ""
    query_prefix: str = ""
    supported_vector_sizes: tuple[int, ...] | None = None

    @property
    def defaults(self) -> dict[str, Any]:
        return {field.name: field.default for field in self.fields}

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_params": self.defaults,
            "description": self.description,
            "fields": [field.to_dict() for field in self.fields],
            "id": self.id,
            "label": self.label,
            "model_name": self.model_name,
            "provider": self.provider,
            "vector_size": self.vector_size,
        }


COMMON_SENTENCE_TRANSFORMER_FIELDS = [
    EmbeddingParamField(
        name="device",
        label="Device",
        field_type="select",
        default="cpu",
        options=[
            {"label": "CPU", "value": "cpu"},
            {"label": "CUDA", "value": "cuda"},
        ],
    ),
    EmbeddingParamField(
        name="batch_size",
        label="Batch size",
        field_type="number",
        default=32,
        min_value=1,
        max_value=256,
    ),
    EmbeddingParamField(
        name="normalize",
        label="Normalize",
        field_type="boolean",
        default=True,
    ),
]


VOYAGE_DIMENSION_OPTIONS = [
    {"label": "256", "value": "256"},
    {"label": "512", "value": "512"},
    {"label": "1024", "value": "1024"},
    {"label": "2048", "value": "2048"},
]

VOYAGE_RETRY_STATUS_CODES = {429, 502, 503, 504}
VOYAGE_TOKEN_CHARS = 2
VOYAGE_TOKEN_OVERHEAD_PER_TEXT = 8
_VOYAGE_THROTTLE_LOCK = Lock()
_VOYAGE_NEXT_REQUEST_AT = 0.0
_VOYAGE_TOKEN_WINDOW_STARTED_AT = 0.0
_VOYAGE_TOKENS_USED_IN_WINDOW = 0


COMMON_VOYAGE_FIELDS = [
    EmbeddingParamField(
        name="output_dimension",
        label="Output dimension",
        field_type="select",
        default=1024,
        help_text="Voyage 4 Matryoshka dimension used for the Qdrant dense vector.",
        options=VOYAGE_DIMENSION_OPTIONS,
    ),
    EmbeddingParamField(
        name="batch_size",
        label="Batch size",
        field_type="number",
        default=128,
        min_value=1,
        max_value=1000,
    ),
    EmbeddingParamField(
        name="truncation",
        label="Truncate overlength inputs",
        field_type="boolean",
        default=True,
    ),
    EmbeddingParamField(
        name="timeout_seconds",
        label="Timeout seconds",
        field_type="number",
        default=300,
        min_value=1,
        max_value=600,
    ),
]


EMBEDDING_MODELS: dict[str, EmbeddingModelSpec] = {
    "intfloat_multilingual_e5_small": EmbeddingModelSpec(
        id="intfloat_multilingual_e5_small",
        label="intfloat multilingual-e5-small",
        description="SentenceTransformer adapter for multilingual E5 small. Uses query/passage prefixes.",
        provider="sentence_transformers",
        model_name="intfloat/multilingual-e5-small",
        vector_size=384,
        fields=COMMON_SENTENCE_TRANSFORMER_FIELDS,
        passage_prefix="passage: ",
        query_prefix="query: ",
    ),
    "baai_bge_small_en_v1_5": EmbeddingModelSpec(
        id="baai_bge_small_en_v1_5",
        label="BAAI bge-small-en-v1.5",
        description="SentenceTransformer adapter for a compact English BGE baseline.",
        provider="sentence_transformers",
        model_name="BAAI/bge-small-en-v1.5",
        vector_size=384,
        fields=COMMON_SENTENCE_TRANSFORMER_FIELDS,
    ),
    "voyage_4_lite": EmbeddingModelSpec(
        id="voyage_4_lite",
        label="Voyage 4 Lite",
        description=(
            "Remote Voyage AI embedding adapter optimized for lower latency and cost. "
            "Uses input_type=document for chunks and input_type=query for search queries."
        ),
        provider="voyage",
        model_name="voyage-4-lite",
        vector_size=1024,
        fields=COMMON_VOYAGE_FIELDS,
        supported_vector_sizes=(256, 512, 1024, 2048),
    ),
    "voyage_4_large": EmbeddingModelSpec(
        id="voyage_4_large",
        label="Voyage 4 Large",
        description=(
            "Remote Voyage AI embedding adapter for highest general-purpose and multilingual "
            "retrieval quality. Uses input_type=document for chunks and input_type=query for search queries."
        ),
        provider="voyage",
        model_name="voyage-4-large",
        vector_size=1024,
        fields=COMMON_VOYAGE_FIELDS,
        supported_vector_sizes=(256, 512, 1024, 2048),
    ),
}


class SentenceTransformerEmbedder:
    def __init__(self, spec: EmbeddingModelSpec, params: dict[str, Any]) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ValueError(
                "sentence-transformers is required for local embedding models"
            ) from exc

        self.spec = spec
        self.params = params
        self.model = SentenceTransformer(spec.model_name, device=str(params["device"]))

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"{self.spec.passage_prefix}{text}" for text in texts])

    def embed_query(self, query: str) -> list[float]:
        return self._encode([f"{self.spec.query_prefix}{query}"])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=int(self.params["batch_size"]),
            convert_to_numpy=True,
            normalize_embeddings=bool(self.params["normalize"]),
            show_progress_bar=False,
        )
        return vectors.astype(float).tolist()


class VoyageEmbedder:
    def __init__(self, spec: EmbeddingModelSpec, params: dict[str, Any]) -> None:
        settings = get_settings()
        api_key = str(getattr(settings, "voyage_api_key", "") or "")
        if not api_key:
            raise ValueError("RAG_LAB_VOYAGE_API_KEY is required for Voyage embedding models")

        self.base_url = str(getattr(settings, "voyage_base_url", "https://api.voyageai.com")).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.params = params
        self.spec = spec
        self.max_retries = max(0, int(getattr(settings, "voyage_max_retries", 0) or 0))
        self.rpm_limit = max(0, int(getattr(settings, "voyage_rpm_limit", 0) or 0))
        self.tpm_limit = max(0, int(getattr(settings, "voyage_tpm_limit", 0) or 0))
        self.tpm_utilization = min(
            1.0,
            max(0.1, float(getattr(settings, "voyage_tpm_utilization", 0.65) or 0.65)),
        )

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="document")

    def embed_query(self, query: str) -> list[float]:
        return self._embed([query], input_type="query")[0]

    def _embed(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []
        batch_size = min(1000, max(1, int(self.params["batch_size"])))
        for batch in _voyage_batches(
            texts,
            batch_size=batch_size,
            tpm_limit=self.tpm_limit,
            tpm_utilization=self.tpm_utilization,
        ):
            response = self._post_embeddings(batch, input_type=input_type)
            payload = response.json()
            items = payload.get("data")
            if not isinstance(items, list):
                raise ValueError("Voyage embeddings response did not include a data list")
            embeddings.extend([_coerce_embedding_vector(item) for item in items])
        return embeddings

    def _post_embeddings(self, batch: list[str], *, input_type: str) -> httpx.Response:
        payload = {
            "input": batch,
            "input_type": input_type,
            "model": self.spec.model_name,
            "output_dimension": int(self.params["output_dimension"]),
            "truncation": bool(self.params["truncation"]),
        }
        timeout = float(self.params["timeout_seconds"])
        estimated_tokens = _estimate_voyage_tokens(batch)
        for attempt in range(self.max_retries + 1):
            _wait_for_voyage_capacity(
                estimated_tokens=estimated_tokens,
                rpm_limit=self.rpm_limit,
                tpm_limit=self.tpm_limit,
            )
            try:
                response = httpx.post(
                    f"{self.base_url}/v1/embeddings",
                    headers=self.headers,
                    json=payload,
                    timeout=timeout,
                )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    time.sleep(_voyage_transport_retry_delay(attempt))
                    continue
                raise ValueError(
                    f"Voyage embeddings request timed out after {timeout:g} seconds. "
                    "Try increasing timeout_seconds, reducing the Voyage batch_size, "
                    "or checking whether the current VPN/proxy is slowing the connection."
                ) from exc
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    time.sleep(_voyage_transport_retry_delay(attempt))
                    continue
                raise ValueError(
                    "Voyage embeddings request failed due to a network transport error. "
                    "Check the current VPN/proxy connection or try again later."
                ) from exc
            if response.status_code in VOYAGE_RETRY_STATUS_CODES and attempt < self.max_retries:
                time.sleep(_voyage_retry_delay(response, attempt))
                continue
            if response.status_code == 429:
                raise ValueError(
                    "Voyage embeddings returned 429 Too Many Requests after retries. "
                    "The free plan is very tight; wait for the Voyage quota window to reset, "
                    "or lower RAG_LAB_VOYAGE_TPM_LIMIT / RAG_LAB_VOYAGE_TPM_UTILIZATION."
                )
            if response.status_code == 403:
                raise ValueError(
                    "Voyage embeddings returned 403 Forbidden. Check whether the current VPN, "
                    "proxy, IP address, or API project is allowed by Voyage AI."
                )
            if response.is_error:
                response.raise_for_status()
            return response
        raise RuntimeError("Voyage embeddings retry loop exited unexpectedly")


def list_embedding_models() -> list[dict[str, Any]]:
    return [model.to_dict() for model in EMBEDDING_MODELS.values()]


def get_embedding_model(model_id: str) -> EmbeddingModelSpec:
    spec = EMBEDDING_MODELS.get(model_id)
    if spec is None:
        raise ValueError(f"Unsupported embedding model: {model_id}")
    return spec


def normalize_embedding_params(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_embedding_model(model_id)
    merged = spec.defaults
    merged.update(params or {})
    normalized = _coerce_params(spec, merged)
    if spec.supported_vector_sizes is not None:
        output_dimension = int(normalized["output_dimension"])
        if output_dimension not in spec.supported_vector_sizes:
            raise ValueError(f"Unsupported output_dimension for {model_id}")
    return normalized


def effective_vector_size(spec: EmbeddingModelSpec, params: dict[str, Any]) -> int:
    if spec.supported_vector_sizes is None:
        return spec.vector_size
    return int(params["output_dimension"])


def create_embedder(
    model_id: str,
    params: dict[str, Any] | None = None,
) -> SentenceTransformerEmbedder | VoyageEmbedder:
    spec = get_embedding_model(model_id)
    normalized = normalize_embedding_params(model_id, params)
    if spec.provider == "sentence_transformers":
        return SentenceTransformerEmbedder(spec, normalized)
    if spec.provider == "voyage":
        return VoyageEmbedder(spec, normalized)
    raise ValueError(f"Unsupported embedding provider: {spec.provider}")


def _coerce_params(spec: EmbeddingModelSpec, params: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    fields_by_name = {field.name: field for field in spec.fields}
    for name, field in fields_by_name.items():
        value = params.get(name, field.default)
        if field.field_type == "number":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
        elif field.field_type == "boolean":
            value = _coerce_bool(value, name)
        elif field.field_type == "select":
            value = str(value)
            allowed = {option["value"] for option in field.options or []}
            if value not in allowed:
                raise ValueError(f"Unsupported value for {name}")
            if isinstance(field.default, int):
                value = int(value)
        else:
            value = str(value)
        coerced[name] = value
    return coerced


def _coerce_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, int):
        return bool(value)
    raise ValueError(f"{name} must be a boolean")


def _voyage_batches(
    texts: list[str],
    *,
    batch_size: int,
    tpm_limit: int,
    tpm_utilization: float = 0.65,
) -> list[list[str]]:
    utilization = min(1.0, max(0.1, tpm_utilization))
    max_tokens = max(1, int(tpm_limit * utilization)) if tpm_limit > 0 else 0
    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for text in texts:
        text_tokens = _estimate_voyage_tokens([text])
        would_exceed_count = len(current) >= batch_size
        would_exceed_tokens = bool(max_tokens and current and current_tokens + text_tokens > max_tokens)
        if would_exceed_count or would_exceed_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(text)
        current_tokens += text_tokens
    if current:
        batches.append(current)
    return batches


def _estimate_voyage_tokens(texts: list[str]) -> int:
    return sum(
        max(1, math.ceil(len(text) / VOYAGE_TOKEN_CHARS) + VOYAGE_TOKEN_OVERHEAD_PER_TEXT)
        for text in texts
    )


def _wait_for_voyage_capacity(*, estimated_tokens: int, rpm_limit: int, tpm_limit: int) -> None:
    global _VOYAGE_NEXT_REQUEST_AT
    global _VOYAGE_TOKEN_WINDOW_STARTED_AT
    global _VOYAGE_TOKENS_USED_IN_WINDOW

    if rpm_limit <= 0 and tpm_limit <= 0:
        return

    while True:
        with _VOYAGE_THROTTLE_LOCK:
            now = time.monotonic()
            wait_seconds = 0.0
            if rpm_limit > 0 and now < _VOYAGE_NEXT_REQUEST_AT:
                wait_seconds = max(wait_seconds, _VOYAGE_NEXT_REQUEST_AT - now)

            if tpm_limit > 0:
                if _VOYAGE_TOKEN_WINDOW_STARTED_AT == 0.0 or now - _VOYAGE_TOKEN_WINDOW_STARTED_AT >= 60.0:
                    _VOYAGE_TOKEN_WINDOW_STARTED_AT = now
                    _VOYAGE_TOKENS_USED_IN_WINDOW = 0
                token_charge = min(max(1, estimated_tokens), tpm_limit)
                if _VOYAGE_TOKENS_USED_IN_WINDOW + token_charge > tpm_limit:
                    wait_seconds = max(wait_seconds, 60.0 - (now - _VOYAGE_TOKEN_WINDOW_STARTED_AT))

            if wait_seconds <= 0.0:
                if rpm_limit > 0:
                    _VOYAGE_NEXT_REQUEST_AT = now + (60.0 / rpm_limit)
                if tpm_limit > 0:
                    _VOYAGE_TOKENS_USED_IN_WINDOW += min(max(1, estimated_tokens), tpm_limit)
                return

        time.sleep(wait_seconds)


def _voyage_retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))


def _voyage_transport_retry_delay(attempt: int) -> float:
    return min(60.0, float(2**attempt))


def _coerce_embedding_vector(item: Any) -> list[float]:
    if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
        raise ValueError("Voyage embeddings response contained an invalid embedding item")
    try:
        return [float(value) for value in item["embedding"]]
    except (TypeError, ValueError) as exc:
        raise ValueError("Voyage embeddings response contained a non-numeric vector") from exc
