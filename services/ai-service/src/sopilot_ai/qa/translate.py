"""Which language to translate a question into, and the prompt for it (TECH-V2-ai-service §6.4b).

``bge-m3`` and the reranker are multilingual, but both score a question and a passage in different
languages lower than the same pair in one language: on 15 answerable questions over English pages
the Vietnamese form passed the rerank gate 6 times, the English form 15 times, and 3 of the 15
Vietnamese questions did not even reach the 25 candidates. BM25 shares no words across the two
languages. So a question is also asked in the language the documents are written in.

Pure functions: the LLM call itself is made by the step.
"""
from __future__ import annotations

from collections.abc import Mapping

SUPPORTED = ("vi", "en")  # the languages in scope (PRD-V2)
LANGUAGE_NAMES = {"vi": "Vietnamese", "en": "English"}


def translation_target(question_lang: str | None, doc_langs: Mapping[str, int], *,
                       min_share: float | None) -> str | None:
    """Language to translate the question into, or ``None`` when it should not be translated.

    ``doc_langs`` counts the documents the asker may read by language. The question is translated
    into the *other* supported language when that language holds at least ``min_share`` of the
    ``vi``/``en`` documents; a workspace in one language never pays for a call. ``min_share=None``
    switches the feature off. Other document languages are not counted.
    """
    if min_share is None or question_lang not in SUPPORTED:
        return None
    total = sum(doc_langs.get(lang, 0) for lang in SUPPORTED)
    if total <= 0:
        return None
    other = "en" if question_lang == "vi" else "vi"
    return other if doc_langs.get(other, 0) / total >= min_share else None


def build_translate_prompt(question: str, target_lang: str) -> list[dict[str, str]]:
    """Messages for the translation call; the question is data, never an instruction."""
    name = LANGUAGE_NAMES[target_lang]
    system = (f"Translate the user's question about company procedures into {name}. Keep "
              "numbers, names, codes and product or tool names unchanged. Do not answer the "
              "question and do not add anything. Print only the translated question, one line.")
    return [{"role": "system", "content": system}, {"role": "user", "content": question}]
