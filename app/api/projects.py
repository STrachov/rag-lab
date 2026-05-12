import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.models.api import (
    DataAssetCreate,
    DataAssetListResponse,
    DataAssetResponse,
    GroundTruthSetCreate,
    GroundTruthSetListResponse,
    GroundTruthSetResponse,
    ParameterSetCreate,
    ParameterSetListResponse,
    ParameterSetResponse,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    SavedExperimentCreate,
    SavedExperimentListResponse,
    SavedExperimentResponse,
)
from app.services.data_assets import (
    append_uploaded_data_asset_files,
    delete_data_asset_file,
    new_data_asset_id,
    store_uploaded_data_asset_files,
)

router = APIRouter()


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
    response_model=DataAssetResponse,
)
def remove_data_asset_file(
    project_id: str,
    data_asset_id: str,
    stored_path: str = Query(...),
    db: Session = Depends(get_db),
) -> DataAssetResponse:
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
    db.commit()
    db.refresh(asset)
    return _build_data_asset_response(db, asset)


@router.get("/projects/{project_id}/parameter-sets", response_model=ParameterSetListResponse)
def list_parameter_sets(project_id: str, db: Session = Depends(get_db)) -> ParameterSetListResponse:
    _get_project_or_404(db, project_id)
    parameter_sets = db.scalars(
        select(models.ParameterSet)
        .where(models.ParameterSet.project_id == project_id)
        .order_by(models.ParameterSet.created_at)
    ).all()
    return ParameterSetListResponse(parameter_sets=parameter_sets)


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
    "/projects/{project_id}/ground-truth-sets",
    response_model=GroundTruthSetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ground_truth_set(
    project_id: str,
    payload: GroundTruthSetCreate,
    db: Session = Depends(get_db),
) -> models.GroundTruthSet:
    _get_project_or_404(db, project_id)

    if payload.data_asset_id is not None:
        _get_project_child_or_404(
            db,
            models.DataAsset,
            project_id,
            payload.data_asset_id,
            "data asset",
        )

    ground_truth_set = models.GroundTruthSet(project_id=project_id, **payload.model_dump())
    db.add(ground_truth_set)
    db.commit()
    db.refresh(ground_truth_set)
    return ground_truth_set


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
