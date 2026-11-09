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

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol

from sopilot_ai.qa import templates
from sopilot_ai.qa.guard import min_meaningful_tokens
from sopilot_ai.qa.query_frame import QueryFrame
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
