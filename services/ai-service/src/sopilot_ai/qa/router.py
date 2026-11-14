"""Rule router: "bóc rồi xét" (TECH-V2-ai-service §7.1 step 3, FR-13, V2-10).

Greeting, thanks and "who are you" words are stripped from the question, together with the
profanity the guard already found. What is left decides:

- nothing left, or too few meaningful tokens -> a fixed sentence picked by the kind of word that
  was stripped (``TEMPLATE``, no LLM);
- something left -> RAG runs on the stripped text.

There is no LLM intent classifier. The semantic router of ``V2-27`` plugs in through
:class:`SemanticRouter`; it runs after the rules and, per D1, only decides ``OUT_OF_SCOPE`` after
the retrieval gate has already refused, so it cannot turn a "pass" into a refusal.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import yaml

from sopilot_ai.qa import templates
from sopilot_ai.qa.guard import min_meaningful_tokens
from sopilot_ai.qa.query_frame import QueryFrame
from sopilot_ai.qa.resources import load_yaml
from sopilot_ai.qa.textnorm import match_phrases, remove_tokens

KIND_ABUSE = "abuse_only"
KIND_NOT_UNDERSTOOD = "not_understood"
_STRIPPABLE = ("about_bot", "thanks", "greeting")  # highest priority first


class SemanticRouter(Protocol):
    """Hook for ``V2-27``: classify an intent from the question embedding. Not used in V2-10."""

    async def classify(self, frame: QueryFrame) -> str | None: ...


@dataclass(frozen=True)
class RouteResult:
    working_text: str  # the question without stripped words; RAG runs on this
    stripped: tuple[str, ...]  # kinds stripped: about_bot / thanks / greeting / abuse
    removed: frozenset[int]  # token indexes cut out (abuse + greeting words)
    template_key: str | None  # set when the question needs no retrieval
    refusal_reason: str | None  # "INPUT_INVALID" for not_understood, else None

    @property
    def answered_by_template(self) -> bool:
        return self.template_key is not None


def _template_for(stripped: Collection[str]) -> str:
    """Profanity wins (neutral sentence with a hint on how to ask); then the strippable kinds by
    ``priority``; nothing stripped means the question simply was not understood."""
    if "abuse" in stripped:
        return KIND_ABUSE
    for kind in sorted((k for k in stripped if k in _STRIPPABLE), key=templates.priority,
                       reverse=True):
        return kind
    return KIND_NOT_UNDERSTOOD


@dataclass(frozen=True)
class Stripped:
    """The question after greeting / thanks / about-bot words and profanity were cut out."""

    working_text: str
    kinds: tuple[str, ...]  # about_bot / thanks / greeting / abuse
    removed: frozenset[int]
    nothing_left: bool


def strip_words(frame: QueryFrame, abuse_indexes: Collection[int] = ()) -> Stripped:
    """Cut greeting, thanks and about-bot words and ``abuse_indexes`` out of the question."""
    removed: set[int] = set(abuse_indexes)
    kinds: list[str] = ["abuse"] if abuse_indexes else []
    for key in _STRIPPABLE:
        hits = match_phrases(frame.tokens, templates.triggers(key), use_folded=True)
        # A word the guard already took as profanity is not also a greeting.
        hits = [(p, idx) for p, idx in hits if not removed.intersection(idx)]
        if hits:
            kinds.append(key)
            for _, idx in hits:
                removed.update(idx)
    text = remove_tokens(frame.text, frame.tokens, removed)
    nothing_left = all(t.index in removed for t in frame.tokens)
    return Stripped(text, tuple(kinds), frozenset(removed), nothing_left)


def judge(frame: QueryFrame, stripped: Stripped, *, min_meaningful: int | None = None,
          check_meaningful: bool = True) -> RouteResult:
    """Decide on what is left: a fixed sentence, or RAG on ``stripped.working_text``.

    With ``check_meaningful`` false only the "nothing left" case is decided (the router step);
    the meaningful-token step then calls again with it true.
    """
    threshold = min_meaningful_tokens() if min_meaningful is None else min_meaningful
    base = (stripped.working_text, stripped.kinds, stripped.removed)
    if stripped.nothing_left or (
            check_meaningful and frame.meaningful_count(stripped.removed) < threshold):
        key = _template_for(stripped.kinds)
        # "Not understood" is INPUT_INVALID on every path (TECH §3.4); the other sentences carry
        # no refusal_reason.
        return RouteResult(*base, key, "INPUT_INVALID" if key == KIND_NOT_UNDERSTOOD else None)
    return RouteResult(*base, None, None)


def strip_and_judge(frame: QueryFrame, abuse_indexes: Collection[int] = (), *,
                    min_meaningful: int | None = None) -> RouteResult:
    """Both stages at once (what the two pipeline steps do in sequence)."""
    return judge(frame, strip_words(frame, abuse_indexes), min_meaningful=min_meaningful)


# --- V2-27 semantic layer (TECH-V2-ai-service §7.1 step 3) ----------------------------------
# Runs after the rules, and only on questions the rules left undecided. It never calls an LLM and
# never blocks: harmful questions stay with the guard. Nothing here is reached unless the caller
# builds a layer; with SOPILOT_SEMANTIC_ROUTER_ENABLED=false the caller builds none (None).

REFERENCE_INTENT = "sop_question"  # the contrast class: margin is measured against it
TEMPLATE_INTENTS = frozenset({"greeting", "thanks", "about_bot", "abuse_only"})
HISTORY_INTENTS = frozenset({"about_source"})  # only with a previous turn
DISCLAIMER_INTENTS = frozenset({"action_request", "personal_data", "legal_medical"})
FEEDBACK_INTENT = "feedback_in_chat"  # not routed yet (owner decision open, see report)
OUT_OF_SCOPE_CANDIDATE = "off_topic"  # becomes OUT_OF_SCOPE only after the gate refused
SEMANTIC_INTENTS = frozenset(
    TEMPLATE_INTENTS | HISTORY_INTENTS | DISCLAIMER_INTENTS
    | {FEEDBACK_INTENT, OUT_OF_SCOPE_CANDIDATE})

ACTION_TEMPLATE = "template"  # fixed sentence, no LLM, no quota
ACTION_DISCLAIMER = "disclaimer"  # RAG runs, a fixed disclaimer is added before citations
ACTION_OUT_OF_SCOPE = "out_of_scope_candidate"  # RAG runs; refused by the gate -> OUT_OF_SCOPE
ACTION_RAG = "rag"


class QueryEmbedder(Protocol):
    """The embedding provider as the router sees it (``providers.embedding`` satisfies it)."""

    def embed(self, texts: Sequence[str], *, is_query: bool) -> np.ndarray: ...


@dataclass(frozen=True)
class IntentThreshold:
    threshold: float  # minimum cosine of the best exemplar of the intent
    margin: float  # minimum gap to the best ``sop_question`` exemplar


@dataclass(frozen=True)
class RouterThresholds:
    default: IntentThreshold
    intents: Mapping[str, IntentThreshold]

    def for_intent(self, intent: str) -> IntentThreshold:
        return self.intents.get(intent, self.default)


@dataclass(frozen=True)
class SemanticDecision:
    intent: str | None  # routed intent; None means the question goes to RAG as before
    top_intent: str  # best eligible intent, routed or not (for the harness and the log)
    top_score: float
    sop_score: float  # best cosine to a ``sop_question`` exemplar
    margin: float  # top_score - sop_score

    @property
    def routed(self) -> bool:
        return self.intent is not None


def _threshold(data: Mapping[str, Any], where: str) -> IntentThreshold:
    value = IntentThreshold(float(data["threshold"]), float(data["margin"]))
    if not (0.0 <= value.threshold <= 1.0) or value.margin < 0.0:
        raise ValueError(f"{where}: threshold must be in [0, 1] and margin >= 0")
    return value


def parse_thresholds(data: Mapping[str, Any]) -> RouterThresholds:
    intents = data.get("intents") or {}
    unknown = set(intents) - SEMANTIC_INTENTS - {REFERENCE_INTENT}
    if unknown:
        raise ValueError(f"router thresholds for unknown intents: {sorted(unknown)}")
    return RouterThresholds(
        default=_threshold(data["default"], "default"),
        intents={k: _threshold(v, k) for k, v in intents.items()},
    )


def parse_exemplars(data: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    unknown = set(data) - SEMANTIC_INTENTS - {REFERENCE_INTENT}
    if unknown:
        raise ValueError(f"router exemplars for unknown intents: {sorted(unknown)}")
    if REFERENCE_INTENT not in data:
        raise ValueError("router exemplars need the sop_question contrast class")
    out: dict[str, tuple[str, ...]] = {}
    for intent, texts in data.items():
        if not isinstance(texts, list) or not texts or not all(
                isinstance(t, str) and t.strip() for t in texts):
            raise ValueError(f"exemplars of {intent} must be a non-empty list of sentences")
        out[intent] = tuple(texts)
    return out


def load_exemplars(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    data = (load_yaml("router_exemplars.yaml") if path is None
            else yaml.safe_load(path.read_text(encoding="utf-8")))
    return parse_exemplars(data)


def load_thresholds(path: Path | None = None) -> RouterThresholds:
    data = (load_yaml("router_thresholds.yaml") if path is None
            else yaml.safe_load(path.read_text(encoding="utf-8")))
    return parse_thresholds(data)


def _unit(vec: np.ndarray) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm > 0 else vec


class SemanticLayer:
    """Cosine routing against precomputed exemplar vectors.

    Exemplar vectors are cached by ``(model_id, text)``. ``model_id`` names the embedding model
    and revision, so a changed model embeds the exemplars again and never compares vectors of
    two models. ``cache`` may be shared (for example with the ``rag.embedding_cache`` adapter).
    """

    def __init__(self, embedder: QueryEmbedder, *, model_id: str,
                 exemplars: Mapping[str, Sequence[str]], thresholds: RouterThresholds,
                 cache: MutableMapping[tuple[str, str], np.ndarray] | None = None) -> None:
        self._embedder = embedder
        self.model_id = model_id
        self.thresholds = thresholds
        self._cache: MutableMapping[tuple[str, str], np.ndarray] = (
            {} if cache is None else cache)
        owners: list[str] = []
        rows: list[np.ndarray] = []
        for intent, texts in exemplars.items():
            rows.append(self._vectors(list(texts)))
            owners += [intent] * len(texts)
        self._matrix = np.vstack(rows)
        self._owner = np.array(owners)

    def _vectors(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if (self.model_id, t) not in self._cache]
        if missing:
            fresh = self._embedder.embed(missing, is_query=True)
            for text, vec in zip(missing, fresh, strict=True):
                self._cache[(self.model_id, text)] = _unit(vec)
        return np.vstack([self._cache[(self.model_id, t)] for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        """The question's vector. The caller may reuse it for dense retrieval (no history)."""
        return _unit(self._embedder.embed([text], is_query=True)[0])

    def decide(self, vector: np.ndarray, *, has_history: bool) -> SemanticDecision:
        sims = self._matrix @ _unit(vector)
        eligible = self._owner != REFERENCE_INTENT
        if not has_history:
            eligible &= ~np.isin(self._owner, list(HISTORY_INTENTS))
        sop_score = float(sims[self._owner == REFERENCE_INTENT].max())
        best = int(np.argmax(np.where(eligible, sims, -np.inf)))
        top_intent = str(self._owner[best])
        top_score = float(sims[best])
        margin = top_score - sop_score
        limit = self.thresholds.for_intent(top_intent)
        routed = top_intent if top_score >= limit.threshold and margin >= limit.margin else None
        return SemanticDecision(routed, top_intent, top_score, sop_score, margin)

    def classify(self, text: str, *, has_history: bool) -> SemanticDecision:
        return self.decide(self.embed_query(text), has_history=has_history)


