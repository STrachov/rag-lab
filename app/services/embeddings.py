from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmbeddingParamField:
    name: str
    label: str
    field_type: str
    default: Any
    help_text: str | None = None
    min_value: int | None = None
    max_value: int | None = None
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
    return _coerce_params(spec, merged)


def create_embedder(model_id: str, params: dict[str, Any] | None = None) -> SentenceTransformerEmbedder:
    spec = get_embedding_model(model_id)
    return SentenceTransformerEmbedder(spec, normalize_embedding_params(model_id, params))


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
            value = bool(value)
        elif field.field_type == "select":
            value = str(value)
            allowed = {option["value"] for option in field.options or []}
            if value not in allowed:
                raise ValueError(f"Unsupported value for {name}")
        else:
            value = str(value)
        coerced[name] = value
    return coerced
