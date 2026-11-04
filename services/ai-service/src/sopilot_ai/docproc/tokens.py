"""Token counting for the chunker (TECH-V2-ai-service §1.1).

The chunker takes a ``Tokenizer`` instead of calling the embedding provider, so it does not depend
on the provider layer and ``eval/`` counts tokens with the same object.
"""
from __future__ import annotations

from typing import Any, Protocol


class Tokenizer(Protocol):
    def count(self, text: str) -> int: ...


class HFTokenizer:
    """Hugging Face tokenizer of the active embedding model; the model weights are not loaded.

    ``model`` and ``revision`` come from the active embedding entry of ``models.yaml``.
    """

    def __init__(self, model: str, revision: str | None = None,
                 local_files_only: bool = False) -> None:
        from transformers import AutoTokenizer

        self.model = model
        self.revision = revision
        kwargs = {"local_files_only": True} if local_files_only else {}
        self._tokenizer: Any = AutoTokenizer.from_pretrained(
            model, revision=revision or None, **kwargs)

    def count(self, text: str) -> int:
        return len(self._tokenizer.encode(text, add_special_tokens=False))
