from typing import AsyncGenerator
import json

from .model_registry import model_registry
from .prompt_builder import prompt_builder
from ...models.retrieval import RetrievalChunk


async def generate_stream(
    query: str,
    context_chunks: list[RetrievalChunk],
    history: list[dict],
    model_id: str = "default"
) -> AsyncGenerator[str, None]:
    
    async for content in model_registry.generate_streaming(
        model_id=model_id,
        query=query,
        retrieved_chunks=context_chunks,
        layer3_history=history
    ):
        yield f"data: {json.dumps({'content': content})}\n\n"

    yield "data: [DONE]\n\n"