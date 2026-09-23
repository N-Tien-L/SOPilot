from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-qa-service"}


@router.get("/actuator/health")
async def actuator_health():
    return {"status": "UP", "service": "ai-qa-service"}