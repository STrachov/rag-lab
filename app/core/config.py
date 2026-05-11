from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "RAG Lab"
    api_prefix: str = "/v1"
    data_dir: Path = Field(default=Path("data"))
    qdrant_url: str = "http://localhost:6333"
    database_url: str = Field(
        default="postgresql+psycopg://raglab:raglab@localhost:5433/raglab",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_LAB_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
