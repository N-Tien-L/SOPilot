"""Model-free fakes shared by unit and integration tests."""
from __future__ import annotations

import hashlib
from collections.abc import Sequence

import numpy as np


class Words:
    """Whitespace tokenizer: deterministic and independent of any model download."""

    def count(self, text: str) -> int:
        return len(text.split())


class FakeEmbedder:
    """Deterministic 1024-d unit vectors from the text hash; counts embedded texts."""

    name = "local"
    model = "fake/bge-m3"
    revision = "test-rev"
    dim = 1024

    def __init__(self) -> None:
        self.embedded: list[str] = []
        self.fail = False

    def tokenizer(self) -> Words:
        return Words()

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        if self.fail:
            from sopilot_ai.providers.embedding import EmbeddingError

            raise EmbeddingError("down")
        self.embedded += list(texts)
        rows = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(t.encode("utf-8")).digest()[:8], "little")
            v = np.random.default_rng(seed).standard_normal(self.dim).astype(np.float32)
            rows.append(v / np.linalg.norm(v))
        return np.stack(rows) if rows else np.zeros((0, self.dim), dtype=np.float32)


class BowEmbedder(FakeEmbedder):
    """Bag-of-words hashing embedder: cosine grows with shared (diacritic-folded) words, so
    retrieval tests can reason about which chunk is closest without a real model."""

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        from sopilot_ai.retrieval.lexical import fold

        if self.fail:
            from sopilot_ai.providers.embedding import EmbeddingError

            raise EmbeddingError("down")
        self.embedded += list(texts)
        rows = []
        for t in texts:
            v = np.zeros(self.dim, dtype=np.float32)
            for word in fold(t.lower()).split():
                word = "".join(ch for ch in word if ch.isalnum())
                if not word:
                    continue
                h = hashlib.sha256(word.encode("utf-8")).digest()
                v[int.from_bytes(h[:4], "little") % self.dim] += 1.0
            if not v.any():
                v[0] = 1.0
            rows.append(v / np.linalg.norm(v))
        return np.stack(rows) if rows else np.zeros((0, self.dim), dtype=np.float32)


class ScriptedChain:
    """Stands in for ``providers.llm.LLMChain``: records every call, never touches the network.

    ``answer`` is a list of text pieces, or a function of the messages (a test that must echo
    the canary of the prompt it was given). ``fail`` makes every call raise ``LLMError``.
    """

    def __init__(self, answer=("Câu trả lời.",), *, model: str = "fake-llm",  # noqa: ANN001
                 rewrite: str = "", budget: int | None = None, fail: bool = False) -> None:
        self._answer = answer
        self.model = model
        self.rewrite_output = rewrite
        self._budget = budget
        self.fail = fail
        self.calls: list[dict] = []

    @property
    def context_budget(self) -> int | None:
        return self._budget

    def stream(self, messages, *, tokens: int, on_start=None):  # noqa: ANN001, ANN201
        from sopilot_ai.providers.llm import LLMError

        self.calls.append({"kind": "stream", "messages": [dict(m) for m in messages],
                           "tokens": tokens})
        if self.fail:
            raise LLMError("LLM_UNAVAILABLE")
        pieces = self._answer(messages) if callable(self._answer) else self._answer
        started = False
        for piece in pieces:
            if not started and on_start is not None:
                on_start(self.model)
            started = True
            yield piece

    def complete(self, messages, *, tokens: int, temperature=None, on_start=None) -> str:  # noqa: ANN001
        from sopilot_ai.providers.llm import LLMError

        self.calls.append({"kind": "complete", "messages": [dict(m) for m in messages],
                           "tokens": tokens, "temperature": temperature})
        if self.fail:
            raise LLMError("LLM_UNAVAILABLE")
        if on_start is not None:
            on_start(self.model)
        return self.rewrite_output
