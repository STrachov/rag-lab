import json
import shutil
from threading import Lock
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models
from app.db.session import get_db
from app.models.api import (
    ChunkingPreviewRequest,
    ChunkingPreviewResponse,
    ChunkingStrategyListResponse,
    DataAssetCreate,
    DataAssetDeleteResponse,
    DataAssetFileDeleteResponse,
    DataAssetListResponse,
    DataAssetPrepareRequest,
    DataAssetResponse,
    GroundTruthSetDeleteResponse,
    GroundTruthSetListResponse,
    GroundTruthSetResponse,
    GroundTruthQuestionListResponse,
    GroundTruthRankingScoreRequest,
    GroundTruthRankingScoreResponse,
    ParameterSetCreate,
    ParameterSetDeleteResponse,
    ParameterSetListResponse,
    ParameterSetResponse,
    PreparationMethodListResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    SavedExperimentCreate,
    SavedExperimentListResponse,
    SavedExperimentResponse,
)
from app.services.chunking import ChunkingParams as ServiceChunkingParams
from app.services.chunking import list_chunking_strategies
from app.services.chunking import preview_prepared_asset_chunks
from app.services.data_assets import (
    append_uploaded_data_asset_files,
    delete_data_asset_file,
    new_data_asset_id,
    resolve_manifest_file_path,
    store_generated_data_asset_files,
    store_uploaded_data_asset_files,
)
from app.services.ground_truth import (
    list_ground_truth_questions,
    new_ground_truth_set_id,
    score_ground_truth_ranking,
    store_uploaded_ground_truth_set,
)
from app.services.preparation import list_preparation_methods
from app.services.preparation import prepare_docling
from app.services.preparation import prepare_pymupdf_text

router = APIRouter()
_active_preparation_jobs: set[tuple[str, str, str]] = set()
_active_preparation_jobs_lock = Lock()


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db)) -> ProjectListResponse:
    projects = db.scalars(select(models.Project).order_by(models.Project.created_at)).all()
    return ProjectListResponse(projects=projects)


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> models.Project:
    project = models.Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)) -> models.Project:
    return _get_project_or_404(db, project_id)


@router.get("/projects/{project_id}/data-assets", response_model=DataAssetListResponse)
def list_data_assets(project_id: str, db: Session = Depends(get_db)) -> DataAssetListResponse:
    _get_project_or_404(db, project_id)
    assets = db.scalars(
        select(models.DataAsset)
        .where(models.DataAsset.project_id == project_id)
        .order_by(models.DataAsset.created_at)
    ).all()
    return DataAssetListResponse(
        data_assets=[_build_data_asset_response(db, asset) for asset in assets]
    )


