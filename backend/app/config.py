from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2025-03-01-preview"

    output_dir: str = "deployment/outputs"
    knowledge_dir: str = "deployment/knowledge"
    data_dir: str = "deployment/data"
    db_path: str = "deployment/data/ontology.db"

    datastore_backend: str = "sqlite"  # "sqlite" | "postgres"
    postgres_dsn: str = ""

    host: str = "0.0.0.0"
    port: int = 8005
    cors_origins: str = "http://localhost:3005"

    class Config:
        env_file = str(_ENV_FILE)
        extra = "ignore"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
