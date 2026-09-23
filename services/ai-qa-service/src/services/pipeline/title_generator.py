from typing import Optional
from uuid import UUID
import structlog
from groq import AsyncGroq
from ...config.settings import settings

logger = structlog.get_logger(__name__)

TITLE_GENERATION_PROMPT = """Based on the following Q&A pair, generate a short title for this conversation.

Requirements:
- Length: 4–10 words
- Style: natural, accurately describes the content (similar to how ChatGPT or Gemini name conversations)
- Language: match the language used by the user
- No quotes, no prefixes like "Title:" or "Conversation:"

Question: {user_query}
Answer (summary): {assistant_summary}

Title:"""

class TitleGenerator:
    def __init__(self, groq_api_key: str, model: str = "llama-3.1-8b-instant"):
        self.client = AsyncGroq(api_key=groq_api_key)
        self.model = model

    async def generate(self, user_query: str, assistant_response: str) -> Optional[str]:
        try:
            summary = assistant_response[:300] if len(assistant_response) > 300 else assistant_response
            prompt = TITLE_GENERATION_PROMPT.format(
                user_query=user_query,
                assistant_summary=summary,
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                temperature=0.5,
            )
            title = response.choices[0].message.content.strip()
            title = title.strip('"\'')
            return title[:255]
        except Exception as e:
            logger.error("title_generation_failed", error=str(e))
            return None
