from datetime import UTC, datetime

from app.models.domain import Dataset


class DatasetService:
    def list_datasets(self) -> list[Dataset]:
        return [
            Dataset(
                dataset_id="synthetic_demo",
                name="Synthetic demo dataset",
                description="Placeholder dataset for skeleton UI/API wiring.",
                domain="demo",
                document_count=0,
                created_at=datetime.now(UTC),
                metadata={"status": "placeholder"},
            )
        ]


def get_dataset_service() -> DatasetService:
    return DatasetService()
