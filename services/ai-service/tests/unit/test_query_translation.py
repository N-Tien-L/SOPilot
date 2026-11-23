"""Translating a question toward the language of the documents (V2-47, TECH-V2-ai-service §6.4b).

Measured on 10 handbook pages with 15 answerable questions: asked in English, 15 of 15 were
answered from the right chunk; the same questions in Vietnamese, 6 of 15 passed the rerank gate.
Translating the question into the language of the documents lifted that to 12 of 15, with no
unanswerable question accepted.
"""
from __future__ import annotations

import pytest

from sopilot_ai.qa.prompt import clean_rewrite
from sopilot_ai.qa.translate import build_translate_prompt, translation_target


def test_vietnamese_question_over_english_documents_is_translated_to_english() -> None:
    assert translation_target("vi", {"en": 10}, min_share=0.2) == "en"


def test_english_question_over_vietnamese_documents_is_translated_to_vietnamese() -> None:
    assert translation_target("en", {"vi": 4}, min_share=0.2) == "vi"


def test_question_in_the_language_of_the_documents_is_not_translated() -> None:
    assert translation_target("vi", {"vi": 10}, min_share=0.2) is None
    assert translation_target("en", {"en": 10}, min_share=0.2) is None


def test_a_few_documents_in_the_other_language_do_not_trigger_a_call() -> None:
    assert translation_target("vi", {"vi": 9, "en": 1}, min_share=0.2) is None  # 10 percent
    assert translation_target("vi", {"vi": 8, "en": 2}, min_share=0.2) == "en"  # exactly 20


def test_mixed_workspace_translates_toward_the_other_language() -> None:
    assert translation_target("vi", {"vi": 5, "en": 5}, min_share=0.2) == "en"
    assert translation_target("en", {"vi": 5, "en": 5}, min_share=0.2) == "vi"


def test_unknown_question_language_or_no_documents_means_no_translation() -> None:
    assert translation_target(None, {"en": 10}, min_share=0.2) is None
    assert translation_target("fr", {"en": 10}, min_share=0.2) is None
    assert translation_target("vi", {}, min_share=0.2) is None


def test_other_document_languages_are_ignored_in_the_share() -> None:
    assert translation_target("vi", {"en": 2, "fr": 100}, min_share=0.2) == "en"


def test_the_switch_is_off_when_the_share_is_none() -> None:
    assert translation_target("vi", {"en": 10}, min_share=None) is None


@pytest.mark.parametrize(("target", "name"), [("en", "English"), ("vi", "Vietnamese")])
def test_prompt_names_the_target_language_and_forbids_answering(target: str, name: str) -> None:
    messages = build_translate_prompt("Khung giờ UTC của AMER là gì?", target)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert name in messages[0]["content"]
    assert "not answer" in messages[0]["content"].lower()
    assert messages[1]["content"] == "Khung giờ UTC của AMER là gì?"


def test_model_output_is_cleaned_like_a_rewrite() -> None:
    assert clean_rewrite('Question: "What is the UTC period for AMER?"\n', max_chars=200) == (
        "What is the UTC period for AMER?")
    assert clean_rewrite("", max_chars=200) is None
