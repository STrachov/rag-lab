from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Lab"
    api_prefix: str = "/v1"
    data_dir: Path = Field(default=Path("data"))
    docling_async_max_wait_seconds: float = 1800.0
    docling_base_url: str = "http://localhost:5001"
    docling_poll_interval_seconds: float = 3.0
    docling_timeout_seconds: float = 120.0
    qdrant_url: str = "http://localhost:6333"
    voyage_api_key: str = ""
    voyage_base_url: str = "https://api.voyageai.com"
    voyage_max_retries: int = 5
    voyage_rpm_limit: int = 3
    voyage_tpm_limit: int = 10000
    voyage_tpm_utilization: float = 0.65
    database_url: str = Field(
        default="postgresql+psycopg://raglab:raglab@localhost:5433/raglab",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_LAB_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
