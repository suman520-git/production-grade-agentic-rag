from pathlib import Path


from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app_name: str
    app_env: str = "development"

    # Database settings loaded from .env.
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str

    openai_api_key: SecretStr
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "rag_document_chunks"

    openai_model: str = "gpt-4o-mini"

    app_api_key: SecretStr = Field(min_length=32)

    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ]
    )


settings = Settings()