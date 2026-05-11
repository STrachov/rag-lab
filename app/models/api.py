from pydantic import BaseModel

from app.models.domain import Dataset


class HealthResponse(BaseModel):
    status: str


class DatasetListResponse(BaseModel):
    datasets: list[Dataset]
