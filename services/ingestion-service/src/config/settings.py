from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8088
    log_level: str = "info"
    internal_api_key: str = Field(..., description="Internal API Key for service-to-service authentication")

    # Database
    database_url: str = Field(..., description="PostgreSQL connection URL with asyncpg")
    database_schema: str = "knowledge"

    # RabbitMQ
    rabbitmq_url: str = Field(..., description="RabbitMQ connection URL")
    rabbitmq_exchange: str = "sopilot.events"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # Inference / Cloud Embedding Services (OpenAI, Jina AI, HuggingFace, etc.)
    embedding_url: str = "https://api.jina.ai"
    embedding_api_key: Optional[str] = None
    embedding_model: str = "jina-embeddings-v3"
    reranker_url: Optional[str] = None

    # LLM (Groq for Metadata Suggestion)
    groq_api_key: str = Field(..., description="Groq API key for metadata suggestion")
    groq_model: str = "llama-3.3-70b-versatile"

    # Chunking
    chunking_parent_size: int = 1500
    chunking_child_size: int = 400
    chunking_child_overlap: int = 80
    chunking_default_strategy: str = "parent_child"

    # OCR Fallback
    ocr_fallback_min_text_length: int = 50
    ocr_fallback_min_image_count: int = 1
    ocr_language: str = "eng"

    # Redundancy Detection
    similarity_threshold: float = 0.90
    similarity_threshold_digital: float = 0.98
    similarity_threshold_ocr: float = 0.90

    model_config = {
        "env_file": ".env", 
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True
    }


settings = Settings()
