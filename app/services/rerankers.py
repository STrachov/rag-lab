from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from threading import Lock
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.hashing import stable_json_dumps

logger = logging.getLogger(__name__)
_LOCAL_RERANKER_CACHE_LOCK = Lock()
_LOCAL_RERANKER_CACHE: dict[str, "CrossEncoderReranker"] = {}

VOYAGE_RERANK_RETRY_STATUS_CODES = {429, 502, 503, 504}
VOYAGE_RERANK_TOKEN_CHARS = 2
VOYAGE_RERANK_TOKEN_OVERHEAD_PER_TEXT = 8
_VOYAGE_RERANK_THROTTLE_LOCK = Lock()
_VOYAGE_RERANK_NEXT_REQUEST_AT = 0.0
_VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT = 0.0
_VOYAGE_RERANK_TOKENS_USED_IN_WINDOW = 0


@dataclass(frozen=True)
class RerankerParamField:
    name: str
    label: str
    field_type: str
    default: Any
    help_text: str | None = None
    min_value: int | None = None
    max_value: int | None = None
    step: float | int | None = None
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


COMMON_VOYAGE_RERANK_FIELDS = [
    RerankerParamField(
        name="truncation",
        label="Truncate overlength inputs",
        field_type="boolean",
        default=True,
        help_text="Allow Voyage to truncate overlength query/document pairs instead of rejecting the request.",
    ),
    RerankerParamField(
        name="timeout_seconds",
        label="Timeout seconds",
        field_type="number",
        default=120,
        min_value=1,
        max_value=600,
        step=1,
    ),
]

