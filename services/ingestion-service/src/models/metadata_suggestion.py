from pydantic import BaseModel, Field


class MetadataSuggestion(BaseModel):
    """Structured LLM output for document metadata suggestion.

    Used by instructor to enforce JSON schema on Groq LLM responses.
    Fields map to metadata.document_metadata columns.
    """

    category_slug: str | None = Field(
        None,
        description="Category slug chosen from the available_categories list. Must be an exact match.",
    )
    title: str | None = Field(
        None,
        description="Document title extracted from first heading or summarized from content.",
    )
    description: str | None = Field(
        None,
        description="One-sentence summary of the document content.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="3-5 keyword tags. Prioritize reusing existing tags when relevant.",
    )
    language: str = Field(
        "en",
        description="Detected language: 'en' for English, 'vi' for Vietnamese.",
    )
    is_policy: bool = Field(
        False,
        description="Whether the document appears to be a policy or regulatory document.",
    )
