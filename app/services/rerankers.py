from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RerankerParamField:
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
class RerankerModelSpec:
    id: str
    label: str
    description: str
    provider: str
    model_name: str
    backend: str
    fields: list[RerankerParamField]

    @property
    def defaults(self) -> dict[str, Any]:
        return {field.name: field.default for field in self.fields}

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "default_params": self.defaults,
            "description": self.description,
            "fields": [field.to_dict() for field in self.fields],
            "id": self.id,
            "label": self.label,
            "model_name": self.model_name,
            "provider": self.provider,
        }


COMMON_CROSS_ENCODER_FIELDS = [
    RerankerParamField(
        name="device",
        label="Device",
        field_type="select",
        default="cpu",
        options=[
            {"label": "CPU", "value": "cpu"},
            {"label": "CUDA", "value": "cuda"},
        ],
    ),
    RerankerParamField(
        name="batch_size",
        label="Batch size",
        field_type="number",
        default=8,
        min_value=1,
        max_value=128,
        step=1,
    ),
    RerankerParamField(
        name="max_length",
        label="Max length",
        field_type="number",
        default=512,
        min_value=128,
        max_value=8192,
        step=128,
    ),
    RerankerParamField(
        name="normalize_scores",
        label="Normalize scores",
        field_type="boolean",
        default=True,
        help_text="Apply sigmoid to raw reranker logits.",
    ),
]


RERANKER_MODELS: dict[str, RerankerModelSpec] = {
    "baai_bge_reranker_v2_m3": RerankerModelSpec(
        id="baai_bge_reranker_v2_m3",
        label="BAAI bge-reranker-v2-m3",
        description="Multilingual cross-encoder reranker baseline. Good first reranker for mixed-language RAG corpora.",
        provider="sentence_transformers",
        model_name="BAAI/bge-reranker-v2-m3",
        backend="cross_encoder",
        fields=COMMON_CROSS_ENCODER_FIELDS,
    ),
    "qwen3_reranker_0_6b": RerankerModelSpec(
        id="qwen3_reranker_0_6b",
        label="Qwen3-Reranker-0.6B",
        description="Instruction-aware multilingual Qwen3 reranker. Stronger but heavier than MiniLM and BGE on CPU.",
        provider="sentence_transformers",
        model_name="Qwen/Qwen3-Reranker-0.6B",
        backend="cross_encoder",
        fields=COMMON_CROSS_ENCODER_FIELDS
        + [
            RerankerParamField(
                name="instruction",
                label="Instruction",
                field_type="text",
                default="Given a web search query, retrieve relevant passages that answer the query",
                help_text="Task instruction used by the Qwen3 reranker prompt.",
            )
        ],
    ),
    "ms_marco_minilm_l6_v2": RerankerModelSpec(
        id="ms_marco_minilm_l6_v2",
        label="MS MARCO MiniLM L6 v2",
        description="Fast English cross-encoder reranker baseline for quick local smoke tests.",
        provider="sentence_transformers",
        model_name="cross-encoder/ms-marco-MiniLM-L6-v2",
        backend="cross_encoder",
        fields=COMMON_CROSS_ENCODER_FIELDS,
    ),
}


class CrossEncoderReranker:
    def __init__(self, spec: RerankerModelSpec, params: dict[str, Any]) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise ValueError("sentence-transformers is required for local reranker models") from exc

        self.spec = spec
        self.params = params
        init_kwargs: dict[str, Any] = {
            "device": str(params["device"]),
            "max_length": int(params["max_length"]),
        }
        instruction = str(params.get("instruction") or "").strip()
        if instruction and spec.id == "qwen3_reranker_0_6b":
            init_kwargs["prompts"] = {"raglab": instruction}
            init_kwargs["default_prompt_name"] = "raglab"
        try:
            self.model = CrossEncoder(spec.model_name, **init_kwargs)
        except TypeError:
            init_kwargs.pop("prompts", None)
            init_kwargs.pop("default_prompt_name", None)
            self.model = CrossEncoder(spec.model_name, **init_kwargs)

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        pairs = [(query, passage) for passage in passages]
        scores = self.model.predict(
            pairs,
            batch_size=int(self.params["batch_size"]),
            show_progress_bar=False,
        )
        values = [_as_float(score) for score in scores]
        if bool(self.params["normalize_scores"]):
            return [_sigmoid(value) for value in values]
        return values


def list_reranker_models() -> list[dict[str, Any]]:
    return [model.to_dict() for model in RERANKER_MODELS.values()]


def get_reranker_model(model_id: str) -> RerankerModelSpec:
    spec = RERANKER_MODELS.get(model_id)
    if spec is None:
        raise ValueError(f"Unsupported reranker model: {model_id}")
    return spec


def normalize_reranker_params(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_reranker_model(model_id)
    merged = spec.defaults
    merged.update(params or {})
    return _coerce_params(spec, merged)


def create_reranker(model_id: str, params: dict[str, Any] | None = None) -> CrossEncoderReranker:
    spec = get_reranker_model(model_id)
    return CrossEncoderReranker(spec, normalize_reranker_params(model_id, params))


def rerank_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    model_id: str,
    params: dict[str, Any] | None,
    text_by_chunk_id: dict[str, str],
) -> list[dict[str, Any]]:
    reranker = create_reranker(model_id, params)
    passages = [
        text_by_chunk_id.get(str(chunk.get("chunk_id") or ""), str(chunk.get("text_preview") or ""))
        for chunk in chunks
    ]
    scores = reranker.score(query, passages)
    reranked: list[dict[str, Any]] = []
    for original_rank, (chunk, score) in enumerate(zip(chunks, scores, strict=True), start=1):
        reranked.append(
            {
                **chunk,
                "original_rank": original_rank,
                "original_score": chunk.get("score"),
                "rerank_score": score,
                "score": score,
            }
        )
    return sorted(reranked, key=lambda chunk: float(chunk["rerank_score"]), reverse=True)


def _coerce_params(spec: RerankerModelSpec, params: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    fields_by_name = {field.name: field for field in spec.fields}
    for name, field in fields_by_name.items():
        value = params.get(name, field.default)
        if field.field_type == "number":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
            if field.min_value is not None and value < field.min_value:
                raise ValueError(f"{name} must be at least {field.min_value}")
            if field.max_value is not None and value > field.max_value:
                raise ValueError(f"{name} must be at most {field.max_value}")
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


def _as_float(value: Any) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, list):
        if not value:
            return 0.0
        return _as_float(value[0])
    return float(value)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)
