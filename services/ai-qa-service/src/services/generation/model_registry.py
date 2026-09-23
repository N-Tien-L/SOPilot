from enum import Enum
from datetime import datetime, timedelta
import time
import structlog
from pydantic import BaseModel
import openai
from openai import AsyncOpenAI
from typing import Optional, List

from ...config.settings import settings
from ...models.generation import GenerationResult
from .prompt_builder import prompt_builder as default_pb

logger = structlog.get_logger(__name__)

class ModelStatus(str, Enum):
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"

class ModelProfile(BaseModel):
    id: str                      
    name: str                    
    provider: str                
    model_name: str              
    base_url: str
    api_key: str | None
    description: str | None = None
    context_window: int = 8192
    is_default: bool = False
    status: ModelStatus = ModelStatus.AVAILABLE
    rate_limited_until: datetime | None = None

DEFAULT_MODEL_PROFILES = [
    ModelProfile(
        id="local/qwen3-8b",
        name="Qwen3 8B (Local)",
        provider="local",
        model_name=settings.local_llm_model_name,
        base_url=settings.local_llm_base_url,
        api_key=None,
        description="Self-hosted, free, best data privacy",
        is_default=True,
    ),
    ModelProfile(
        id="groq/qwen3-32b",
        name="Qwen3 32B (Groq)",
        provider="groq",
        model_name="qwen/qwen3-32b",
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        description="More powerful, free on Groq (rate limited)",
    ),
    ModelProfile(
        id="groq/llama-70b",
        name="Llama 3.3 70B (Groq)",
        provider="groq",
        model_name="llama-3.3-70b-versatile",
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.groq_api_key,
        description="Large model, high quality (~1,000 RPD)",
    ),
    ModelProfile(
        id="gemini/flash-2",
        name="Gemini 2.0 Flash",
        provider="gemini",
        model_name="gemini-2.0-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key=settings.gemini_api_key,
        description="Google Gemini, fast and capable",
    ),
    ModelProfile(
        id="openrouter/mistral-7b",
        name="Mistral 7B (OpenRouter)",
        provider="openrouter",
        model_name="mistralai/mistral-7b-instruct",
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        description="Via OpenRouter, many model options",
    ),
]

class RateLimitError(Exception):
    pass

class ModelRegistry:
    RATE_LIMIT_COOLDOWN = timedelta(minutes=settings.model_rate_limit_cooldown_minutes)

    def __init__(self, profiles: list[ModelProfile]):
        self._profiles = {p.id: p for p in profiles}

    def get_all(self) -> list[ModelProfile]:
        self._refresh_rate_limit_status()
        return list(self._profiles.values())

    def get_available(self) -> list[ModelProfile]:
        self._refresh_rate_limit_status()
        return [p for p in self._profiles.values() if p.status == ModelStatus.AVAILABLE]

    def get(self, model_id: str) -> ModelProfile | None:
        self._refresh_rate_limit_status()
        return self._profiles.get(model_id)

    def _get_default(self) -> ModelProfile:
        return self.get(settings.default_model_id) or list(self._profiles.values())[0]

    def mark_rate_limited(self, model_id: str):
        if model_id in self._profiles:
            self._profiles[model_id].status = ModelStatus.RATE_LIMITED
            self._profiles[model_id].rate_limited_until = (
                datetime.utcnow() + self.RATE_LIMIT_COOLDOWN
            )
            logger.warning(f"Model {model_id} marked as RATE_LIMITED for {settings.model_rate_limit_cooldown_minutes} minutes.")

    def mark_unavailable(self, model_id: str):
        if model_id in self._profiles:
            self._profiles[model_id].status = ModelStatus.UNAVAILABLE
            logger.warning(f"Model {model_id} marked as UNAVAILABLE due to connection failure.")

    def _refresh_rate_limit_status(self):
        now = datetime.utcnow()
        for profile in self._profiles.values():
            if (
                profile.status == ModelStatus.RATE_LIMITED
                and profile.rate_limited_until
                and now >= profile.rate_limited_until
            ):
                profile.status = ModelStatus.AVAILABLE
                profile.rate_limited_until = None
                logger.info(f"Model {profile.id} rate limit cooldown expired -> AVAILABLE")

    async def generate(
        self,
        model_id: str,
        query: str,
        original_query: str,
        retrieved_chunks: list,
        layer3_history: list,
    ) -> GenerationResult:
        profile = self.get(model_id)
        if not profile:
            profile = self._get_default()
        if profile.status != ModelStatus.AVAILABLE:
            raise RateLimitError(f"Model {model_id} is {profile.status}")

        client = AsyncOpenAI(
            api_key=profile.api_key or "not-needed",
            base_url=profile.base_url,
        )

        messages = default_pb.build(
            query=query,
            context_chunks=retrieved_chunks,
            history=layer3_history,  # Layer 3 ONLY
        )

        start_time = time.time()
        try:
            response = await client.chat.completions.create(
                model=profile.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,            )
            latency_ms = int((time.time() - start_time) * 1000)
            usage = response.usage
            
            return GenerationResult(
                content=response.choices[0].message.content,
                model_used=model_id,
                model_name_actual=profile.model_name,
                tokens_prompt=usage.prompt_tokens if usage else 0,
                tokens_completion=usage.completion_tokens if usage else 0,
                tokens_total=usage.total_tokens if usage else 0,
                latency_ms=latency_ms
            )
        except openai.RateLimitError:
            self.mark_rate_limited(model_id)
            raise RateLimitError(f"Model {model_id} hit rate limit")

    async def generate_streaming(
        self,
        model_id: str,
        query: str,
        retrieved_chunks: list,
        layer3_history: list,
    ):
        profile = self.get(model_id)
        if not profile:
            profile = self._get_default()
        if profile.status != ModelStatus.AVAILABLE:
            raise RateLimitError(f"Model {model_id} is {profile.status}")

        client = AsyncOpenAI(
            api_key=profile.api_key or "not-needed",
            base_url=profile.base_url,
        )

        messages = default_pb.build(
            query=query,
            context_chunks=retrieved_chunks,
            history=layer3_history,  # Layer 3 ONLY
        )

        try:
            stream = await client.chat.completions.create(
                model=profile.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,                stream=True
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.RateLimitError:
            self.mark_rate_limited(model_id)
            raise RateLimitError(f"Model {model_id} hit rate limit")

model_registry = ModelRegistry(DEFAULT_MODEL_PROFILES)
