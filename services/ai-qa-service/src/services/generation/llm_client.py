"""LLM client - unified interface for chat routes to interact with model registry."""

import time
import structlog
from typing import List, Optional, AsyncGenerator

from ...config.settings import settings
from .model_registry import model_registry, ModelProfile, RateLimitError

logger = structlog.get_logger()


class LLMClient:
    """High-level LLM client used by chat routes."""

    def __init__(self):
        self.registry = model_registry

    async def _resolve_model(self, model_id: str) -> ModelProfile:
        """Resolve a model profile, with preemptive fallback if unavailable."""
        if model_id == "default":
            model_id = settings.default_model_id

        profile = self.registry.get(model_id)
        if not profile:
            profile = self.registry.get(settings.default_model_id)

        # Fallback if profile is not available
        if profile.status.value != "available":
            logger.warning("llm_model_not_available_finding_fallback", model_id=profile.id, status=profile.status.value)
            fallback_profile = None
            for fid in ["groq/llama-70b", "groq/qwen3-32b"]:
                f_prof = self.registry.get(fid)
                if f_prof and f_prof.status.value == "available" and f_prof.api_key:
                    fallback_profile = f_prof
                    break
            if not fallback_profile:
                for f_prof in self.registry.get_all():
                    if not f_prof.id.startswith("local/") and f_prof.status.value == "available" and f_prof.api_key:
                        fallback_profile = f_prof
                        break
            if fallback_profile:
                logger.info("llm_selected_fallback_preemptively", original_model=profile.id, fallback_model=fallback_profile.id)
                profile = fallback_profile
            else:
                raise RateLimitError(f"Requested model {profile.id} is {profile.status.value} and no remote fallbacks are available.")
        
        return profile

    async def generate(
        self,
        messages: List[dict],
        model_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> tuple[str, int, int, int, int]:
        """Generate a completion.

        Returns:
            (content, prompt_tokens, completion_tokens, total_tokens, latency_ms)
        """
        profile = await self._resolve_model(model_id)

        from openai import AsyncOpenAI
        import openai

        active_profile = profile
        attempts = 0
        max_attempts = 2

        import httpx
        
        while attempts < max_attempts:
            client = AsyncOpenAI(
                api_key=active_profile.api_key or "not-needed",
                base_url=active_profile.base_url,
            )

            start_time = time.time()
            try:
                connect_timeout = 1.0 if active_profile.id.startswith("local/") else 5.0
                response = await client.chat.completions.create(
                    model=active_profile.model_name,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2048,
                    timeout=httpx.Timeout(30.0, connect=connect_timeout),
                )
                latency_ms = int((time.time() - start_time) * 1000)
                usage = response.usage

                if metadata is not None:
                    metadata["model_used"] = active_profile.id

                # If this was a fallback retry, log success
                if attempts > 0:
                    logger.info("llm_fallback_success", original_model=model_id, fallback_model=active_profile.id)

                return (
                    response.choices[0].message.content,
                    usage.prompt_tokens if usage else 0,
                    usage.completion_tokens if usage else 0,
                    usage.total_tokens if usage else 0,
                    latency_ms,
                )
            except (openai.APIConnectionError, Exception) as e:
                # Check if we can fall back (only on first attempt, and if active model is a local one)
                if attempts == 0 and active_profile.id.startswith("local/"):
                    logger.warning(
                        "llm_connection_failed_falling_back",
                        error=str(e),
                        model=active_profile.model_name,
                        model_id=active_profile.id
                    )
                    # Mark local model as offline/unavailable
                    self.registry.mark_unavailable(active_profile.id)

                    # Find a remote fallback
                    fallback_profile = None
                    for fid in ["groq/llama-70b", "groq/qwen3-32b"]:
                        f_prof = self.registry.get(fid)
                        if f_prof and f_prof.api_key:
                            fallback_profile = f_prof
                            break
                    if not fallback_profile:
                        for f_prof in self.registry.get_all():
                            if not f_prof.id.startswith("local/") and f_prof.api_key:
                                fallback_profile = f_prof
                                break
                    
                    if fallback_profile:
                        logger.info("llm_selected_fallback", fallback_model_id=fallback_profile.id)
                        active_profile = fallback_profile
                        attempts += 1
                        continue
                
                logger.error("llm_generation_failed", error=str(e), model=active_profile.model_name)
                raise

    async def generate_streaming(
        self,
        messages: List[dict],
        model_id: str = "default",
        temperature: float = 0.3,
        max_tokens: int = 1024,
        metadata: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion."""
        profile = await self._resolve_model(model_id)

        from openai import AsyncOpenAI
        import openai

        active_profile = profile
        attempts = 0
        max_attempts = 2

        import httpx

        while attempts < max_attempts:
            client = AsyncOpenAI(
                api_key=active_profile.api_key or "not-needed",
                base_url=active_profile.base_url,
            )

            try:
                connect_timeout = 1.0 if active_profile.id.startswith("local/") else 5.0
                stream = await client.chat.completions.create(
                    model=active_profile.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048,
                    stream=True,
                    timeout=httpx.Timeout(30.0, connect=connect_timeout),
                )

                if metadata is not None:
                    metadata["model_used"] = active_profile.id

                # Stream content
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                
                # Stream successfully consumed, return
                return

            except (openai.APIConnectionError, Exception) as e:
                # Check if we can fall back (only on first attempt, and if active model is a local one)
                if attempts == 0 and active_profile.id.startswith("local/"):
                    logger.warning(
                        "llm_streaming_connection_failed_falling_back",
                        error=str(e),
                        model=active_profile.model_name,
                        model_id=active_profile.id
                    )
                    # Mark local model as offline/unavailable
                    self.registry.mark_unavailable(active_profile.id)

                    # Find a remote fallback
                    fallback_profile = None
                    for fid in ["groq/llama-70b", "groq/qwen3-32b"]:
                        f_prof = self.registry.get(fid)
                        if f_prof and f_prof.api_key:
                            fallback_profile = f_prof
                            break
                    if not fallback_profile:
                        for f_prof in self.registry.get_all():
                            if not f_prof.id.startswith("local/") and f_prof.api_key:
                                fallback_profile = f_prof
                                break
                    
                    if fallback_profile:
                        logger.info("llm_streaming_selected_fallback", fallback_model_id=fallback_profile.id)
                        active_profile = fallback_profile
                        attempts += 1
                        continue
                
                logger.error("llm_streaming_failed", error=str(e), model=active_profile.model_name)
                raise


llm_client = LLMClient()
