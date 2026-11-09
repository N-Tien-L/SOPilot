"""Load ``config/models.yaml`` (TECH-V2-ai-service §4.2), the only place that declares models."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from sopilot_ai.docproc import ChunkConfig
from sopilot_ai.retrieval.context import ContextConfig

_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _expand(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if not isinstance(value, str):
        return value
    whole = _VAR.fullmatch(value)
    if whole:  # a value that is only a variable keeps YAML typing (bool, number, null)
        name, default = whole.groups()
        raw = os.environ.get(name, default if default is not None else "")
        return yaml.safe_load(raw) if raw != "" else ""
    return _VAR.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)


@dataclass(frozen=True)
class EmbeddingSpec:
    key: str
    provider: str
    model: str
    revision: str
    dim: int
    max_tokens: int
    query_prefix: str
    batch_size: int
    tokenizer: str  # HF id of the tokenizer; the model id unless the provider renames it


@dataclass(frozen=True)
class RerankSpec:
    enabled: bool
    provider: str  # local | none
    model: str
    revision: str
    max_pairs: int


@dataclass(frozen=True)
class RetrievalConfig:
    """``retrieval`` section of §4.2; the eval harness reads the same keys."""

    mode: str = "hybrid"
    candidate_pool: int = 50
    rerank_pool: int = 25
    context_k: int = 5
    rrf_k: int = 60
    rrf_weights: tuple[float, float] = (1.0, 1.0)
    doc_code_boost: float = 0.02
    cross_lingual_bm25_factor: float = 1.0
    thresholds: dict[str, float | None] = field(default_factory=lambda: {
        "dense": 0.45, "bm25": None, "hybrid": 0.45, "hybrid_rerank": 0.30})

    def __post_init__(self) -> None:
        if self.mode not in ("dense", "bm25", "hybrid"):
            raise ValueError("retrieval.mode must be dense, bm25 or hybrid")
        if min(self.candidate_pool, self.rerank_pool, self.context_k) <= 0:
            raise ValueError("retrieval pools must be positive")
        if len(self.rrf_weights) != 2:
            raise ValueError("retrieval.rrf_weights needs a dense and a BM25 weight")


@dataclass(frozen=True)
class ModelsConfig:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> ModelsConfig:
        with path.open(encoding="utf-8") as fh:
            return cls(raw=_expand(yaml.safe_load(fh)))

    def embedding(self) -> EmbeddingSpec:
        section = self.raw["embedding"]
        key = section["active"]
        entry = section["models"][key]
        revision = entry.get("revision")
        return EmbeddingSpec(
            key=key,
            provider=entry["provider"],
            model=entry["model"],
            revision="" if revision in (None, "") else str(revision),
            dim=int(entry["dim"]),
            max_tokens=int(entry.get("max_tokens", 512)),
            query_prefix=entry.get("query_prefix") or "",
            batch_size=int(entry.get("batch_size", 16)),
            tokenizer=entry.get("tokenizer") or entry["model"],
        )

    def provider_endpoint(self, name: str) -> dict[str, Any]:
        return dict(self.raw.get("providers", {}).get(name) or {})

    def chunking(self) -> ChunkConfig:
        c = self.raw.get("chunking", {})
        return ChunkConfig(target_tokens=int(c.get("target_tokens", 384)),
                           max_tokens=int(c.get("max_tokens", 512)),
                           min_tokens=int(c.get("min_tokens", 64)))

    def rerank(self) -> RerankSpec:
        r = self.raw.get("rerank") or {}
        enabled = r.get("enabled")
        return RerankSpec(
            enabled=enabled is True or str(enabled).lower() == "true",
            provider=str(r.get("provider") or "none"),
            model=str(r.get("model") or ""),
            revision="" if r.get("revision") in (None, "") else str(r["revision"]),
            max_pairs=int(r.get("max_pairs", 25)),
        )

    def retrieval(self) -> RetrievalConfig:
        r = self.raw.get("retrieval") or {}
        defaults = RetrievalConfig()
        thresholds = r.get("thresholds")
        return RetrievalConfig(
            mode=str(r.get("mode", defaults.mode)),
            candidate_pool=int(r.get("candidate_pool", defaults.candidate_pool)),
            rerank_pool=int(r.get("rerank_pool", defaults.rerank_pool)),
            context_k=int(r.get("context_k", defaults.context_k)),
            rrf_k=int(r.get("rrf_k", defaults.rrf_k)),
            rrf_weights=tuple(float(w) for w in r.get("rrf_weights", defaults.rrf_weights)),
            doc_code_boost=float(r.get("doc_code_boost", defaults.doc_code_boost)),
            cross_lingual_bm25_factor=float(
                r.get("cross_lingual_bm25_factor", defaults.cross_lingual_bm25_factor)),
            thresholds=({k: (None if v in (None, "") else float(v)) for k, v in thresholds.items()}
                        if thresholds else dict(defaults.thresholds)),
        )

    def context(self) -> ContextConfig:
        """``retrieval.context`` (§6.4a): section expansion and the token cap of the prompt."""
        c = (self.raw.get("retrieval") or {}).get("context") or {}
        defaults = ContextConfig()
        expand = c.get("expand", defaults.expand)
        return ContextConfig(
            expand=expand is True or str(expand).lower() == "true",
            section_max_tokens=int(c.get("section_max_tokens", defaults.section_max_tokens)),
            max_tokens=int(c.get("max_tokens", defaults.max_tokens)),
        )
