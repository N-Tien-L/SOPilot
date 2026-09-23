import json
from pydantic import BaseModel
from groq import AsyncGroq
import structlog
from typing import Any

logger = structlog.get_logger(__name__)

REFINEMENT_PROMPT = """You are an expert at improving search queries for a policy knowledge base.
The system is Poliwise, a policy management platform. Documents may be in English, Vietnamese, or mixed.

Given the original question and conversation history, do the following:
1. TRANSLATE: If the question is NOT in English, translate it to English. Be accurate - do not change the meaning.
2. De-contextualize: Rewrite the question so it is self-contained without conversation context. Use the conversation history to understand what the user is referring to (e.g. "tell me more" about a policy discussed earlier should become "details about [policy name]").
3. Expand: Add related policy keywords to improve search recall.

Conversation history:
{layer3_history}

Original question: {original_query}

Return JSON ONLY:
{{
  "refined_query": "the translated and improved question in English",
  "search_keywords": ["keyword1", "keyword2"],
  "filters_hint": {{"date_range": null, "category": null}}
}}"""

class RefinedQuery(BaseModel):
    original: str
    refined: str
    keywords: list[str] = []
    filters_hint: dict[str, Any] = {}
    latency_ms: int = 0

class QueryRefiner:
    def __init__(self, groq_api_key: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 256):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.model = model
        self.max_tokens = max_tokens

    def _format_layer3_history(self, layer3_history: list[Any]) -> str:
        if not layer3_history:
            return "None"
        formatted_messages = []
        for msg in layer3_history:
            role = getattr(msg, "role", "unknown")
            content = getattr(msg, "content", "")
            formatted_messages.append(f"{role.upper()}: {content}")
        return "\n".join(formatted_messages)

    async def refine(
        self,
        original_query: str,
        layer3_history: list[Any],
    ) -> RefinedQuery:
        import time
        start_time = time.time()
        
        history_text = self._format_layer3_history(layer3_history)
        prompt = REFINEMENT_PROMPT.format(
            layer3_history=history_text,
            original_query=original_query
        )

        logger.info("query_refiner_input",
            original_query=original_query,
            has_history=bool(layer3_history),
            history_length=len(layer3_history)
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            latency_ms = int((time.time() - start_time) * 1000)

            raw_response = response.choices[0].message.content
            logger.info("query_refiner_raw_response",
                raw_response=raw_response,
                latency_ms=latency_ms
            )

            data = json.loads(raw_response)
            refined = data.get("refined_query", original_query)
            keywords = data.get("search_keywords", [])

            logger.info("query_refiner_output",
                original=original_query,
                refined=refined,
                keywords=keywords,
                latency_ms=latency_ms
            )

            return RefinedQuery(
                original=original_query,
                refined=refined,
                keywords=keywords,
                filters_hint=data.get("filters_hint", {}),
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("query_refiner_failed",
                error=str(e),
                original_query=original_query,
                latency_ms=latency_ms
            )
            return RefinedQuery(
                original=original_query,
                refined=original_query,
                latency_ms=latency_ms
            )
