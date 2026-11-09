"""Rule-based input guard (FR-13 layer 1, TECH-V2-ai-service §7.1 step 2). No LLM.

Three outcomes from the YAML rules (``guard_rules.yaml``):

- **block**: prompt reveal, instruction override, fake system role, and the real-harm group
  (threats, self-harm, harassment). The caller answers with a fixed sentence.
- **flag**: role-play, "skip the steps", other-workspace talk. The question is still answered and a
  ``guard_events(INPUT_FLAG)`` row is written.
- **abuse words**: whole-word profanity. They are not a verdict on their own; the router strips them
  and decides on what is left ("bóc rồi xét").
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

from sopilot_ai.qa.resources import load_yaml
from sopilot_ai.qa.textnorm import Token, match_phrases, nfc
from sopilot_ai.retrieval.lexical import fold

_LEET = str.maketrans("013457", "oieast")

ABUSE_RULE = "abuse.profanity"
ABUSE_STANDALONE_RULE = "abuse.standalone"


@dataclass(frozen=True)
class _Rule:
    id: str
    template: str | None
    raw: bool
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class GuardResult:
    blocked_rule: str | None = None
    block_template: str | None = None
    flag_rules: tuple[str, ...] = ()
    abuse_indexes: tuple[int, ...] = ()
    abuse_rules: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.blocked_rule is not None


def _compile(entries: list[dict]) -> tuple[_Rule, ...]:
    return tuple(
        _Rule(e["id"], e.get("template"), bool(e.get("raw", False)),
              tuple(re.compile(p, re.DOTALL) for p in e["patterns"]))
        for e in entries)


@lru_cache(maxsize=1)
def _rules() -> dict:
    data = load_yaml("guard_rules.yaml")
    return {
        "block": _compile(data["block"]),
        "flag": _compile(data["flag"]),
        "abuse": data["abuse"],
        "standalone_max_tokens": int(data["standalone_max_tokens"]),
        "min_meaningful_tokens": int(data["min_meaningful_tokens"]),
    }


def min_meaningful_tokens() -> int:
    return _rules()["min_meaningful_tokens"]


def _views(text: str) -> tuple[str, str]:
    """(raw, normalized): lowercase NFC with diacritics; and stripped with leetspeak undone."""
    raw = nfc(text).lower()
    return raw, fold(raw).translate(_LEET)


def _first_hit(rules: Sequence[_Rule], raw: str, norm: str) -> list[_Rule]:
    return [r for r in rules
            if any(p.search(raw if r.raw else norm) for p in r.patterns)]


def _inside_code(text: str, token: Token) -> bool:
    """A token glued to ``-`` or ``/`` belongs to a document code ("QT-VL-02", "DM-05")."""
    before = text[token.start - 1] if token.start > 0 else ""
    after = text[token.end] if token.end < len(text) else ""
    return before in ("-", "/") or after in ("-", "/")


def inspect(text: str, tokens: Sequence[Token]) -> GuardResult:
    """Run the rules on the PII-masked question. ``tokens`` come from the same NFC text."""
    rules = _rules()
    raw, norm = _views(text)

    blocked = _first_hit(rules["block"], raw, norm)
    flags = tuple(r.id for r in _first_hit(rules["flag"], raw, norm))
    abuse = rules["abuse"]

    hits = match_phrases(tokens, abuse["accented"])
    hits += match_phrases(tokens, abuse["folded"], use_folded=True)
    rule_ids: list[str] = []
    if hits:
        rule_ids.append(ABUSE_RULE)
    if len(tokens) <= rules["standalone_max_tokens"]:
        standalone = [
            (phrase, idx) for phrase, idx in match_phrases(tokens, abuse["standalone_only"])
            if not any(_inside_code(text, tokens[i]) for i in idx)]
        if standalone:
            hits += standalone
            rule_ids.append(ABUSE_STANDALONE_RULE)
    indexes = tuple(sorted({i for _, idx in hits for i in idx}))

    return GuardResult(
        blocked_rule=blocked[0].id if blocked else None,
        block_template=blocked[0].template if blocked else None,
        flag_rules=flags,
        abuse_indexes=indexes,
        abuse_rules=tuple(rule_ids),
    )