COMMON_OPENAI_LLM_RERANK_FIELDS = [
    RerankerParamField(
        name="model",
        label="Model",
        field_type="text",
        default="gpt-5.4-mini",
        help_text="OpenAI chat/completions model used as a pointwise LLM reranker.",
    ),
    RerankerParamField(
        name="items_per_call",
        label="Items per call",
        field_type="number",
        default=3,
        min_value=1,
        max_value=10,
        step=1,
        help_text="How many candidate passages are scored in one LLM request.",
    ),
    RerankerParamField(
        name="max_candidate_chars",
        label="Max candidate chars",
        field_type="number",
        default=3000,
        min_value=200,
        max_value=20000,
        step=100,
        help_text="Candidate text is clipped to this many characters before being sent to OpenAI.",
    ),
    RerankerParamField(
        name="llm_weight",
        label="LLM weight",
        field_type="number",
        default=0.7,
        min_value=0,
        max_value=1,
        step=0.05,
        help_text="Weight of the LLM relevance score in the final rerank score.",
    ),
    RerankerParamField(
        name="retrieval_weight",
        label="Retrieval weight",
        field_type="number",
        default=0.3,
        min_value=0,
        max_value=1,
        step=0.05,
        help_text="Weight of the normalized original retrieval score in the final rerank score.",
    ),
    RerankerParamField(
        name="include_reasoning",
        label="Include reasoning",
        field_type="boolean",
        default=False,
        help_text="Ask the LLM to return a short reason for each score. Useful for debugging, slower and more costly.",
    ),
    RerankerParamField(
        name="temperature",
        label="Temperature",
        field_type="number",
        default=0.0,
        min_value=0,
        max_value=2,
        step=0.1,
    ),
    RerankerParamField(
        name="timeout_seconds",
        label="Timeout seconds",
        field_type="number",
        default=120,
        min_value=1,
        max_value=600,
        step=1,
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
    "voyage_rerank_2_5": RerankerModelSpec(
        id="voyage_rerank_2_5",
        label="Voyage rerank-2.5",
        description=(
            "Remote Voyage AI reranker for higher-quality reranking of retrieved candidates. "
            "Sends the query and candidate chunk text to Voyage."
        ),
        provider="voyage",
        model_name="rerank-2.5",
        backend="remote_api",
        fields=COMMON_VOYAGE_RERANK_FIELDS,
    ),
    "voyage_rerank_2_5_lite": RerankerModelSpec(
        id="voyage_rerank_2_5_lite",
        label="Voyage rerank-2.5 Lite",
        description=(
            "Remote Voyage AI reranker optimized for lower latency and higher throughput. "
            "Sends the query and candidate chunk text to Voyage."
        ),
        provider="voyage",
        model_name="rerank-2.5-lite",
        backend="remote_api",
        fields=COMMON_VOYAGE_RERANK_FIELDS,
    ),
    "openai_llm_reranker": RerankerModelSpec(
        id="openai_llm_reranker",
        label="OpenAI LLM reranker",
        description=(
            "Pointwise LLM-as-reranker. Sends query and candidate text batches to OpenAI, "
            "expects strict JSON relevance scores from 0 to 1, and can blend LLM score with "
            "the original retrieval score."
        ),
        provider="openai",
        model_name="configurable",
        backend="llm_api",
        fields=COMMON_OPENAI_LLM_RERANK_FIELDS,
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


class VoyageReranker:
    def __init__(self, spec: RerankerModelSpec, params: dict[str, Any]) -> None:
        settings = get_settings()
        api_key = str(getattr(settings, "voyage_api_key", "") or "")
        if not api_key:
            raise ValueError("RAG_LAB_VOYAGE_API_KEY is required for Voyage reranker models")

        self.base_url = str(getattr(settings, "voyage_base_url", "https://api.voyageai.com")).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.max_retries = max(0, int(getattr(settings, "voyage_rerank_max_retries", 0) or 0))
        self.params = params
        self.rpm_limit = max(0, int(getattr(settings, "voyage_rerank_rpm_limit", 0) or 0))
        self.spec = spec
        self.tpm_limit = _voyage_rerank_tpm_limit(settings, spec.model_name)
        self.tpm_utilization = min(
            1.0,
            max(0.1, float(getattr(settings, "voyage_rerank_tpm_utilization", 0.65) or 0.65)),
        )
        self.usage: dict[str, Any] = {}

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        estimated_tokens = _estimate_voyage_rerank_tokens(query, passages)
        logger.info(
            "voyage rerank plan model=%s document_count=%s estimated_tokens=%s "
            "rpm_limit=%s tpm_limit=%s tpm_utilization=%.2f timeout_seconds=%s",
            self.spec.model_name,
            len(passages),
            estimated_tokens,
            self.rpm_limit,
            self.tpm_limit,
            self.tpm_utilization,
            float(self.params["timeout_seconds"]),
        )
        started_at = time.perf_counter()
        response = self._post_rerank(query, passages, estimated_tokens=estimated_tokens)
        elapsed_seconds = time.perf_counter() - started_at
        payload = response.json()
        items = payload.get("data")
        if not isinstance(items, list):
            raise ValueError("Voyage rerank response did not include a data list")

        scores: list[float | None] = [None] * len(passages)
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Voyage rerank response contained an invalid item")
            try:
                index = int(item["index"])
                score = float(item.get("relevance_score", item.get("score")))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Voyage rerank response contained an invalid score item") from exc
            if 0 <= index < len(scores):
                scores[index] = score

        if any(score is None for score in scores):
            raise ValueError("Voyage rerank response did not return a score for every candidate")
        self.usage = _usage_payload(
            candidate_count=len(passages),
            duration_seconds=elapsed_seconds,
            estimated_cost_usd=_voyage_rerank_estimated_cost(self.spec.model_name, estimated_tokens),
            estimated_tokens=estimated_tokens,
            input_tokens=estimated_tokens,
            model=self.spec.model_name,
            output_tokens=0,
            provider="voyage",
            request_count=int(getattr(self, "_last_request_count", 1)),
            retry_count=int(getattr(self, "_last_retry_count", 0)),
            total_tokens=estimated_tokens,
        )
        return [float(score) for score in scores]

    def _post_rerank(
        self,
        query: str,
        passages: list[str],
        *,
        estimated_tokens: int,
    ) -> httpx.Response:
        payload = {
            "documents": passages,
            "model": self.spec.model_name,
            "query": query,
            "return_documents": False,
            "top_k": len(passages),
            "truncation": bool(self.params["truncation"]),
        }
        timeout = float(self.params["timeout_seconds"])
        for attempt in range(self.max_retries + 1):
            _wait_for_voyage_rerank_capacity(
                estimated_tokens=estimated_tokens,
                rpm_limit=self.rpm_limit,
                tpm_limit=self.tpm_limit,
                tpm_utilization=self.tpm_utilization,
            )
            try:
                started_at = time.perf_counter()
                response = httpx.post(
                    f"{self.base_url}/v1/rerank",
                    headers=self.headers,
                    json=payload,
                    timeout=timeout,
                )
                elapsed_seconds = time.perf_counter() - started_at
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    delay = _voyage_rerank_transport_retry_delay(attempt)
                    logger.warning(
                        "voyage rerank timeout model=%s attempt=%s/%s retry_in_seconds=%.1f "
                        "timeout_seconds=%s document_count=%s estimated_tokens=%s",
                        self.spec.model_name,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                        timeout,
                        len(passages),
                        estimated_tokens,
                    )
                    time.sleep(delay)
                    continue
                raise ValueError(
                    f"Voyage rerank request timed out after {timeout:g} seconds. "
                    "Try increasing timeout_seconds, reducing candidate_k, or checking whether "
                    "the current VPN/proxy is slowing the connection."
                ) from exc
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    delay = _voyage_rerank_transport_retry_delay(attempt)
                    logger.warning(
                        "voyage rerank transport error model=%s attempt=%s/%s retry_in_seconds=%.1f "
                        "error_type=%s document_count=%s estimated_tokens=%s",
                        self.spec.model_name,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                        type(exc).__name__,
                        len(passages),
                        estimated_tokens,
                    )
                    time.sleep(delay)
                    continue
                raise ValueError(
                    "Voyage rerank request failed due to a network transport error. "
                    "Check the current VPN/proxy connection or try again later."
                ) from exc

            logger.info(
                "voyage rerank response model=%s attempt=%s/%s status_code=%s elapsed_seconds=%.2f "
                "retry_after=%s document_count=%s estimated_tokens=%s",
                self.spec.model_name,
                attempt + 1,
                self.max_retries + 1,
                response.status_code,
                elapsed_seconds,
                response.headers.get("Retry-After"),
                len(passages),
                estimated_tokens,
            )
            if response.status_code in VOYAGE_RERANK_RETRY_STATUS_CODES and attempt < self.max_retries:
                delay = _voyage_rerank_retry_delay(response, attempt)
                logger.warning(
                    "voyage rerank retry model=%s status_code=%s retry_in_seconds=%.1f "
                    "document_count=%s estimated_tokens=%s",
                    self.spec.model_name,
                    response.status_code,
                    delay,
                    len(passages),
                    estimated_tokens,
                )
                time.sleep(delay)
                continue
            if response.status_code == 429:
                raise ValueError(
                    "Voyage rerank returned 429 Too Many Requests after retries. "
                    "Wait for the Voyage quota window to reset, or lower "
                    "RAG_LAB_VOYAGE_RERANK_RPM_LIMIT / model TPM limit / "
                    "RAG_LAB_VOYAGE_RERANK_TPM_UTILIZATION."
                )
            if response.status_code == 403:
                raise ValueError(
                    "Voyage rerank returned 403 Forbidden. Check whether the current VPN, proxy, "
                    "IP address, or API project is allowed by Voyage AI."
                )
            if response.is_error:
                response.raise_for_status()
            self._last_request_count = attempt + 1
            self._last_retry_count = attempt
            return response
        raise RuntimeError("Voyage rerank retry loop exited unexpectedly")


class OpenAILLMReranker:
    def __init__(self, spec: RerankerModelSpec, params: dict[str, Any]) -> None:
        settings = get_settings()
        api_key = str(getattr(settings, "openai_api_key", "") or "")
        if not api_key:
            raise ValueError("RAG_LAB_OPENAI_API_KEY is required for OpenAI LLM reranker models")

        self.base_url = str(getattr(settings, "openai_base_url", "https://api.openai.com")).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.max_retries = max(0, int(getattr(settings, "openai_max_retries", 0) or 0))
        self.params = params
        self.spec = spec
        self.usage: dict[str, Any] = {}

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        scores: list[float | None] = [None] * len(passages)
        started_at = time.perf_counter()
        items_per_call = max(1, int(self.params["items_per_call"]))
        max_chars = max(1, int(self.params["max_candidate_chars"]))
        model = str(self.params["model"])
        logger.info(
            "openai llm rerank plan model=%s candidate_count=%s items_per_call=%s "
            "max_candidate_chars=%s timeout_seconds=%s include_reasoning=%s",
            model,
            len(passages),
            items_per_call,
            max_chars,
            float(self.params["timeout_seconds"]),
            bool(self.params["include_reasoning"]),
        )
        indexed_passages = [
            {"index": index, "text": passage[:max_chars]}
            for index, passage in enumerate(passages)
        ]
        request_count = 0
        retry_count = 0
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        for batch_index, start in enumerate(range(0, len(indexed_passages), items_per_call), start=1):
            batch = indexed_passages[start : start + items_per_call]
            payload = self._build_payload(query=query, candidates=batch)
            response = self._post_chat_completions(payload, batch_index=batch_index, batch_count=math.ceil(len(indexed_passages) / items_per_call))
            request_count += int(getattr(self, "_last_request_count", 1))
            retry_count += int(getattr(self, "_last_retry_count", 0))
            response_usage = _openai_response_usage(response)
            input_tokens += response_usage["input_tokens"]
            output_tokens += response_usage["output_tokens"]
            total_tokens += response_usage["total_tokens"]
            parsed_scores = self._parse_scores(response, expected_indexes={item["index"] for item in batch})
            for index, score in parsed_scores.items():
                scores[index] = score

        if any(score is None for score in scores):
            missing = [index for index, score in enumerate(scores) if score is None]
            raise ValueError(f"OpenAI LLM rerank response did not return scores for candidate indexes: {missing}")
        self.usage = _usage_payload(
            candidate_count=len(passages),
            duration_seconds=time.perf_counter() - started_at,
            estimated_cost_usd=_openai_llm_rerank_estimated_cost(input_tokens, output_tokens),
            input_tokens=input_tokens,
            items_per_call=items_per_call,
            model=model,
            output_tokens=output_tokens,
            provider="openai",
            request_count=request_count,
            retry_count=retry_count,
            total_tokens=total_tokens,
        )
        return [float(score) for score in scores]

    def _build_payload(self, *, query: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        include_reasoning = bool(self.params["include_reasoning"])
        return {
            "messages": [
                {
                    "content": _openai_rerank_system_prompt(include_reasoning=include_reasoning),
                    "role": "system",
                },
                {
                    "content": json.dumps(
                        {
                            "candidates": candidates,
                            "question": query,
                        },
                        ensure_ascii=False,
                    ),
                    "role": "user",
                },
            ],
            "model": str(self.params["model"]),
            "response_format": _openai_rerank_response_format(include_reasoning=include_reasoning),
            "temperature": float(self.params["temperature"]),
        }

    def _post_chat_completions(self, payload: dict[str, Any], *, batch_index: int, batch_count: int) -> httpx.Response:
        timeout = float(self.params["timeout_seconds"])
        for attempt in range(self.max_retries + 1):
            try:
                started_at = time.perf_counter()
                response = httpx.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=timeout,
                )
                elapsed_seconds = time.perf_counter() - started_at
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    delay = _openai_retry_delay(None, attempt)
                    logger.warning(
                        "openai llm rerank timeout model=%s batch=%s/%s attempt=%s/%s "
                        "retry_in_seconds=%.1f timeout_seconds=%s",
                        payload["model"],
                        batch_index,
                        batch_count,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                        timeout,
                    )
                    time.sleep(delay)
                    continue
                raise ValueError(
                    f"OpenAI LLM rerank request timed out after {timeout:g} seconds. "
                    "Try increasing timeout_seconds, lowering items_per_call, or lowering candidate_k."
                ) from exc
            except httpx.TransportError as exc:
                if attempt < self.max_retries:
                    delay = _openai_retry_delay(None, attempt)
                    logger.warning(
                        "openai llm rerank transport error model=%s batch=%s/%s attempt=%s/%s "
                        "retry_in_seconds=%.1f error_type=%s",
                        payload["model"],
                        batch_index,
                        batch_count,
                        attempt + 1,
                        self.max_retries + 1,
                        delay,
                        type(exc).__name__,
                    )
                    time.sleep(delay)
                    continue
                raise ValueError("OpenAI LLM rerank request failed due to a network transport error.") from exc

            logger.info(
                "openai llm rerank response model=%s batch=%s/%s attempt=%s/%s status_code=%s "
                "elapsed_seconds=%.2f retry_after=%s",
                payload["model"],
                batch_index,
                batch_count,
                attempt + 1,
                self.max_retries + 1,
                response.status_code,
                elapsed_seconds,
                response.headers.get("Retry-After"),
            )
            if response.status_code in {429, 502, 503, 504} and attempt < self.max_retries:
                delay = _openai_retry_delay(response, attempt)
                logger.warning(
                    "openai llm rerank retry model=%s status_code=%s retry_in_seconds=%.1f batch=%s/%s",
                    payload["model"],
                    response.status_code,
                    delay,
                    batch_index,
                    batch_count,
                )
                time.sleep(delay)
                continue
            if response.status_code == 429:
                raise ValueError("OpenAI LLM rerank returned 429 Too Many Requests after retries.")
            if response.status_code == 401:
                raise ValueError("OpenAI LLM rerank returned 401 Unauthorized. Check RAG_LAB_OPENAI_API_KEY.")
            if response.status_code == 403:
                raise ValueError("OpenAI LLM rerank returned 403 Forbidden. Check API project, model access, VPN, or proxy.")
            if response.is_error:
                response.raise_for_status()
            self._last_request_count = attempt + 1
            self._last_retry_count = attempt
            return response
        raise RuntimeError("OpenAI LLM rerank retry loop exited unexpectedly")

    def _parse_scores(self, response: httpx.Response, *, expected_indexes: set[int]) -> dict[int, float]:
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            items = parsed["scores"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("OpenAI LLM rerank response did not match the expected JSON shape") from exc
        if not isinstance(items, list):
            raise ValueError("OpenAI LLM rerank response scores must be a list")

        scores: dict[int, float] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("OpenAI LLM rerank response contained an invalid score item")
            try:
                index = int(item["index"])
                score = float(item["relevance_score"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("OpenAI LLM rerank response contained an invalid score value") from exc
            if index not in expected_indexes:
                raise ValueError(f"OpenAI LLM rerank returned an unexpected candidate index: {index}")
            scores[index] = min(1.0, max(0.0, score))
        missing = expected_indexes - scores.keys()
        if missing:
            raise ValueError(f"OpenAI LLM rerank response omitted candidate indexes: {sorted(missing)}")
        return scores


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


def create_reranker(model_id: str, params: dict[str, Any] | None = None) -> CrossEncoderReranker | VoyageReranker | OpenAILLMReranker:
    spec = get_reranker_model(model_id)
    normalized = normalize_reranker_params(model_id, params)
    if spec.provider == "sentence_transformers":
        return _cached_cross_encoder_reranker(spec, normalized)
    if spec.provider == "voyage":
        return VoyageReranker(spec, normalized)
    if spec.provider == "openai":
        return OpenAILLMReranker(spec, normalized)
    raise ValueError(f"Unsupported reranker provider: {spec.provider}")


def _cached_cross_encoder_reranker(
    spec: RerankerModelSpec,
    params: dict[str, Any],
) -> CrossEncoderReranker:
    cache_key = _model_cache_key(spec.id, params)
    with _LOCAL_RERANKER_CACHE_LOCK:
        cached = _LOCAL_RERANKER_CACHE.get(cache_key)
        if cached is not None:
            logger.debug("local reranker cache hit model_id=%s model_name=%s", spec.id, spec.model_name)
            return cached
        logger.info(
            "local reranker load start model_id=%s model_name=%s device=%s",
            spec.id,
            spec.model_name,
            params.get("device"),
        )
        reranker = CrossEncoderReranker(spec, dict(params))
        _LOCAL_RERANKER_CACHE[cache_key] = reranker
        logger.info(
            "local reranker load finished model_id=%s model_name=%s device=%s",
            spec.id,
            spec.model_name,
            params.get("device"),
        )
        return reranker


def _model_cache_key(model_id: str, params: dict[str, Any]) -> str:
    return stable_json_dumps({"model_id": model_id, "params": params})


def rerank_chunks(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    model_id: str,
    params: dict[str, Any] | None,
    text_by_chunk_id: dict[str, str],
) -> list[dict[str, Any]]:
    return rerank_chunks_with_usage(
        chunks=chunks,
        model_id=model_id,
        params=params,
        query=query,
        text_by_chunk_id=text_by_chunk_id,
    )["chunks"]


def rerank_chunks_with_usage(
    *,
    query: str,
    chunks: list[dict[str, Any]],
    model_id: str,
    params: dict[str, Any] | None,
    text_by_chunk_id: dict[str, str],
) -> dict[str, Any]:
    reranker = create_reranker(model_id, params)
    passages = [
        text_by_chunk_id.get(str(chunk.get("chunk_id") or ""), str(chunk.get("text_preview") or ""))
        for chunk in chunks
    ]
    scores = reranker.score(query, passages)
    original_scores = _normalized_original_scores(chunks)
    is_llm_reranker = isinstance(reranker, OpenAILLMReranker)
    llm_weight = float(reranker.params["llm_weight"]) if is_llm_reranker else 1.0
    retrieval_weight = float(reranker.params["retrieval_weight"]) if is_llm_reranker else 0.0
    weight_sum = llm_weight + retrieval_weight
    if is_llm_reranker and weight_sum <= 0:
        raise ValueError("OpenAI LLM reranker requires llm_weight + retrieval_weight to be greater than 0")
    reranked: list[dict[str, Any]] = []
    for original_rank, (chunk, score) in enumerate(zip(chunks, scores, strict=True), start=1):
        final_score = (
            ((llm_weight * score) + (retrieval_weight * original_scores[original_rank - 1])) / weight_sum
            if is_llm_reranker
            else score
        )
        reranked.append(
            {
                **chunk,
                **(
                    {
                        "llm_score": score,
                        "retrieval_score_normalized": original_scores[original_rank - 1],
                    }
                    if is_llm_reranker
                    else {}
                ),
                "original_rank": original_rank,
                "original_score": chunk.get("score"),
                "rerank_score": final_score,
                "score": final_score,
            }
        )
    return {
        "chunks": sorted(reranked, key=lambda chunk: float(chunk["rerank_score"]), reverse=True),
        "usage": getattr(reranker, "usage", {}),
    }


def _coerce_params(spec: RerankerModelSpec, params: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    fields_by_name = {field.name: field for field in spec.fields}
    for name, field in fields_by_name.items():
        value = params.get(name, field.default)
        if field.field_type == "number":
            try:
                value = float(value) if isinstance(field.default, float) else int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
            if field.min_value is not None and value < field.min_value:
                raise ValueError(f"{name} must be at least {field.min_value}")
            if field.max_value is not None and value > field.max_value:
                raise ValueError(f"{name} must be at most {field.max_value}")
        elif field.field_type == "boolean":
            value = _coerce_bool(value, name)
        elif field.field_type == "select":
            value = str(value)
            allowed = {option["value"] for option in field.options or []}
            if value not in allowed:
                raise ValueError(f"Unsupported value for {name}")
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


def _normalized_original_scores(chunks: list[dict[str, Any]]) -> list[float]:
    scores = [_safe_float(chunk.get("score")) for chunk in chunks]
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score > min_score:
        return [(score - min_score) / (max_score - min_score) for score in scores]
    return [min(1.0, max(0.0, score)) for score in scores]


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(result):
        return 0.0
    return result


def _usage_payload(**values: Any) -> dict[str, Any]:
    return {
        key: value
        for key, value in {
            **values,
            "duration_seconds": round(float(values.get("duration_seconds") or 0.0), 3),
            "estimated_cost_usd": round(float(values.get("estimated_cost_usd") or 0.0), 8),
        }.items()
        if value is not None
    }


def _openai_response_usage(response: httpx.Response) -> dict[str, int]:
    usage = response.json().get("usage") or {}
    input_tokens = _int_usage(usage.get("prompt_tokens", usage.get("input_tokens")))
    output_tokens = _int_usage(usage.get("completion_tokens", usage.get("output_tokens")))
    total_tokens = _int_usage(usage.get("total_tokens")) or input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _int_usage(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _openai_llm_rerank_estimated_cost(input_tokens: int, output_tokens: int) -> float:
    settings = get_settings()
    input_rate = float(getattr(settings, "openai_llm_rerank_input_cost_per_1m_tokens", 0.0) or 0.0)
    output_rate = float(getattr(settings, "openai_llm_rerank_output_cost_per_1m_tokens", 0.0) or 0.0)
    return ((input_tokens / 1_000_000.0) * input_rate) + ((output_tokens / 1_000_000.0) * output_rate)


def _voyage_rerank_estimated_cost(model_name: str, estimated_tokens: int) -> float:
    settings = get_settings()
    if model_name == "rerank-2.5-lite":
        rate = float(getattr(settings, "voyage_rerank_2_5_lite_cost_per_1m_tokens", 0.0) or 0.0)
    else:
        rate = float(getattr(settings, "voyage_rerank_2_5_cost_per_1m_tokens", 0.0) or 0.0)
    return (estimated_tokens / 1_000_000.0) * rate


def _openai_rerank_system_prompt(*, include_reasoning: bool) -> str:
    reasoning_instruction = (
        "Return a concise reason for each score."
        if include_reasoning
        else "Do not include reasoning; return only indexes and relevance scores."
    )
    return "\n".join(
        [
            "You are a reranking model for a RAG system.",
            "Score each candidate passage by how directly it helps answer the user question.",
            "Use relevance_score from 0.0 to 1.0 in 0.1-like increments when possible.",
            "0.0 means irrelevant or contradicts the question.",
            "0.3 means topical but not useful as answer evidence.",
            "0.5 means partial or weakly useful evidence.",
            "0.7 means useful evidence but incomplete.",
            "0.9 means directly answers the question.",
            "1.0 means decisive evidence with the exact answer.",
            "Prefer passages that answer the question over passages that merely share keywords.",
            "For not-found questions, score absence evidence highly only when the passage explicitly supports absence.",
            "Return every candidate exactly once and do not invent facts.",
            reasoning_instruction,
        ]
    )


def _openai_rerank_response_format(*, include_reasoning: bool) -> dict[str, Any]:
    item_properties: dict[str, Any] = {
        "index": {"type": "integer"},
        "relevance_score": {"maximum": 1, "minimum": 0, "type": "number"},
    }
    required = ["index", "relevance_score"]
    if include_reasoning:
        item_properties["reasoning"] = {"type": "string"}
        required.append("reasoning")
    return {
        "json_schema": {
            "name": "raglab_llm_rerank_scores",
            "schema": {
                "additionalProperties": False,
                "properties": {
                    "scores": {
                        "items": {
                            "additionalProperties": False,
                            "properties": item_properties,
                            "required": required,
                            "type": "object",
                        },
                        "type": "array",
                    }
                },
                "required": ["scores"],
                "type": "object",
            },
            "strict": True,
        },
        "type": "json_schema",
    }


def _openai_retry_delay(response: httpx.Response | None, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))


def _voyage_rerank_tpm_limit(settings: Any, model_name: str) -> int:
    if model_name == "rerank-2.5-lite":
        value = getattr(settings, "voyage_rerank_2_5_lite_tpm_limit", 0)
    else:
        value = getattr(settings, "voyage_rerank_2_5_tpm_limit", 0)
    return max(0, int(value or 0))


def _estimate_voyage_rerank_tokens(query: str, passages: list[str]) -> int:
    texts = [query, *passages]
    return sum(
        max(1, math.ceil(len(text) / VOYAGE_RERANK_TOKEN_CHARS) + VOYAGE_RERANK_TOKEN_OVERHEAD_PER_TEXT)
        for text in texts
    )


def _wait_for_voyage_rerank_capacity(
    *,
    estimated_tokens: int,
    rpm_limit: int,
    tpm_limit: int,
    tpm_utilization: float,
) -> None:
    global _VOYAGE_RERANK_NEXT_REQUEST_AT
    global _VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT
    global _VOYAGE_RERANK_TOKENS_USED_IN_WINDOW

    if rpm_limit <= 0 and tpm_limit <= 0:
        return

    usable_tpm_limit = max(1, int(tpm_limit * min(1.0, max(0.1, tpm_utilization)))) if tpm_limit > 0 else 0
    while True:
        with _VOYAGE_RERANK_THROTTLE_LOCK:
            now = time.monotonic()
            wait_seconds = 0.0
            wait_reason = ""
            if rpm_limit > 0 and now < _VOYAGE_RERANK_NEXT_REQUEST_AT:
                wait_seconds = max(wait_seconds, _VOYAGE_RERANK_NEXT_REQUEST_AT - now)
                wait_reason = "rpm"

            if usable_tpm_limit > 0:
                if (
                    _VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT == 0.0
                    or now - _VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT >= 60.0
                ):
                    _VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT = now
                    _VOYAGE_RERANK_TOKENS_USED_IN_WINDOW = 0
                token_charge = min(max(1, estimated_tokens), usable_tpm_limit)
                if _VOYAGE_RERANK_TOKENS_USED_IN_WINDOW + token_charge > usable_tpm_limit:
                    token_wait_seconds = 60.0 - (now - _VOYAGE_RERANK_TOKEN_WINDOW_STARTED_AT)
                    if token_wait_seconds >= wait_seconds:
                        wait_reason = "tpm"
                    wait_seconds = max(wait_seconds, token_wait_seconds)

            if wait_seconds <= 0.0:
                if rpm_limit > 0:
                    _VOYAGE_RERANK_NEXT_REQUEST_AT = now + (60.0 / rpm_limit)
                if usable_tpm_limit > 0:
                    _VOYAGE_RERANK_TOKENS_USED_IN_WINDOW += min(max(1, estimated_tokens), usable_tpm_limit)
                return

        logger.info(
            "voyage rerank throttle wait reason=%s wait_seconds=%.1f estimated_tokens=%s "
            "rpm_limit=%s tpm_limit=%s tpm_utilization=%.2f",
            wait_reason or "unknown",
            wait_seconds,
            estimated_tokens,
            rpm_limit,
            tpm_limit,
            tpm_utilization,
        )
        time.sleep(wait_seconds)


def _voyage_rerank_retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(60.0, float(2**attempt))


def _voyage_rerank_transport_retry_delay(attempt: int) -> float:
    return min(60.0, float(2**attempt))
