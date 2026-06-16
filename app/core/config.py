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
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com"
    openai_llm_rerank_model: str = "gpt-5.4-mini"
    openai_llm_rerank_model_options: str = "gpt-5.4-mini,gpt-5.4-nano"
    openai_llm_rerank_input_cost_per_1m_tokens: float = 0.2
    openai_llm_rerank_output_cost_per_1m_tokens: float = 1.25
    openai_max_retries: int = 2
    qdrant_url: str = "http://localhost:6333"
    voyage_api_key: str = ""
    voyage_base_url: str = "https://api.voyageai.com"
    voyage_max_retries: int = 5
    voyage_rpm_limit: int = 2000
    voyage_rerank_2_5_lite_tpm_limit: int = 4000000
    voyage_rerank_2_5_lite_cost_per_1m_tokens: float = 0.02
    voyage_rerank_2_5_tpm_limit: int = 2000000
    voyage_rerank_2_5_cost_per_1m_tokens: float = 0.05
    voyage_rerank_max_retries: int = 5
    voyage_rerank_rpm_limit: int = 2000
    voyage_rerank_tpm_utilization: float = 0.95
    voyage_tpm_limit: int = 16000000
    voyage_tpm_utilization: float = 0.95
    database_url: str = Field(
        default="postgresql+psycopg://raglab:raglab@localhost:5433/raglab",
        validation_alias="DATABASE_URL",
    )

    model_config = SettingsConfigDict(env_file=".env", env_prefix="RAG_LAB_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
