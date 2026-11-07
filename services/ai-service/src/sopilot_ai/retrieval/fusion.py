"""Fusion, BM25 language factor, document-code boost and gate (TECH-V2-ai-service §6.4).

Pure functions over hashable candidate keys (chunk ids in the service, list indices in the eval
harness), so ``eval/`` imports this module and both rank the same way (§6.5).
"""
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from typing import Any, TypeVar

K = TypeVar("K", bound=Hashable)

MODES = ("dense", "bm25", "hybrid", "hybrid_rerank")
_LANGS = ("vi", "en")


def rrf(rankings: Sequence[Sequence[K]], weights: Sequence[float], k: int = 60,
        item_weights: Sequence[Mapping[K, float] | None] | None = None) -> dict[K, float]:
    """``fusion(c) = Σ wᵢ · fᵢ(c) / (k + rankᵢ(c))`` with 1-based ranks.

    ``item_weights[i][c]`` (default 1) scales one item of branch ``i``; it carries the
    cross-lingual BM25 factor.
    """
    if len(rankings) != len(weights):
        raise ValueError("one weight per ranking")
    fused: dict[K, float] = {}
    for n, (ranking, w) in enumerate(zip(rankings, weights, strict=True)):
        per_item = item_weights[n] if item_weights else None
        for r, key in enumerate(ranking):
            f = per_item.get(key, 1.0) if per_item else 1.0
            fused[key] = fused.get(key, 0.0) + w * f / (k + r + 1)
    return fused


def cross_lingual_weights(langs: Mapping[K, str | None], query_lang: str | None,
                          factor: float) -> dict[K, float]:
    """BM25-branch factor per candidate: ``factor`` when the chunk language differs from the
    question language; nothing (``1.0``) when either is unknown or outside vi/en, or factor 1."""
    if factor == 1.0 or query_lang not in _LANGS:
        return {}
    return {key: factor for key, lang in langs.items() if lang in _LANGS and lang != query_lang}


def apply_doc_code_boost(fusion: Mapping[K, float], matching: Iterable[K],
                         boost: float) -> dict[K, float]:
    """Add ``retrieval.doc_code_boost`` to candidates whose version's ``docCode`` matched."""
    out = dict(fusion)
    if boost:
        for key in matching:
            if key in out:
                out[key] += boost
    return out


def order(fusion: Mapping[K, float], tie_key: Any = None) -> list[K]:
    """Best first; ties broken by ``tie_key(key)`` (the key itself by default)."""
    tie = tie_key or (lambda key: key)
    return sorted(fusion, key=lambda key: (-fusion[key], tie(key)))


def _field(candidate: Any, name: str) -> Any:
    if isinstance(candidate, Mapping):
        return candidate.get(name)
    return getattr(candidate, name)


def gate_score(mode: str, candidate: Any) -> float | None:
    """Score the refusal threshold compares (§6.4 table); ``None`` means no gate (``bm25``).

    ``hybrid`` gates on the cosine of the best fused candidate, which must always be present:
    candidates found only by BM25 get a direct cosine before this is called.
    """
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode}")
    if mode == "bm25":
        return None
    if mode == "hybrid_rerank":
        score = _field(candidate, "rerank_score")
        if score is None:
            raise ValueError("hybrid_rerank gate requires rerank_score")
        return float(score)
    score = _field(candidate, "dense_score")
    if score is None:
        raise ValueError("dense/hybrid gate requires dense_score for every candidate")
    return float(score)


def threshold_for(mode: str, thresholds: Mapping[str, float | None]) -> float | None:
    """Per-mode threshold of ``retrieval.thresholds``; ``None`` means the mode never refuses."""
    if mode not in MODES:
        raise ValueError(f"unknown retrieval mode {mode}")
    value = thresholds.get(mode)
    return None if value is None else float(value)


def passes(gate: float | None, threshold: float | None) -> bool:
    """No threshold (``bm25``) never refuses; otherwise the best candidate must reach it."""
    if threshold is None:
        return True
    return gate is not None and gate >= threshold
