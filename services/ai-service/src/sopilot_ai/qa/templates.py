"""Fixed sentences from ``templates.yaml`` (TECH-V2-ai-service §7.1)."""
from __future__ import annotations

from typing import Literal

from sopilot_ai.qa.resources import load_yaml

Lang = Literal["vi", "en"]
LANGS: tuple[Lang, ...] = ("vi", "en")


def render(key: str, lang: str, **values: object) -> str:
    """Sentence ``key`` in ``lang`` (unknown language falls back to Vietnamese)."""
    texts = load_yaml("templates.yaml")[key]["text"]
    text = texts.get(lang) or texts["vi"]
    return text.format(**values) if values else text


def triggers(key: str) -> tuple[str, ...]:
    return tuple(load_yaml("templates.yaml")[key].get("triggers", ()))


def priority(key: str) -> int:
    return int(load_yaml("templates.yaml")[key].get("priority", 0))


def not_found_openings() -> tuple[str, ...]:
    """The fixed opening sentence in every language."""
    return tuple(load_yaml("templates.yaml")["not_found_opening"]["text"][lang] for lang in LANGS)
