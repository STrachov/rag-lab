from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.session import get_db
from app.models.api import (
    DataAssetCreate,
    DataAssetListResponse,
    DataAssetResponse,
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
    return DataAssetListResponse(data_assets=assets)


@router.post(
    "/projects/{project_id}/data-assets",
    response_model=DataAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_data_asset(
    project_id: str,
    payload: DataAssetCreate,
    db: Session = Depends(get_db),
) -> models.DataAsset:
    _get_project_or_404(db, project_id)
    asset = models.DataAsset(project_id=project_id, **payload.model_dump())
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


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

    saved_experiment = models.SavedExperiment(project_id=project_id, **payload.model_dump())
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
