"""Embedding providers (TECH-V2-ai-service §4.3, §5.5).

``embed`` is synchronous and CPU or network bound; async callers run it in a thread. Every
provider returns L2-normalised float32 vectors and reports the provider, model, revision and dim
that are written on each chunk.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

import numpy as np
import structlog

from sopilot_ai.docproc import Tokenizer
from sopilot_ai.providers.registry import EmbeddingSpec, ModelsConfig

log = structlog.get_logger(__name__)

UNPINNED = "unpinned"


class EmbeddingError(Exception):
    """Provider failure; the worker retries it as transient (``EMBEDDING_ERROR``)."""


class EmbeddingProvider(Protocol):
    name: str
    model: str
    revision: str
    dim: int

    def tokenizer(self) -> Tokenizer: ...

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray: ...


def _normalise(vectors: Any, dim: int) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim != 2 or arr.shape[1] != dim:
        raise EmbeddingError(f"expected (n, {dim}) embeddings, got {arr.shape}")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.all(np.isfinite(arr)):
        raise EmbeddingError("zero or non-finite embedding")
    return arr / norms


class _Base:
    def __init__(self, spec: EmbeddingSpec, revision: str) -> None:
        self.spec = spec
        self.model = spec.model
        self.revision = revision
        self.dim = spec.dim
        self._tokenizer: Tokenizer | None = None

    def tokenizer(self) -> Tokenizer:
        """``docproc.tokens.HFTokenizer`` of this model (§1.1); no second tokenizer exists."""
        if self._tokenizer is None:
            from sopilot_ai.docproc.tokens import HFTokenizer

            pinned = None if self.revision == UNPINNED else self.revision
            self._tokenizer = HFTokenizer(self.spec.tokenizer, pinned)
        return self._tokenizer

    def _inputs(self, texts: Sequence[str], is_query: bool) -> list[str]:
        prefix = self.spec.query_prefix if is_query else ""
        return [prefix + t for t in texts]


class LocalEmbeddingProvider(_Base):
    """sentence-transformers on CPU (extra ``local``)."""

    name = "local"

    def __init__(self, spec: EmbeddingSpec, revision: str) -> None:
        super().__init__(spec, revision)
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            pinned = None if self.revision == UNPINNED else self.revision
            self._model = SentenceTransformer(self.model, revision=pinned, device="cpu")
        return self._model

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        try:
            out = self._load().encode(self._inputs(texts, is_query),
                                      batch_size=self.spec.batch_size,
                                      normalize_embeddings=True, convert_to_numpy=True)
        except Exception as exc:  # noqa: BLE001 - any model failure is an embedding failure
            raise EmbeddingError(type(exc).__name__) from exc
        return _normalise(out, self.dim)


class _HttpProvider(_Base):
    def __init__(self, spec: EmbeddingSpec, revision: str, base_url: str, api_key: str | None,
                 timeout: float = 60.0) -> None:
        super().__init__(spec, revision)
        import httpx

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import httpx

        try:
            resp = self._client.post(path, json=body)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EmbeddingError(type(exc).__name__) from exc


class OpenAICompatibleEmbeddingProvider(_HttpProvider):
    """``POST {base_url}/embeddings`` (TEI or another OpenAI-style server)."""

    name = "openai_compatible"

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        body = {"model": self.model, "input": self._inputs(texts, is_query)}
        data = self._post("/embeddings", body)
        try:
            rows = sorted(data["data"], key=lambda d: d["index"])
            return _normalise([r["embedding"] for r in rows], self.dim)
        except (KeyError, TypeError) as exc:
            raise EmbeddingError("malformed embeddings response") from exc


class CloudflareEmbeddingProvider(_HttpProvider):
    """Workers AI ``@cf/baai/bge-m3`` (deploy only, outside the V2 scope; ADR-006)."""

    name = "cloudflare"

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        data = self._post(f"/{self.model}", {"text": self._inputs(texts, is_query)})
        try:
            return _normalise(data["result"]["data"], self.dim)
        except (KeyError, TypeError) as exc:
            raise EmbeddingError("malformed embeddings response") from exc


def resolve_revision(spec: EmbeddingSpec, profile: str) -> str:
    if spec.revision:
        return spec.revision
    if profile == "eval":
        raise RuntimeError(f"embedding revision of {spec.key} must be pinned in profile eval")
    log.warning("embedding_revision_unpinned", model=spec.model)
    return UNPINNED


def build_embedding_provider(config: ModelsConfig, profile: str) -> EmbeddingProvider:
    import os

    spec = config.embedding()
    revision = resolve_revision(spec, profile)
    if spec.provider == "local":
        return LocalEmbeddingProvider(spec, revision)
    if spec.provider in ("openai_compatible", "cloudflare"):
        endpoint = config.provider_endpoint(spec.provider)
        key_env = endpoint.get("api_key_env")
        api_key = os.environ.get(key_env) if key_env else None
        cls = (OpenAICompatibleEmbeddingProvider if spec.provider == "openai_compatible"
               else CloudflareEmbeddingProvider)
        return cls(spec, revision, endpoint["base_url"], api_key)
    raise ValueError(f"unknown embedding provider {spec.provider!r}")
