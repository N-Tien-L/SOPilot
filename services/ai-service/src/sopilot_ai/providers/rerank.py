"""Rerank providers (TECH-V2-ai-service §4.3, §6.4 step 3).

``score`` is synchronous and CPU bound; async callers run it in a thread. Scores are sigmoid
probabilities in ``[0, 1]`` so the ``hybrid_rerank`` threshold has one scale across questions.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import numpy as np
import structlog

from sopilot_ai.providers.registry import ModelsConfig, RerankSpec

log = structlog.get_logger(__name__)


class RerankError(Exception):
    """Reranker failure; retrieval surfaces it instead of silently skipping the rerank."""


class RerankProvider(Protocol):
    name: str
    model: str
    revision: str

    def score(self, query: str, passages: Sequence[str]) -> np.ndarray: ...


def _sigmoid(raw: Any) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(raw, dtype=np.float32)))


class LocalRerankProvider:
    """Cross-encoder (``bge-reranker-v2-m3``) via sentence-transformers on CPU (extra ``local``).

    Raw logits are taken and the sigmoid applied here, independent of library defaults, exactly
    like the eval harness ``CrossEncoder``.
    """

    name = "local"

    def __init__(self, spec: RerankSpec, revision: str) -> None:
        self.spec = spec
        self.model = spec.model
        self.revision = revision
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import CrossEncoder

            pinned = None if self.revision == "unpinned" else self.revision
            self._model = CrossEncoder(self.model, revision=pinned, max_length=512, device="cpu")
        return self._model

    def score(self, query: str, passages: Sequence[str]) -> np.ndarray:
        if not passages:
            return np.zeros(0, dtype=np.float32)
        try:
            raw = self._load().predict([(query, p) for p in passages], activation_fn=_identity)
        except Exception as exc:  # noqa: BLE001 - any model failure is a rerank failure
            raise RerankError(type(exc).__name__) from exc
        return _sigmoid(raw)


def _identity(x: Any) -> Any:
    return x


def build_rerank_provider(config: ModelsConfig, profile: str) -> RerankProvider | None:
    """``None`` when rerank is disabled or the provider is ``none`` (mode stays without suffix)."""
    spec = config.rerank()
    if not spec.enabled or spec.provider == "none":
        return None
    if spec.provider != "local":
        raise ValueError(f"unknown rerank provider {spec.provider!r}")
    if spec.revision:
        revision = spec.revision
    elif profile == "eval":
        raise RuntimeError("rerank revision must be pinned in profile eval")
    else:
        log.warning("rerank_revision_unpinned", model=spec.model)
        revision = "unpinned"
    return LocalRerankProvider(spec, revision)
