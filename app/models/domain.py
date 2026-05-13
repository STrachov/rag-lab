from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    description: str | None = None
    domain: str | None = None
    status: str = "active"
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DataAsset(BaseModel):
    id: str
    project_id: str
    name: str
    asset_type: Literal["raw", "prepared"]
    parent_id: str | None = None
    storage_path: str | None = None
    manifest_hash: str | None = None
    preparation_params_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ParameterSet(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None = None
    category: str = "general"
    params_json: dict[str, Any]
    params_hash: str
    created_at: datetime


class GroundTruthSet(BaseModel):
    id: str
    project_id: str
    name: str
    data_asset_id: str | None = None
    storage_path: str | None = None
    manifest_hash: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SavedExperiment(BaseModel):
    id: str
    project_id: str
    name: str
    data_asset_id: str
    ground_truth_set_id: str | None = None
    parameter_set_id: str | None = None
    params_snapshot_json: dict[str, Any]
    params_hash: str
    metrics_summary_json: dict[str, Any] = Field(default_factory=dict)
    status: str = "created"
    notes: str | None = None
    debug_level: Literal["none", "summary", "full"] = "none"
    code_commit: str | None = None
    pipeline_version: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_json: dict[str, Any] | None = None


class MetricValue(BaseModel):
    id: str
    saved_experiment_id: str
    metric_name: str
    metric_value: float
    metric_scope: str | None = None
    created_at: datetime


class DerivedCache(BaseModel):
    id: str
    project_id: str
    data_asset_id: str | None = None
    params_hash: str
    cache_type: Literal["chunks", "embeddings", "qdrant_index", "retrieval_temp", "answer_temp"]
    cache_key: str
    status: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    last_used_at: datetime | None = None
