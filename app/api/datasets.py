from fastapi import APIRouter, Depends

from app.models.api import DatasetListResponse
from app.services.datasets import DatasetService, get_dataset_service

router = APIRouter()


@router.get("/datasets", response_model=DatasetListResponse)
def list_datasets(
    service: DatasetService = Depends(get_dataset_service),
) -> DatasetListResponse:
    return DatasetListResponse(datasets=service.list_datasets())
