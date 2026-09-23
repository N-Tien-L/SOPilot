"""POST /api/v1/metadata/suggest — AI-powered metadata suggestion endpoint.

Called synchronously by Java knowledge-service during file upload.
Downloads the file from MinIO, extracts first 4000 chars, and calls Groq LLM
to suggest category, title, description, tags, language, and policy flag.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import structlog
from src.api.dependencies import get_api_key
from fastapi import Depends

from src.services.minio_service import minio_service
from src.services.preview_extractor import extract_preview
from src.services.metadata_suggestion_service import metadata_suggestion_service

logger = structlog.get_logger()

router = APIRouter()


# ── Request / Response Schemas ──────────────────────────────────────────────


class MetadataSuggestRequest(BaseModel):
    """Request payload from Java knowledge-service."""

    file_key: str = Field(..., description="MinIO object key for the uploaded file")
    bucket_name: str = Field(
        "poliwise-documents", description="MinIO bucket name"
    )
    available_categories: list[str] = Field(
        default_factory=list,
        description="Active category slugs from metadata.categories (is_active=true)",
    )
    top_tags: list[str] = Field(
        default_factory=list,
        description="Top 20 most-used tag names from metadata.tags",
    )


class MetadataSuggestResponse(BaseModel):
    """AI-suggested metadata returned to Java for user review."""

    category_slug: str | None = None
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    language: str = "en"
    is_policy: bool = False


class ErrorResponse(BaseModel):
    """Error response for failed suggestions."""

    error: str
    detail: str | None = None


# ── Endpoint ────────────────────────────────────────────────────────────────


@router.post(
    "/metadata/suggest",
    response_model=MetadataSuggestResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal processing error"},
    },
    summary="Suggest document metadata using AI",
    description=(
        "Downloads a file from MinIO, extracts the first 4000 characters, "
        "and uses Groq LLM to suggest metadata fields. Called synchronously "
        "by knowledge-service during file upload (< 5s expected)."
    ),
    dependencies=[Depends(get_api_key)],
)
async def suggest_metadata(request: MetadataSuggestRequest):
    """Generate AI metadata suggestions for an uploaded document."""
    logger.info(
        "metadata_suggest_request_received",
        file_key=request.file_key,
        bucket=request.bucket_name,
        num_categories=len(request.available_categories),
        num_tags=len(request.top_tags),
    )

    # Step 1: Download file from MinIO
    try:
        file_bytes = await minio_service.download_file(
            bucket_name=request.bucket_name,
            file_key=request.file_key,
        )
        logger.info(
            "file_downloaded",
            file_key=request.file_key,
            size_bytes=len(file_bytes),
        )
    except Exception as e:
        logger.error("minio_download_failed", file_key=request.file_key, error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Failed to download file from MinIO: {e}",
        )

    # Step 2: Extract first 4000 characters
    try:
        text_preview = extract_preview(file_bytes, request.file_key)
        if not text_preview.strip():
            logger.warning("empty_text_extracted", file_key=request.file_key)
            return MetadataSuggestResponse()
    except ValueError as e:
        logger.error("extraction_failed", file_key=request.file_key, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("extraction_failed", file_key=request.file_key, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text: {e}",
        )

    # Step 3: Call Groq LLM for metadata suggestion
    try:
        suggestion = await metadata_suggestion_service.suggest(
            text_preview=text_preview,
            available_categories=request.available_categories,
            top_tags=request.top_tags,
        )

        return MetadataSuggestResponse(
            category_slug=suggestion.category_slug,
            title=suggestion.title,
            description=suggestion.description,
            tags=suggestion.tags,
            language=suggestion.language,
            is_policy=suggestion.is_policy,
        )

    except Exception as e:
        logger.error(
            "ai_suggestion_failed",
            file_key=request.file_key,
            error=str(e),
            exc_info=True,
        )
        # Per extraction-plan: if AI fails, return 503 so client might retry or fallback
        # 503 is more appropriate for external LLM service unavailability
        raise HTTPException(
            status_code=503,
            detail=f"AI metadata suggestion failed: {e}",
        )
