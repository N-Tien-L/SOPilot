"""AI-powered metadata suggestion using Groq LLM.

Calls Groq API with instructor for structured JSON output.
The prompt constrains the LLM to pick from available categories and
prioritize reusing existing tags.
"""

import structlog
from groq import AsyncGroq
import instructor

from src.config.settings import settings
from src.models.metadata_suggestion import MetadataSuggestion

logger = structlog.get_logger()

# System prompt template — kept under ~500 tokens per extraction-plan spec
SYSTEM_PROMPT = """\
You are a document classifier for a policy knowledge platform. \
Given the first section of a document, return ONLY a JSON object with metadata.

Constraints:
1. "category_slug" MUST be chosen from this exact list: [{available_categories}]. \
If none fit, set to null.
2. For "tags", generate 3-5 keywords. Prioritize reusing these existing tags \
if relevant: [{top_tags}]. Only invent new tags if absolutely necessary.
3. "title": Extract from the first heading or summarize in under 100 characters. \
Set to null if unclear.
4. "description": A single sentence summarizing the document. Set to null if unclear.
5. "language": "en" for English, "vi" for Vietnamese.
6. "is_policy": true if this appears to be an official policy, regulation, \
or compliance document.\
"""

USER_PROMPT_TEMPLATE = """\
Document content:
---
{text_preview}
---\
"""


class MetadataSuggestionService:
    """Service for generating metadata suggestions via Groq LLM."""

    def __init__(self):
        self._client: instructor.AsyncInstructor | None = None

    def _get_client(self) -> instructor.AsyncInstructor:
        """Lazy-initialize the instructor-patched Groq client."""
        if self._client is None:
            groq_client = AsyncGroq(api_key=settings.groq_api_key)
            self._client = instructor.from_groq(groq_client, mode=instructor.Mode.JSON)
        return self._client

    async def suggest(
        self,
        text_preview: str,
        available_categories: list[str],
        top_tags: list[str],
    ) -> MetadataSuggestion:
        """Generate metadata suggestion from document text preview.

        Args:
            text_preview: First ~4000 characters of the document.
            available_categories: Active category slugs from Java DB context.
            top_tags: Top 20 most-used tag names from Java DB context.

        Returns:
            MetadataSuggestion with AI-suggested fields.

        Raises:
            Exception: If Groq API call fails after retries.
        """
        client = self._get_client()

        # Build the system prompt with injected context
        system_prompt = SYSTEM_PROMPT.format(
            available_categories=", ".join(available_categories) if available_categories else "none provided",
            top_tags=", ".join(top_tags) if top_tags else "none provided",
        )

        user_prompt = USER_PROMPT_TEMPLATE.format(text_preview=text_preview)

        logger.info(
            "metadata_suggestion_started",
            model=settings.groq_model,
            text_length=len(text_preview),
            num_categories=len(available_categories),
            num_tags=len(top_tags),
        )

        try:
            suggestion = await client.chat.completions.create(
                model=settings.groq_model,
                response_model=MetadataSuggestion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_retries=2,
                timeout=10.0,
            )

            # Validate category_slug is in the allowed list
            if suggestion.category_slug and suggestion.category_slug not in available_categories:
                logger.warning(
                    "metadata_suggestion_invalid_category",
                    suggested=suggestion.category_slug,
                    available=available_categories,
                )
                suggestion.category_slug = None

            logger.info(
                "metadata_suggestion_completed",
                category=suggestion.category_slug,
                title=suggestion.title,
                num_tags=len(suggestion.tags),
                language=suggestion.language,
                is_policy=suggestion.is_policy,
            )

            return suggestion

        except Exception as e:
            logger.error("metadata_suggestion_failed", error=str(e), exc_info=True)
            raise


# Global service instance
metadata_suggestion_service = MetadataSuggestionService()
