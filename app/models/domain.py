from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Dataset(BaseModel):
    dataset_id: str
    name: str
    description: str | None = None
    domain: str | None = None
    document_count: int = 0
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    document_id: str
    dataset_id: str
    source_name: str
    source_path: str | None = None
    mime_type: str | None = None
    text_hash: str | None = None
    char_count: int | None = None
    page_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    dataset_id: str
    text: str
    token_count: int | None = None
    source_page: int | None = None
    source_section: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkingConfig(BaseModel):
    config_id: str
    strategy: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingConfig(BaseModel):
    config_id: str
    provider: str
    model: str
    dimensions: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalConfig(BaseModel):
    config_id: str
    mode: str
    top_k: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptConfig(BaseModel):
    config_id: str
    template_path: str
    model: str
    temperature: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalSet(BaseModel):
    eval_set_id: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Experiment(BaseModel):
    experiment_id: str
    dataset_id: str
    eval_set_id: str
    chunking_config_id: str
    embedding_config_id: str
    retrieval_config_id: str
    prompt_config_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalTrace(BaseModel):
    trace_id: str
    experiment_id: str | None = None
    question_id: str | None = None
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)


class AnswerTrace(BaseModel):
    trace_id: str
    experiment_id: str | None = None
    prompt_template_id: str
    prompt_hash: str | None = None
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)


class ExperimentResult(BaseModel):
    experiment_id: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class Recipe(BaseModel):
    recipe_id: str
    name: str
    status: str = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)
