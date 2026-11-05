"""Environment settings (TECH-V2-ai-service §10). Secrets come only from the environment."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # local: an unpinned embedding revision is allowed (logged, stored as "unpinned");
    # eval: it is a startup error (TECH-V2-ai-service §5.5).
    profile: Literal["local", "eval"] = Field("local", alias="SOPILOT_PROFILE")

    db_url: SecretStr = Field(..., alias="SOPILOT_DB_URL")
    internal_token: SecretStr = Field(..., alias="SOPILOT_INTERNAL_TOKEN")
    core_base_url: str = Field("http://core-api:8080", alias="SOPILOT_CORE_BASE_URL")
    core_jwks_url: str = Field("http://core-api:8080/.well-known/jwks.json",
                               alias="SOPILOT_CORE_JWKS_URL")

    s3_endpoint: str = Field("minio:9000", alias="SOPILOT_S3_ENDPOINT")
    s3_secure: bool = Field(False, alias="SOPILOT_S3_SECURE")
    s3_bucket: str = Field("sopilot-v2-documents", alias="SOPILOT_S3_BUCKET")
    s3_access_key: SecretStr = Field(SecretStr(""), alias="SOPILOT_S3_AI_ACCESS_KEY")
    s3_secret_key: SecretStr = Field(SecretStr(""), alias="SOPILOT_S3_AI_SECRET_KEY")

    models_config: Path = Field(SERVICE_ROOT / "config" / "models.yaml",
                                alias="SOPILOT_MODELS_CONFIG")

    ingest_max_attempts: int = Field(3, ge=1, alias="SOPILOT_INGEST_MAX_ATTEMPTS")
    ingest_lease_seconds: int = Field(600, ge=30, alias="SOPILOT_INGEST_LEASE_SECONDS")
    ingest_backoff_base_seconds: float = Field(30.0, ge=0, alias="SOPILOT_INGEST_BACKOFF_SECONDS")
    worker_poll_seconds: float = Field(5.0, gt=0, alias="SOPILOT_WORKER_POLL_SECONDS")

    outbox_max_attempts: int = Field(20, ge=1, alias="SOPILOT_OUTBOX_MAX_ATTEMPTS")
    outbox_http_timeout_seconds: float = Field(10.0, gt=0, alias="SOPILOT_OUTBOX_HTTP_TIMEOUT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
