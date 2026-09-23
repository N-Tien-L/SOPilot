from typing import List, Dict
from ...models.retrieval import RetrievalChunk

SYSTEM_PROMPT = """You are a helpful AI assistant for Poliwise, a policy management platform.
Answer the user's question based ONLY on the provided context from the knowledge base.

## Instructions
- Answer based only on the provided context
- Respond in the same language as the user's query (e.g., respond in Vietnamese if the query is in Vietnamese or uses Vietnamese slang/typos/phrases like 'la gi', 'lla gi')
- If the context doesn't contain enough information to answer the question, say "I don't have enough information to answer this question based on the available documents."
- Cite sources by mentioning document titles when relevant
- Provide detailed, comprehensive, and well-structured answers using bullet points or steps when necessary
- If unsure, acknowledge uncertainty rather than hallucinating
- Do NOT output any thinking, reasoning, or `` tags. Return only the final answer."""


class PromptBuilder:
    def __init__(self):
        self.system_prompt = SYSTEM_PROMPT

    def build(
        self,
        query: str,
        context_chunks: List[RetrievalChunk],
        history: List[Dict[str, str]] = None,
        system_prompt: str = None
    ) -> List[Dict[str, str]]:
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": self.system_prompt})

        if history:
            for msg in history[-10:]:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        formatted_chunks = self._format_chunks(context_chunks)
        context_message = f"## Context (Retrieved Documents)\n{formatted_chunks}\n\n## Question\n{query}"
        messages.append({"role": "user", "content": context_message})

        return messages

    def _format_chunks(self, chunks: List[RetrievalChunk]) -> str:
        if not chunks:
            return "No relevant documents found."

        formatted = []
        for i, chunk in enumerate(chunks[:10], 1):
            doc_name = chunk.document_name or "Unknown Document"
            content = chunk.content[:2500] + "..." if len(chunk.content) > 2500 else chunk.content
            formatted.append(f"### Document {i}: {doc_name}\n{content}\n")

        return "\n\n".join(formatted)


prompt_builder = PromptBuilder()