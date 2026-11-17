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
    provider: str  # local | modal | none
    model: str
    revision: str
    max_pairs: int
    timeout_s: float = 30.0  # modal only: per-request httpx timeout


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
class RouterClassifierSpec:
    """``router_classifier`` section (V2-44, ADR-012): artifact, labels and input format."""

    artifact_dir: Path
    max_seq_length: int
    max_input_chars: int
    previous_template: str  # needs {previous} and {current}
    previous_max_chars: int
    labels: tuple[str, ...]
    template_labels: frozenset[str]  # answered with a fixed sentence before retrieval
    deferred_labels: frozenset[str]  # never routed before retrieval
    disclaimer_labels: frozenset[str]  # retrieval runs, a fixed disclaimer is added
    out_of_scope_label: str  # becomes OUT_OF_SCOPE only after the retrieval gate refused

    def __post_init__(self) -> None:
        known = set(self.labels)
        groups = (self.template_labels, self.deferred_labels, self.disclaimer_labels,
                  frozenset({self.out_of_scope_label}))
        if len(known) != len(self.labels) or not self.labels:
            raise ValueError("router_classifier.labels must be a non-empty list of unique names")
        if any(not g <= known for g in groups):
            raise ValueError("router_classifier: a label group names a label not in labels")
        if self.template_labels & {"sop_question", "followup", "harmful", "feedback_in_chat"}:
            raise ValueError("router_classifier: retrieval and guard labels cannot be templates")
        if (self.template_labels & self.disclaimer_labels
                or self.out_of_scope_label in self.template_labels | self.disclaimer_labels):
            raise ValueError("router_classifier: template, disclaimer and out-of-scope groups "
                             "must be disjoint")
        if self.template_labels & self.deferred_labels:
            raise ValueError("router_classifier: a deferred label cannot be a template label")
        if "{previous}" not in self.previous_template or "{current}" not in self.previous_template:
            raise ValueError("router_classifier.input.with_previous needs {previous} and {current}")
        if min(self.max_seq_length, self.max_input_chars, self.previous_max_chars) <= 0:
            raise ValueError("router_classifier: lengths must be positive")


@dataclass(frozen=True)
class ModelsConfig:
    raw: dict[str, Any]

    def router_classifier(self, base_dir: Path) -> RouterClassifierSpec:
        """A relative ``artifact_dir`` is read from ``base_dir`` (the service root)."""
        c = self.raw["router_classifier"]
        given = c["input"]
        artifact = Path(str(c["artifact_dir"]))
        return RouterClassifierSpec(
            artifact_dir=artifact if artifact.is_absolute() else base_dir / artifact,
            max_seq_length=int(c["max_seq_length"]),
            max_input_chars=int(c["max_input_chars"]),
            previous_template=str(given["with_previous"]),
            previous_max_chars=int(given["previous_max_chars"]),
            labels=tuple(c["labels"]),
            template_labels=frozenset(c["template_labels"]),
            deferred_labels=frozenset(c["deferred_labels"]),
            disclaimer_labels=frozenset(c["disclaimer_labels"]),
            out_of_scope_label=str(c["out_of_scope_label"]),
        )

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
            timeout_s=float(r.get("timeout_s", 30.0)),
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
