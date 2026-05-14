from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)


@dataclass(frozen=True)
class SparseParamField:
    name: str
    label: str
    field_type: str
    default: Any
    help_text: str | None = None
    min_value: float | int | None = None
    max_value: float | int | None = None
    step: float | int | None = None

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
        return payload


@dataclass(frozen=True)
class SparseModelSpec:
    id: str
    label: str
    description: str
    provider: str
    fields: list[SparseParamField]

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
            "provider": self.provider,
        }


SPARSE_MODELS: dict[str, SparseModelSpec] = {
    "bm25_local": SparseModelSpec(
        id="bm25_local",
        label="BM25 local",
        description="Inspectable local BM25-style sparse vectors stored in Qdrant.",
        provider="rag_lab",
        fields=[
            SparseParamField(
                name="lowercase",
                label="Lowercase",
                field_type="boolean",
                default=True,
            ),
            SparseParamField(
                name="min_token_len",
                label="Min token length",
                field_type="number",
                default=2,
                min_value=1,
                max_value=32,
                step=1,
            ),
            SparseParamField(
                name="k1",
                label="K1",
                field_type="number",
                default=1.2,
                min_value=0,
                max_value=4,
                step=0.05,
            ),
            SparseParamField(
                name="b",
                label="B",
                field_type="number",
                default=0.75,
                min_value=0,
                max_value=1,
                step=0.05,
            ),
        ],
    )
}


def list_sparse_models() -> list[dict[str, Any]]:
    return [model.to_dict() for model in SPARSE_MODELS.values()]


def get_sparse_model(model_id: str) -> SparseModelSpec:
    spec = SPARSE_MODELS.get(model_id)
    if spec is None:
        raise ValueError(f"Unsupported sparse model: {model_id}")
    return spec


def normalize_sparse_params(model_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = get_sparse_model(model_id)
    merged = spec.defaults
    merged.update(params or {})
    return _coerce_params(spec, merged)


def build_bm25_stats(texts: list[str], params: dict[str, Any]) -> dict[str, Any]:
    tokenized = [tokenize(text, params) for text in texts]
    doc_count = len(tokenized)
    doc_lengths = [len(tokens) for tokens in tokenized]
    avg_doc_len = sum(doc_lengths) / doc_count if doc_count else 0.0
    doc_freqs: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freqs.update(set(tokens))

    vocabulary = {token: index for index, token in enumerate(sorted(doc_freqs), start=1)}
    idf = {
        token: math.log(1 + ((doc_count - doc_freq + 0.5) / (doc_freq + 0.5)))
        for token, doc_freq in doc_freqs.items()
    }
    return {
        "avg_doc_len": avg_doc_len,
        "doc_count": doc_count,
        "doc_lengths": doc_lengths,
        "idf": idf,
        "model": "bm25_local",
        "params": params,
        "schema_version": "raglab.bm25_stats.v1",
        "vocabulary": vocabulary,
    }


def encode_bm25_document(text: str, stats: dict[str, Any], doc_index: int) -> dict[str, list[float] | list[int]]:
    params = dict(stats["params"])
    tokens = tokenize(text, params)
    counts = Counter(token for token in tokens if token in stats["vocabulary"])
    doc_len = int(stats["doc_lengths"][doc_index]) if stats["doc_lengths"] else len(tokens)
    avg_doc_len = float(stats["avg_doc_len"] or 1.0)
    k1 = float(params["k1"])
    b = float(params["b"])
    indices: list[int] = []
    values: list[float] = []
    for token, tf in sorted(counts.items(), key=lambda item: stats["vocabulary"][item[0]]):
        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
        weight = float(stats["idf"][token]) * ((tf * (k1 + 1)) / denominator)
        if weight > 0:
            indices.append(int(stats["vocabulary"][token]))
            values.append(weight)
    return {"indices": indices, "values": values}


def encode_bm25_query(query: str, stats: dict[str, Any]) -> dict[str, list[float] | list[int]]:
    params = dict(stats["params"])
    counts = Counter(token for token in tokenize(query, params) if token in stats["vocabulary"])
    indices: list[int] = []
    values: list[float] = []
    for token, tf in sorted(counts.items(), key=lambda item: stats["vocabulary"][item[0]]):
        indices.append(int(stats["vocabulary"][token]))
        values.append(float(stats["idf"][token]) * float(tf))
    return {"indices": indices, "values": values}


def tokenize(text: str, params: dict[str, Any]) -> list[str]:
    raw_tokens = TOKEN_PATTERN.findall(text)
    if bool(params.get("lowercase", True)):
        raw_tokens = [token.lower() for token in raw_tokens]
    min_len = int(params.get("min_token_len", 2))
    return [token for token in raw_tokens if len(token) >= min_len]


def _coerce_params(spec: SparseModelSpec, params: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    fields_by_name = {field.name: field for field in spec.fields}
    for name, field in fields_by_name.items():
        value = params.get(name, field.default)
        if field.field_type == "number":
            try:
                value = float(value) if name in {"k1", "b"} else int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
        elif field.field_type == "boolean":
            value = bool(value)
        else:
            value = str(value)
        coerced[name] = value
    return coerced