def build_semantic_layer(*, enabled: bool, embedder_factory: Callable[[], QueryEmbedder],
                         model_id: str, exemplars: Mapping[str, Sequence[str]] | None = None,
                         thresholds: RouterThresholds | None = None,
                         cache: MutableMapping[tuple[str, str], np.ndarray] | None = None,
                         ) -> SemanticLayer | None:
    """``None`` when disabled: the factory (which may load a model) is not called then."""
    if not enabled:
        return None
    return SemanticLayer(
        embedder_factory(), model_id=model_id,
        exemplars=load_exemplars() if exemplars is None else exemplars,
        thresholds=load_thresholds() if thresholds is None else thresholds, cache=cache)


def action_for(intent: str | None) -> str:
    """What the caller does with a decision. Feedback and unrouted questions go to RAG."""
    if intent in TEMPLATE_INTENTS or intent in HISTORY_INTENTS:
        return ACTION_TEMPLATE
    if intent in DISCLAIMER_INTENTS:
        return ACTION_DISCLAIMER
    if intent == OUT_OF_SCOPE_CANDIDATE:
        return ACTION_OUT_OF_SCOPE
    return ACTION_RAG


def is_out_of_scope(decision: SemanticDecision, *, gate_refused: bool) -> bool:
    """OUT_OF_SCOPE needs both: the retrieval gate refused, and the router saw ``off_topic``.
    The router never changes a gate decision to "pass" (TECH §7.1, D1)."""
    return gate_refused and decision.intent == OUT_OF_SCOPE_CANDIDATE
