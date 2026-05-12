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


class DataAssetPrepareRequest(BaseModel):
    name: str | None = None
    method: Literal["pymupdf_text"] = "pymupdf_text"
    output_format: Literal["markdown"] = "markdown"
    page_breaks: bool = True


class ParameterSetCreate(BaseModel):
    name: str
    description: str | None = None
    params_json: JsonObject
    params_hash: str


class ParameterSetResponse(ParameterSetCreate):
    id: str
    project_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParameterSetListResponse(BaseModel):
    parameter_sets: list[ParameterSetResponse]


class GroundTruthSetCreate(BaseModel):
    name: str
    data_asset_id: str | None = None
    storage_path: str | None = None
    manifest_hash: str | None = None
    metadata_json: JsonObject = Field(default_factory=dict)


class GroundTruthSetResponse(GroundTruthSetCreate):
    id: str
    project_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroundTruthSetListResponse(BaseModel):
    ground_truth_sets: list[GroundTruthSetResponse]


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