@router.post(
    "/projects/{project_id}/data-assets",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_data_asset(
    project_id: str,
    payload: DataAssetCreate,
    db: Session = Depends(get_db),
) -> DataAssetResponse:
    _get_project_or_404(db, project_id)
    _validate_data_asset_payload(db, project_id, payload)
    asset = models.DataAsset(project_id=project_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _build_data_asset_response(db, asset)


@router.post(
    "/projects/{project_id}/data-assets/raw/upload",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_raw_data_asset(
    project_id: str,
    name: str = Form(...),
    data_format: str = Form("pdf"),
    metadata_json: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> DataAssetResponse:
    _get_project_or_404(db, project_id)
    asset_id = new_data_asset_id()
    stored = _store_upload_or_400(
        project_id=project_id,
        asset_id=asset_id,
        asset_type="raw",
        files=files,
    )
    metadata = _parse_json_object(metadata_json, "metadata_json") if metadata_json else {}
    asset = models.DataAsset(
        id=asset_id,
        project_id=project_id,
        name=name,
        asset_type="raw",
        data_format=data_format,
        storage_kind="uploaded",
        storage_path=stored["storage_path"],
        manifest_hash=stored["manifest_hash"],
        metadata_json=metadata,
        status="ready",
    )
    db.add(asset)
    _add_manifest_snapshot(db, asset_id, stored["manifest_hash"], stored["manifest_json"])
    db.commit()
    db.refresh(asset)
    return _build_data_asset_response(db, asset)


@router.post(
    "/projects/{project_id}/data-assets/prepared/upload",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_prepared_data_asset(
    project_id: str,
    name: str = Form(...),
    data_format: str = Form("markdown"),
    parent_id: str | None = Form(None),
    preparation_params_json: str = Form(...),
    metadata_json: str | None = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> DataAssetResponse:
    _get_project_or_404(db, project_id)
    preparation_params = _parse_json_object(
        preparation_params_json,
        "preparation_params_json",
    )
    _validate_prepared_provenance(preparation_params)
    if parent_id is not None:
        _get_project_child_or_404(db, models.DataAsset, project_id, parent_id, "data asset")
        _require_data_asset_type(db, parent_id, "raw")

    asset_id = new_data_asset_id()
    stored = _store_upload_or_400(
        project_id=project_id,
        asset_id=asset_id,
        asset_type="prepared",
        files=files,
        parent_id=parent_id,
        preparation_params_json=preparation_params,
    )
    metadata = _parse_json_object(metadata_json, "metadata_json") if metadata_json else {}
    asset = models.DataAsset(
        id=asset_id,
        project_id=project_id,
        name=name,
        asset_type="prepared",
        data_format=data_format,
        storage_kind="uploaded",
        parent_id=parent_id,
        storage_path=stored["storage_path"],
        manifest_hash=stored["manifest_hash"],
        preparation_params_json=preparation_params,
        metadata_json=metadata,
        status="ready",
    )
    db.add(asset)
    _add_manifest_snapshot(db, asset_id, stored["manifest_hash"], stored["manifest_json"])
    db.commit()
    db.refresh(asset)
    return _build_data_asset_response(db, asset)


@router.post(
    "/projects/{project_id}/data-assets/{data_asset_id}/files",
    response_model=DataAssetResponse,
)
def add_data_asset_files(
    project_id: str,
    data_asset_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> DataAssetResponse:
    _get_project_or_404(db, project_id)
    asset = _get_data_asset_or_404(db, project_id, data_asset_id)
    current_manifest = _get_current_manifest_json(db, asset)
    stored = _append_upload_or_400(
        storage_path=asset.storage_path,
        current_manifest=current_manifest,
        files=files,
    )
    asset.manifest_hash = stored["manifest_hash"]
    _add_manifest_snapshot(db, asset.id, stored["manifest_hash"], stored["manifest_json"])
    db.commit()
    db.refresh(asset)
    return _build_data_asset_response(db, asset)


@router.delete(
    "/projects/{project_id}/data-assets/{data_asset_id}/files",
    response_model=DataAssetFileDeleteResponse,
)
def remove_data_asset_file(
    project_id: str,
    data_asset_id: str,
    stored_path: str = Query(...),
    db: Session = Depends(get_db),
) -> DataAssetFileDeleteResponse:
    _get_project_or_404(db, project_id)
    asset = _get_data_asset_or_404(db, project_id, data_asset_id)
    current_manifest = _get_current_manifest_json(db, asset)
    stored = _delete_file_or_400(
        storage_path=asset.storage_path,
        current_manifest=current_manifest,
        stored_path=stored_path,
    )
    asset.manifest_hash = stored["manifest_hash"]
    _add_manifest_snapshot(db, asset.id, stored["manifest_hash"], stored["manifest_json"])

    if asset.asset_type == "prepared" and not stored["manifest_json"].get("files"):
        deleted_asset_id = asset.id
        _delete_asset_storage(asset.storage_path)
        db.delete(asset)
        db.commit()
        return DataAssetFileDeleteResponse(deleted_data_asset_id=deleted_asset_id)

    db.commit()
    db.refresh(asset)
    return DataAssetFileDeleteResponse(data_asset=_build_data_asset_response(db, asset))


@router.delete(
    "/projects/{project_id}/data-assets/{data_asset_id}",
    response_model=DataAssetDeleteResponse,
)
def delete_data_asset(
    project_id: str,
    data_asset_id: str,
    db: Session = Depends(get_db),
) -> DataAssetDeleteResponse:
    _get_project_or_404(db, project_id)
    asset = _get_data_asset_or_404(db, project_id, data_asset_id)
    assets_to_delete = _collect_deletable_data_assets(db, project_id, asset)
    deleted_ids = [item.id for item in assets_to_delete]

    for item in assets_to_delete:
        _delete_asset_storage(item.storage_path)
        db.delete(item)

    db.commit()
    return DataAssetDeleteResponse(deleted_data_asset_ids=deleted_ids)


@router.get("/projects/{project_id}/data-assets/{data_asset_id}/files/download")
def download_data_asset_file(
    project_id: str,
    data_asset_id: str,
    stored_path: str = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    _get_project_or_404(db, project_id)
    asset = _get_data_asset_or_404(db, project_id, data_asset_id)
    current_manifest = _get_current_manifest_json(db, asset)
    path, file_entry = _resolve_file_or_400(
        storage_path=asset.storage_path,
        current_manifest=current_manifest,
        stored_path=stored_path,
    )
    return FileResponse(
        path,
        filename=str(file_entry.get("original_name") or path.name),
        media_type=file_entry.get("content_type") or "application/octet-stream",
    )


@router.post(
    "/projects/{project_id}/data-assets/{data_asset_id}/prepare",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def prepare_data_asset(
    project_id: str,
    data_asset_id: str,
    payload: DataAssetPrepareRequest,
    db: Session = Depends(get_db),
) -> DataAssetResponse:
    _get_project_or_404(db, project_id)
    source_asset = _get_data_asset_or_404(db, project_id, data_asset_id)
    _require_data_asset_type(db, source_asset.id, "raw")
    source_manifest = _get_current_manifest_json(db, source_asset)

    if source_asset.storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source data asset has no storage path",
        )

    job_key = (project_id, source_asset.id, payload.method)
    _claim_preparation_job(job_key)
    try:
        preparation_params = _build_preparation_params(source_asset, source_manifest, payload)
        try:
            generated_files = _prepare_generated_files(
                payload=payload,
                source_asset=source_asset,
                source_manifest=source_manifest,
            )
            asset_id = new_data_asset_id()
            stored = store_generated_data_asset_files(
                project_id=project_id,
                asset_id=asset_id,
                asset_type="prepared",
                generated_files=generated_files,
                parent_id=source_asset.id,
                preparation_params_json=preparation_params,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        asset = models.DataAsset(
            id=asset_id,
            project_id=project_id,
            name=payload.name or f"{source_asset.name} {payload.method}",
            asset_type="prepared",
            data_format="mixed" if payload.method == "docling" else "markdown",
            storage_kind="generated",
            parent_id=source_asset.id,
            storage_path=stored["storage_path"],
            manifest_hash=stored["manifest_hash"],
            preparation_params_json=preparation_params,
            metadata_json={},
            status="ready",
        )
        db.add(asset)
        _add_manifest_snapshot(db, asset_id, stored["manifest_hash"], stored["manifest_json"])
        db.commit()
        db.refresh(asset)
        return _build_data_asset_response(db, asset)
    finally:
        _release_preparation_job(job_key)


@router.get(
    "/projects/{project_id}/data-assets/preparation/methods",
    response_model=PreparationMethodListResponse,
)
def list_project_preparation_methods(
    project_id: str,
    db: Session = Depends(get_db),
) -> PreparationMethodListResponse:
    _get_project_or_404(db, project_id)
    return PreparationMethodListResponse.model_validate({"methods": list_preparation_methods()})


@router.get("/projects/{project_id}/parameter-sets", response_model=ParameterSetListResponse)
def list_parameter_sets(project_id: str, db: Session = Depends(get_db)) -> ParameterSetListResponse:
    _get_project_or_404(db, project_id)
    parameter_sets = db.scalars(
        select(models.ParameterSet)
        .where(models.ParameterSet.project_id == project_id)
        .order_by(models.ParameterSet.created_at)
    ).all()
    return ParameterSetListResponse(parameter_sets=parameter_sets)


@router.get(
    "/projects/{project_id}/parameter-sets/chunking/strategies",
    response_model=ChunkingStrategyListResponse,
)
def list_project_chunking_strategies(
    project_id: str,
    db: Session = Depends(get_db),
) -> ChunkingStrategyListResponse:
    _get_project_or_404(db, project_id)
    return ChunkingStrategyListResponse.model_validate({"strategies": list_chunking_strategies()})


@router.post(
    "/projects/{project_id}/parameter-sets",
    response_model=ParameterSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_parameter_set(
    project_id: str,
    payload: ParameterSetCreate,
    db: Session = Depends(get_db),
) -> models.ParameterSet:
    _get_project_or_404(db, project_id)
    parameter_set = models.ParameterSet(project_id=project_id, **payload.model_dump())
    db.add(parameter_set)
    db.commit()
    db.refresh(parameter_set)
    return parameter_set


@router.delete(
    "/projects/{project_id}/parameter-sets/{parameter_set_id}",
    response_model=ParameterSetDeleteResponse,
)
def delete_parameter_set(
    project_id: str,
    parameter_set_id: str,
    db: Session = Depends(get_db),
) -> ParameterSetDeleteResponse:
    _get_project_or_404(db, project_id)
    parameter_set = _get_parameter_set_or_404(db, project_id, parameter_set_id)
    used_by_experiment = db.scalar(
        select(models.SavedExperiment.id)
        .where(models.SavedExperiment.project_id == project_id)
        .where(models.SavedExperiment.parameter_set_id == parameter_set_id)
    )
    if used_by_experiment is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete parameter set used by saved experiments",
        )

    db.delete(parameter_set)
    db.commit()
    return ParameterSetDeleteResponse(deleted_parameter_set_id=parameter_set_id)


@router.post(
    "/projects/{project_id}/parameter-sets/chunking/preview",
    response_model=ChunkingPreviewResponse,
)
def preview_chunking(
    project_id: str,
    payload: ChunkingPreviewRequest,
    db: Session = Depends(get_db),
) -> ChunkingPreviewResponse:
    _get_project_or_404(db, project_id)
    asset = _get_data_asset_or_404(db, project_id, payload.data_asset_id)
    _require_data_asset_type(db, payload.data_asset_id, "prepared")
    manifest_json = _get_current_manifest_json(db, asset)
    if asset.storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Prepared data asset has no storage path",
        )

    try:
        preview = preview_prepared_asset_chunks(
            storage_path=asset.storage_path,
            manifest_json=manifest_json,
            chunking=ServiceChunkingParams(**payload.chunking.model_dump()),
            max_chunks=payload.max_chunks,
            text_preview_chars=payload.text_preview_chars,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ChunkingPreviewResponse.model_validate(preview)


@router.get("/projects/{project_id}/ground-truth-sets", response_model=GroundTruthSetListResponse)
def list_ground_truth_sets(
    project_id: str,
    db: Session = Depends(get_db),
) -> GroundTruthSetListResponse:
    _get_project_or_404(db, project_id)
    ground_truth_sets = db.scalars(
        select(models.GroundTruthSet)
        .where(models.GroundTruthSet.project_id == project_id)
        .order_by(models.GroundTruthSet.created_at)
    ).all()
    return GroundTruthSetListResponse(ground_truth_sets=ground_truth_sets)


@router.post(
    "/projects/{project_id}/ground-truth-sets/upload",
    response_model=GroundTruthSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_ground_truth_set(
    project_id: str,
    name: str = Form(...),
    data_asset_id: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> models.GroundTruthSet:
    _get_project_or_404(db, project_id)
    data_asset = None

    if data_asset_id is not None:
        data_asset = _get_data_asset_or_404(db, project_id, data_asset_id)
        _require_data_asset_type(db, data_asset_id, "prepared")

    ground_truth_set_id = new_ground_truth_set_id()
    try:
        stored = store_uploaded_ground_truth_set(
            data_asset=data_asset,
            file=file,
            ground_truth_set_id=ground_truth_set_id,
            project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ground_truth_set = models.GroundTruthSet(
        id=ground_truth_set_id,
        project_id=project_id,
        name=name,
        data_asset_id=data_asset.id if data_asset else None,
        storage_path=stored["storage_path"],
        manifest_hash=stored["manifest_hash"],
        metadata_json=stored["metadata_json"],
    )
    db.add(ground_truth_set)
    db.commit()
    db.refresh(ground_truth_set)
    return ground_truth_set


@router.get("/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/files/{file_kind}")
def download_ground_truth_set_file(
    project_id: str,
    ground_truth_set_id: str,
    file_kind: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    _get_project_or_404(db, project_id)
    ground_truth_set = _get_ground_truth_set_or_404(db, project_id, ground_truth_set_id)
    path, filename, media_type = _resolve_ground_truth_file_or_404(
        project_id,
        ground_truth_set,
        file_kind,
    )
    return FileResponse(path, filename=filename, media_type=media_type)


@router.get(
    "/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/questions",
    response_model=GroundTruthQuestionListResponse,
)
def list_ground_truth_set_questions(
    project_id: str,
    ground_truth_set_id: str,
    db: Session = Depends(get_db),
) -> GroundTruthQuestionListResponse:
    _get_project_or_404(db, project_id)
    ground_truth_set = _get_ground_truth_set_or_404(db, project_id, ground_truth_set_id)
    try:
        questions = list_ground_truth_questions(ground_truth_set)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GroundTruthQuestionListResponse(questions=questions)


@router.post(
    "/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}/score-ranking",
    response_model=GroundTruthRankingScoreResponse,
)
def score_ground_truth_set_ranking(
    project_id: str,
    ground_truth_set_id: str,
    payload: GroundTruthRankingScoreRequest,
    db: Session = Depends(get_db),
) -> GroundTruthRankingScoreResponse:
    _get_project_or_404(db, project_id)
    ground_truth_set = _get_ground_truth_set_or_404(db, project_id, ground_truth_set_id)
    index_cache = None
    if payload.index_cache_id is not None:
        index_cache = _get_project_cache_or_404(db, project_id, payload.index_cache_id)
        if index_cache.cache_type != "qdrant_index":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="index_cache_id must reference a qdrant_index cache",
            )
    try:
        scored = score_ground_truth_ranking(
            ground_truth_set=ground_truth_set,
            index_cache=index_cache,
            k=payload.k,
            question_id=payload.question_id,
            retrieved_chunks=[
                chunk.model_dump(mode="json", exclude_none=True)
                for chunk in payload.retrieved_chunks
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GroundTruthRankingScoreResponse.model_validate(scored)


@router.delete(
    "/projects/{project_id}/ground-truth-sets/{ground_truth_set_id}",
    response_model=GroundTruthSetDeleteResponse,
)
def delete_ground_truth_set(
    project_id: str,
    ground_truth_set_id: str,
    db: Session = Depends(get_db),
) -> GroundTruthSetDeleteResponse:
    _get_project_or_404(db, project_id)
    ground_truth_set = _get_ground_truth_set_or_404(db, project_id, ground_truth_set_id)
    used_by_experiment = db.scalar(
        select(models.SavedExperiment.id)
        .where(models.SavedExperiment.project_id == project_id)
        .where(models.SavedExperiment.ground_truth_set_id == ground_truth_set_id)
    )
    if used_by_experiment is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete ground truth set used by saved experiments",
        )

    _delete_ground_truth_storage(project_id, ground_truth_set.storage_path)
    db.delete(ground_truth_set)
    db.commit()
    return GroundTruthSetDeleteResponse(deleted_ground_truth_set_id=ground_truth_set_id)


@router.get("/projects/{project_id}/saved-experiments", response_model=SavedExperimentListResponse)
def list_saved_experiments(
    project_id: str,
    db: Session = Depends(get_db),
) -> SavedExperimentListResponse:
    _get_project_or_404(db, project_id)
    saved_experiments = db.scalars(
        select(models.SavedExperiment)
        .where(models.SavedExperiment.project_id == project_id)
        .order_by(models.SavedExperiment.created_at)
    ).all()
    return SavedExperimentListResponse(saved_experiments=saved_experiments)


@router.post(
    "/projects/{project_id}/saved-experiments",
    response_model=SavedExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_saved_experiment(
    project_id: str,
    payload: SavedExperimentCreate,
    db: Session = Depends(get_db),
) -> models.SavedExperiment:
    _get_project_or_404(db, project_id)
    _get_project_child_or_404(db, models.DataAsset, project_id, payload.data_asset_id, "data asset")
    _require_data_asset_type(db, payload.data_asset_id, "prepared")

    if payload.parameter_set_id is not None:
        _get_project_child_or_404(
            db,
            models.ParameterSet,
            project_id,
            payload.parameter_set_id,
            "parameter set",
        )

    if payload.ground_truth_set_id is not None:
        _get_project_child_or_404(
            db,
            models.GroundTruthSet,
            project_id,
            payload.ground_truth_set_id,
            "ground truth set",
        )

    data_asset = db.get(models.DataAsset, payload.data_asset_id)
    saved_experiment_payload = payload.model_dump()
    saved_experiment_payload["data_asset_manifest_hash"] = data_asset.manifest_hash
    saved_experiment = models.SavedExperiment(project_id=project_id, **saved_experiment_payload)
    db.add(saved_experiment)
    db.commit()
    db.refresh(saved_experiment)
    return saved_experiment


def _get_project_or_404(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_project_child_or_404(
    db: Session,
    model: type[models.DataAsset] | type[models.ParameterSet] | type[models.GroundTruthSet],
    project_id: str,
    child_id: str,
    label: str,
) -> None:
    item = db.get(model, child_id)
    if item is None or item.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label.title()} not found")


def _get_data_asset_or_404(db: Session, project_id: str, data_asset_id: str) -> models.DataAsset:
    asset = db.get(models.DataAsset, data_asset_id)
    if asset is None or asset.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data asset not found")
    return asset


def _get_ground_truth_set_or_404(
    db: Session,
    project_id: str,
    ground_truth_set_id: str,
) -> models.GroundTruthSet:
    ground_truth_set = db.get(models.GroundTruthSet, ground_truth_set_id)
    if ground_truth_set is None or ground_truth_set.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ground truth set not found")
    return ground_truth_set


def _get_project_cache_or_404(db: Session, project_id: str, cache_id: str) -> models.DerivedCache:
    cache = db.get(models.DerivedCache, cache_id)
    if cache is None or cache.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Derived cache not found")
    return cache


def _get_parameter_set_or_404(
    db: Session,
    project_id: str,
    parameter_set_id: str,
) -> models.ParameterSet:
    parameter_set = db.get(models.ParameterSet, parameter_set_id)
    if parameter_set is None or parameter_set.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parameter set not found")
    return parameter_set


def _build_data_asset_response(db: Session, asset: models.DataAsset) -> DataAssetResponse:
    return DataAssetResponse.model_validate(asset).model_copy(
        update={"current_manifest_json": _get_current_manifest_json(db, asset, required=False)}
    )


def _get_current_manifest_json(
    db: Session,
    asset: models.DataAsset,
    *,
    required: bool = True,
) -> dict | None:
    if asset.manifest_hash is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data asset has no current manifest",
            )
        return None

    manifest = db.scalar(
        select(models.DataAssetManifest)
        .where(models.DataAssetManifest.data_asset_id == asset.id)
        .where(models.DataAssetManifest.manifest_hash == asset.manifest_hash)
        .order_by(models.DataAssetManifest.created_at.desc())
    )
    if manifest is None:
        if required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current data asset manifest snapshot not found",
            )
        return None
    return manifest.manifest_json


def _add_manifest_snapshot(
    db: Session,
    data_asset_id: str,
    manifest_hash: str,
    manifest_json: dict,
) -> None:
    db.add(
        models.DataAssetManifest(
            data_asset_id=data_asset_id,
            manifest_hash=manifest_hash,
            manifest_json=manifest_json,
        )
    )


def _collect_deletable_data_assets(
    db: Session,
    project_id: str,
    asset: models.DataAsset,
) -> list[models.DataAsset]:
    children = db.scalars(
        select(models.DataAsset)
        .where(models.DataAsset.project_id == project_id)
        .where(models.DataAsset.parent_id == asset.id)
    ).all()
    assets = [asset, *children]
    used_asset_ids = {
        row[0]
        for row in db.execute(
            select(models.SavedExperiment.data_asset_id).where(
                models.SavedExperiment.data_asset_id.in_([item.id for item in assets])
            )
        ).all()
    }
    if used_asset_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete data asset used by saved experiments",
        )
    return list(reversed(assets))


def _claim_preparation_job(job_key: tuple[str, str, str]) -> None:
    with _active_preparation_jobs_lock:
        if job_key in _active_preparation_jobs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Preparation is already running for this source asset and method",
            )
        _active_preparation_jobs.add(job_key)


def _release_preparation_job(job_key: tuple[str, str, str]) -> None:
    with _active_preparation_jobs_lock:
        _active_preparation_jobs.discard(job_key)


def _build_preparation_params(
    source_asset: models.DataAsset,
    source_manifest: dict,
    payload: DataAssetPrepareRequest,
) -> dict:
    settings = _normalize_preparation_settings(payload)
    if payload.method == "docling":
        base_url = _docling_base_url(settings)
        return {
            "method": "docling",
            "output_format": "markdown_json",
            "output_formats": ["markdown", "json"],
            "settings": {
                "do_ocr": settings["do_ocr"],
                "force_ocr": settings["force_ocr"],
                "image_export_mode": settings["image_export_mode"],
            },
            "service": {"base_url": base_url},
            "source_format": source_asset.data_format,
            "source_manifest_hash": source_manifest.get("manifest_hash"),
            "tool": "docling",
        }

    return {
        "method": "pymupdf_text",
        "output_format": "markdown",
        "settings": {"page_breaks": settings["page_breaks"]},
        "source_format": source_asset.data_format,
        "source_manifest_hash": source_manifest.get("manifest_hash"),
        "tool": "pymupdf",
    }


def _prepare_generated_files(
    *,
    payload: DataAssetPrepareRequest,
    source_asset: models.DataAsset,
    source_manifest: dict,
) -> list[dict]:
    if source_asset.storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source data asset has no storage path",
        )

    settings = _normalize_preparation_settings(payload)
    if payload.method == "docling":
        return prepare_docling(
            source_storage_path=source_asset.storage_path,
            source_manifest=source_manifest,
            base_url=_docling_base_url(settings),
            do_ocr=settings["do_ocr"],
            force_ocr=settings["force_ocr"],
            image_export_mode=settings["image_export_mode"],
        )

    return prepare_pymupdf_text(
        source_storage_path=source_asset.storage_path,
        source_manifest=source_manifest,
        page_breaks=settings["page_breaks"],
    )


def _normalize_preparation_settings(payload: DataAssetPrepareRequest) -> dict:
    if payload.method == "docling":
        return {
            "base_url": str(payload.settings.get("base_url") or get_settings().docling_base_url),
            "do_ocr": _bool_setting(payload.settings, "do_ocr", True),
            "force_ocr": _bool_setting(payload.settings, "force_ocr", False),
            "image_export_mode": _choice_setting(
                payload.settings,
                "image_export_mode",
                "placeholder",
                {"placeholder", "embedded"},
            ),
        }

    return {"page_breaks": _bool_setting(payload.settings, "page_breaks", True)}


def _docling_base_url(settings: dict) -> str:
    base_url = str(settings.get("base_url") or "").strip()
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Docling base_url cannot be empty",
        )
    return base_url


def _bool_setting(settings: dict, name: str, default: bool) -> bool:
    value = settings.get(name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _choice_setting(settings: dict, name: str, default: str, allowed: set[str]) -> str:
    value = str(settings.get(name) or default).strip().lower()
    if value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported value for {name}: {value}",
        )
    return value


def _validate_data_asset_payload(
    db: Session,
    project_id: str,
    payload: DataAssetCreate,
) -> None:
    if payload.asset_type == "raw" and payload.parent_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Raw data assets cannot have a parent data asset",
        )

    if payload.parent_id is not None:
        _get_project_child_or_404(db, models.DataAsset, project_id, payload.parent_id, "data asset")
        _require_data_asset_type(db, payload.parent_id, "raw")

    if payload.asset_type == "prepared":
        if payload.preparation_params_json is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prepared data assets require preparation_params_json",
            )
        _validate_prepared_provenance(payload.preparation_params_json)


def _validate_prepared_provenance(preparation_params: dict) -> None:
    missing = [
        field
        for field in ("method", "output_format")
        if not str(preparation_params.get(field, "")).strip()
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prepared data provenance missing required fields: {', '.join(missing)}",
        )


def _require_data_asset_type(db: Session, data_asset_id: str, asset_type: str) -> None:
    asset = db.get(models.DataAsset, data_asset_id)
    if asset is None or asset.asset_type != asset_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parent data asset must be {asset_type}",
        )


def _parse_json_object(raw_json: str, field_name: str) -> dict:
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be valid JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a JSON object",
        )
    return parsed


def _store_upload_or_400(
    *,
    project_id: str,
    asset_id: str,
    asset_type: str,
    files: list[UploadFile],
    parent_id: str | None = None,
    preparation_params_json: dict | None = None,
) -> dict:
    try:
        return store_uploaded_data_asset_files(
            project_id=project_id,
            asset_id=asset_id,
            asset_type=asset_type,
            files=files,
            parent_id=parent_id,
            preparation_params_json=preparation_params_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _append_upload_or_400(
    *,
    storage_path: str | None,
    current_manifest: dict,
    files: list[UploadFile],
) -> dict:
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data asset has no storage path",
        )
    try:
        return append_uploaded_data_asset_files(
            storage_path=storage_path,
            current_manifest=current_manifest,
            files=files,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _delete_file_or_400(
    *,
    storage_path: str | None,
    current_manifest: dict,
    stored_path: str,
) -> dict:
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data asset has no storage path",
        )
    try:
        return delete_data_asset_file(
            storage_path=storage_path,
            current_manifest=current_manifest,
            stored_path=stored_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def _resolve_file_or_400(
    *,
    storage_path: str | None,
    current_manifest: dict,
    stored_path: str,
) -> tuple[Path, dict]:
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data asset has no storage path",
        )
    try:
        return resolve_manifest_file_path(
            storage_path=storage_path,
            current_manifest=current_manifest,
            stored_path=stored_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _delete_asset_storage(storage_path: str | None) -> None:
    if storage_path is None:
        return
    path = Path(storage_path)
    if path.exists():
        shutil.rmtree(path)


def _delete_ground_truth_storage(project_id: str, storage_path: str | None) -> None:
    try:
        ground_truth_dir = _ground_truth_storage_dir(project_id, storage_path)
    except HTTPException:
        raise
    except OSError:
        return
    if ground_truth_dir.exists():
        shutil.rmtree(ground_truth_dir)


def _resolve_ground_truth_file_or_404(
    project_id: str,
    ground_truth_set: models.GroundTruthSet,
    file_kind: str,
) -> tuple[Path, str, str]:
    ground_truth_dir = _ground_truth_storage_dir(project_id, ground_truth_set.storage_path)
    if file_kind == "canonical":
        path = ground_truth_dir / "ground_truth.json"
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Canonical ground truth file not found")
        return path, "ground_truth.canonical.json", "application/json"
    if file_kind != "original":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_kind must be canonical or original",
        )

    manifest_path = ground_truth_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ground truth manifest not found")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ground truth manifest is invalid",
        ) from exc
    original = manifest.get("original") or {}
    stored_path = original.get("stored_path")
    if not isinstance(stored_path, str):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original ground truth file not found")
    path = ground_truth_dir / stored_path
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original ground truth file not found")
    filename = str(original.get("original_name") or path.name)
    media_type = str(original.get("content_type") or "application/octet-stream")
    return path, filename, media_type


def _ground_truth_storage_dir(project_id: str, storage_path: str | None) -> Path:
    if storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ground truth set has no storage path",
        )
    path = Path(storage_path)
    ground_truth_dir = path.parent
    root = get_settings().data_dir / "ground_truth" / project_id / "ground_truths"
    resolved_dir = ground_truth_dir.resolve()
    resolved_root = root.resolve()
    if resolved_root not in resolved_dir.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ground truth storage path is outside project ground truth storage",
        )
    if not ground_truth_dir.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ground truth storage is missing")
    return ground_truth_dir
