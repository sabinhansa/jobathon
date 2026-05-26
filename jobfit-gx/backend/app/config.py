from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://jobfit:jobfit@db:5432/jobfit"
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    ollama_base_url: str = "http://ollama:11434"
    local_llm_model: str = "qwen3:8b"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cors_allow_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "chrome-extension://*",
    ]
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

