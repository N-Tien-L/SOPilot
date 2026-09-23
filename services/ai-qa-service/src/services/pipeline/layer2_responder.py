from pydantic import BaseModel
from groq import AsyncGroq
import structlog

logger = structlog.get_logger(__name__)

class Layer2Response(BaseModel):
    content: str
    model_used: str
    latency_ms: int = 0

class Layer2Responder:
    """
    Reuses llama-3.1-8b-instant (already used in Layer 2) to answer SIMPLE queries.
    No additional API call needed — saves latency and RPD quota.
    No RAG — answers from general knowledge only.
    """

    SIMPLE_RESPONSE_SYSTEM = """You are Poliwise, an AI policy assistant.
The knowledge base you serve contains organizational policies and internal documents.
Respond concisely, in a friendly and natural tone.
Respond in the same language as the user's query (e.g., respond in Vietnamese if the query is in Vietnamese or uses Vietnamese slang/typos/phrases like 'la gi', 'lla gi').
If the user asks "what is Poliwise" or "what data do you have", explain that you are an AI assistant helping them navigate and query organizational policies, regulations, and internal documents.
If the question relates to specific policies, regulations, or deep internal documents — say you need to look it up and ask the user to rephrase (this handles cases where intent was misclassified).
Never hallucinate specific policy information."""

    def __init__(self, groq_api_key: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 256):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def respond(self, query: str) -> Layer2Response:
        import time
        start_time = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SIMPLE_RESPONSE_SYSTEM},
                    {"role": "user", "content": query},
                ],
                max_tokens=self.max_tokens,
                temperature=0.7,
            )
            latency_ms = int((time.time() - start_time) * 1000)
            return Layer2Response(
                content=response.choices[0].message.content,
                model_used=f"groq/{self.model}",
                latency_ms=latency_ms
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Layer 2 simple response failed: {e}")
            return Layer2Response(
                content="I'm sorry, I cannot fulfill that request right now.",
                model_used=f"groq/{self.model}",
                latency_ms=latency_ms
            )
