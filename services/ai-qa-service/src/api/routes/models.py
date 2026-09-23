from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..dependencies import get_user_context, UserContext

router = APIRouter(prefix="/models", tags=["Models"])


from datetime import datetime

class AIModelResponse(BaseModel):
    id: str
    name: str
    provider: str
    description: str | None
    context_window: int
    is_default: bool
    status: str      # available | rate_limited | unavailable
    rate_limited_until: datetime | None = None

class ModelListResponse(BaseModel):
    models: list[AIModelResponse]

@router.get("", response_model=ModelListResponse)
async def list_models(user: UserContext = Depends(get_user_context)):
    from ...services.generation.model_registry import model_registry

    profiles = model_registry.get_all()

    models = []
    for profile in profiles:
        models.append(AIModelResponse(
            id=profile.id,
            name=profile.name,
            provider=profile.provider,
            description=profile.description,
            context_window=profile.context_window,
            is_default=profile.is_default,
            status=profile.status,
            rate_limited_until=profile.rate_limited_until
        ))

    if not any(m.is_default for m in models):
        models[0].is_default = True

    return ModelListResponse(models=models)