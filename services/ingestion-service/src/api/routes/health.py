from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        service="ingestion-service",
        version="0.1.0",
    )
