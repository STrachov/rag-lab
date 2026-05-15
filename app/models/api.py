from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JsonObject = dict[str, Any]


class HealthResponse(BaseModel):
    status: str


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    domain: str | None = None
    status: str = "active"
    metadata_json: JsonObject = Field(default_factory=dict)


class ProjectResponse(ProjectCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class DataAssetCreate(BaseModel):
    name: str
    asset_type: Literal["raw", "prepared"] = "raw"
    data_format: str = "mixed"
    storage_kind: str = "uploaded"
    parent_id: str | None = None
    storage_path: str | None = None
    manifest_hash: str | None = None
    preparation_params_json: JsonObject | None = None
    metadata_json: JsonObject = Field(default_factory=dict)
    status: str = "ready"


class DataAssetResponse(DataAssetCreate):
    id: str
    project_id: str
    created_at: datetime
    current_manifest_json: JsonObject | None = None

    model_config = ConfigDict(from_attributes=True)


class DataAssetListResponse(BaseModel):
    data_assets: list[DataAssetResponse]


class DataAssetFileDeleteResponse(BaseModel):
    data_asset: DataAssetResponse | None = None
    deleted_data_asset_id: str | None = None


class DataAssetDeleteResponse(BaseModel):
    deleted_data_asset_ids: list[str]


class PreparationMethodField(BaseModel):
    name: str
    label: str
    type: Literal["boolean", "select", "text"]
    default: Any
    help_text: str | None = None
    options: list[dict[str, str]] | None = None


class PreparationMethodResponse(BaseModel):
    id: str
    label: str
    description: str
    output_formats: list[str]
    fields: list[PreparationMethodField] = Field(default_factory=list)


class PreparationMethodListResponse(BaseModel):
    methods: list[PreparationMethodResponse]


class DataAssetPrepareRequest(BaseModel):
    name: str | None = None
    method: Literal["pymupdf_text", "docling"] = "pymupdf_text"
    settings: JsonObject = Field(default_factory=dict)


class ParameterSetCreate(BaseModel):
    name: str
    description: str | None = None
    category: str = "general"
    params_json: JsonObject
    params_hash: str


class ParameterSetResponse(ParameterSetCreate):
    id: str
    project_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParameterSetListResponse(BaseModel):
    parameter_sets: list[ParameterSetResponse]


class ParameterSetDeleteResponse(BaseModel):
    deleted_parameter_set_id: str


class ChunkingParams(BaseModel):
    strategy: str = "heading_recursive"
    params: JsonObject = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ChunkingStrategyField(BaseModel):
    name: str
    label: str
    type: Literal["number", "select", "boolean", "text"]
    default: Any
    help_text: str | None = None
    min: int | None = None
    max: int | None = None
    options: list[dict[str, str]] | None = None


class ChunkingStrategyResponse(BaseModel):
    id: str
    label: str
    description: str
    default_params: JsonObject
    fields: list[ChunkingStrategyField]


class ChunkingStrategyListResponse(BaseModel):
    strategies: list[ChunkingStrategyResponse]


class ChunkingPreviewRequest(BaseModel):
    data_asset_id: str
    chunking: ChunkingParams = Field(default_factory=ChunkingParams)
    max_chunks: int = Field(default=50, ge=1, le=200)
    text_preview_chars: int = Field(default=900, ge=120, le=4000)


class ChunkPreview(BaseModel):
    chunk_id: str
    source_name: str
    stored_path: str
    section: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    page: int | None = None
    token_count: int
    char_count: int
    text_preview: str


class ChunkingPreviewSummaryFile(BaseModel):
    source_name: str
    chunk_count: int


class ChunkingPreviewSummary(BaseModel):
    chunk_count: int
    files_count: int
    min_tokens: int
    avg_tokens: float
    max_tokens: int
    min_chars: int
    avg_chars: float
    max_chars: int
    chunks_by_file: list[ChunkingPreviewSummaryFile]
    strategy: str
    token_counter: str


class ChunkingPreviewResponse(BaseModel):
    summary: ChunkingPreviewSummary
    warnings: list[str] = Field(default_factory=list)
    chunks: list[ChunkPreview] = Field(default_factory=list)


class DerivedCacheResponse(BaseModel):
    id: str
    project_id: str
    data_asset_id: str | None = None
    params_hash: str
    cache_type: Literal["chunks", "embeddings", "qdrant_index", "retrieval_temp", "answer_temp"]
    cache_key: str
    status: str
    metadata_json: JsonObject
    created_at: datetime
    last_used_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DerivedCacheListResponse(BaseModel):
    derived_caches: list[DerivedCacheResponse]


class ChunkMaterializeRequest(BaseModel):
    data_asset_id: str
    chunking: ChunkingParams = Field(default_factory=ChunkingParams)


class EmbeddingModelField(BaseModel):
    name: str
    label: str
    type: Literal["number", "select", "boolean", "text"]
    default: Any
    help_text: str | None = None
    min: int | None = None
    max: int | None = None
    options: list[dict[str, str]] | None = None


class EmbeddingModelResponse(BaseModel):
    id: str
    label: str
    description: str
    provider: str
    model_name: str
    vector_size: int
    default_params: JsonObject
    fields: list[EmbeddingModelField]


class EmbeddingModelListResponse(BaseModel):
    models: list[EmbeddingModelResponse]


class SparseModelField(BaseModel):
    name: str
    label: str
    type: Literal["number", "select", "boolean", "text"]
    default: Any
    help_text: str | None = None
    min: float | int | None = None
    max: float | int | None = None
    step: float | int | None = None


class SparseModelResponse(BaseModel):
    id: str
    label: str
    description: str
    provider: str
    default_params: JsonObject
    fields: list[SparseModelField]


class SparseModelListResponse(BaseModel):
    models: list[SparseModelResponse]


class RerankerModelField(BaseModel):
    name: str
    label: str
    type: Literal["number", "select", "boolean", "text"]
    default: Any
    help_text: str | None = None
    min: int | None = None
    max: int | None = None
    step: int | None = None
    options: list[dict[str, str]] | None = None


class RerankerModelResponse(BaseModel):
    id: str
    label: str
    description: str
    provider: str
    model_name: str
    backend: str
    default_params: JsonObject
    fields: list[RerankerModelField]


class RerankerModelListResponse(BaseModel):
    models: list[RerankerModelResponse]


class EmbeddingParams(BaseModel):
    model_id: str = "intfloat_multilingual_e5_small"
    params: JsonObject = Field(default_factory=dict)


class SparseParams(BaseModel):
    model_id: str = "bm25_local"
    params: JsonObject = Field(default_factory=dict)


class RerankingParams(BaseModel):
    enabled: bool = False
    model_id: str = "baai_bge_reranker_v2_m3"
    params: JsonObject = Field(default_factory=dict)


class QdrantIndexRequest(BaseModel):
    chunks_cache_id: str
    embedding: EmbeddingParams = Field(default_factory=EmbeddingParams)
    sparse: SparseParams | None = Field(default_factory=SparseParams)
    index_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    collection_name: str | None = None
    distance: Literal["Cosine", "Dot", "Euclid"] = "Cosine"


class RetrievalPreviewRequest(BaseModel):
    index_cache_id: str
    query: str
    mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_k: int | None = Field(default=None, ge=1, le=100)
    reranking: RerankingParams = Field(default_factory=RerankingParams)


class RerankPreviewRequest(BaseModel):
    retrieval_cache_id: str
    top_k: int = Field(default=5, ge=1, le=50)
    reranking: RerankingParams = Field(default_factory=lambda: RerankingParams(enabled=True))


class RetrievedChunk(BaseModel):
    chunk_id: str | None = None
    score: float | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    original_score: float | None = None
    original_rank: int | None = None
    source_name: str | None = None
    stored_path: str | None = None
    section: str | None = None
    heading_path: list[str] = Field(default_factory=list)
    page: int | None = None
    token_count: int | None = None
    char_count: int | None = None
    text_preview: str | None = None

    model_config = ConfigDict(extra="allow")


class RetrievalPreviewResponse(BaseModel):
    index_cache_id: str
    retrieval_cache_id: str | None = None
    mode: Literal["dense", "sparse", "hybrid"]
    query: str
    top_k: int
    candidate_k: int | None = None
    reranking: JsonObject | None = None
    retrieved_chunks: list[RetrievedChunk]


class GroundTruthSetResponse(BaseModel):
    id: str
    project_id: str
    name: str
    data_asset_id: str | None = None
    storage_path: str | None = None
    manifest_hash: str | None = None
    metadata_json: JsonObject = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroundTruthSetListResponse(BaseModel):
    ground_truth_sets: list[GroundTruthSetResponse]


class GroundTruthSetDeleteResponse(BaseModel):
    deleted_ground_truth_set_id: str


class GroundTruthQuestionResponse(BaseModel):
    question_id: str
    question: str
    question_type: str
    expected_answer_type: str
    relevant_chunk_count: int


class GroundTruthQuestionListResponse(BaseModel):
    questions: list[GroundTruthQuestionResponse]


class GroundTruthRankingScoreRequest(BaseModel):
    question_id: str
    retrieved_chunks: list[RetrievedChunk]
    k: int = Field(default=5, ge=1, le=100)
    index_cache_id: str | None = None


class GroundTruthRankingScoreResponse(BaseModel):
    question_id: str
    expected_answer_type: str
    k: int
    metrics: dict[str, float]
    warnings: list[str] = Field(default_factory=list)


class SavedExperimentCreate(BaseModel):
    name: str
    data_asset_id: str
    data_asset_manifest_hash: str | None = None
    ground_truth_set_id: str | None = None
    parameter_set_id: str | None = None
    params_snapshot_json: JsonObject
    params_hash: str
    metrics_summary_json: JsonObject = Field(default_factory=dict)
    status: str = "created"
    notes: str | None = None
    debug_level: Literal["none", "summary", "full"] = "none"
    code_commit: str | None = None
    pipeline_version: str | None = None
    error_json: JsonObject | None = None


class SavedExperimentResponse(SavedExperimentCreate):
    id: str
    project_id: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SavedExperimentListResponse(BaseModel):
    saved_experiments: list[SavedExperimentResponse]
