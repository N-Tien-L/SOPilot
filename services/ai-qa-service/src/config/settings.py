from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    host: str = "0.0.0.0"
    port: int = 8086
    log_level: str = "info"
    internal_api_key: str = Field(..., description="Internal API Key for service-to-service authentication")
    jwt_secret: str = Field(..., min_length=32, description="Shared access-token signing secret")
    jwt_issuer: str = "sopilot-auth-service"

    database_url: str = Field(..., description="PostgreSQL connection URL with asyncpg")
    database_schema: str = "conversation"

    rabbitmq_url: str = Field(..., description="RabbitMQ connection URL")
    rabbitmq_exchange: str = "sopilot.events"
    redis_url: str = "redis://localhost:6379/0"

    embedding_url: str = "https://api.jina.ai"
    embedding_api_key: Optional[str] = None
    embedding_model: str = "jina-embeddings-v3"
    reranker_url: Optional[str] = None

    # Layer 1 - Groq
    groq_api_key: str = Field(..., description="Groq API Key for pipeline layers")
    layer1_model: str = "meta-llama/llama-prompt-guard-2-86m"
    layer1_fail_open: bool = False
    # Layer 1 - Toxic/Abusive Detection
    toxic_model: str = "llama-3.1-8b-instant"
    toxic_threshold: float = 0.5
    layer2_model: str = "llama-3.1-8b-instant"
    layer2_max_tokens_classify: int = 10
    layer2_max_tokens_respond: int = 256
    layer2_model_respond: str = "llama-3.1-8b-instant"
    query_refiner_model: str = "llama-3.1-8b-instant"
    query_refiner_max_tokens: int = 256

    # Layer 3 - Remote APIs
    openrouter_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    default_model_id: str = "local/qwen3-8b"
    model_rate_limit_cooldown_minutes: int = 5
    
    # Layer 3 - Local LLM
    local_llm_base_url: str = "http://host.docker.internal:8080/v1"
    local_llm_model_name: str = "qwen3-8b"
    
    # Title Generation
    title_generation_enabled: bool = True
    title_default_patterns: str = "New Conversation,"

    # Context Isolation
    context_layer3_only: bool = True
    max_layer3_context_pairs: int = 5

    retrieval_limit: int = 25
    rerank_limit: int = 10
    similarity_threshold: float = 0.15
    use_reranker: bool = True
    layer2_fallback_intent: str = "COMPLEX"

    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60

    max_history_messages: int = 20
    query_refiner_history_limit: int = 10
    conversation_title_max_length: int = 255


settings = Settings()
