"""Metadata suggestions follow the language of the document (V2-25, found in V2-47).

The suggestion model (a Qwen model) answered English documents in Chinese ("same language as the
document" was too weak): 7 of 9 English pages in a measurement, tags included. The prompt now names
the detected language, and an answer in CJK script for an English or Vietnamese document is rejected
so the runner retries and then falls back to the rules.
"""
from __future__ import annotations

import json

import pytest

from sopilot_ai.suggest import llm

DOC = "# Expenses\n\nTeam members submit receipts for every business expense.\n"


def _system(language: str | None) -> str:
    return llm.build_messages("t", DOC, [], [], 500, language)[0]["content"]


@pytest.mark.parametrize(("language", "name"), [("en", "English"), ("vi", "Vietnamese")])
def test_prompt_names_the_language_of_the_document(language: str, name: str) -> None:
    system = _system(language)
    assert f"written in {name}" in system
    assert "never in Chinese" in system


def test_prompt_without_a_detected_language_still_warns_about_chinese() -> None:
    system = _system(None)
    assert "written in" not in system
    assert "unless the document itself is Chinese" in system


def test_prompt_budget_still_counts_the_longer_system_prompt() -> None:
    huge = "# T\n\n" + ("Long paragraph. " * 2000)
    msgs = llm.build_messages("T", huge, [], [], 200, "en")
    assert sum(len(m["content"]) for m in msgs) <= 200 * 4 + 50


def test_prompt_version_changed_so_cached_chinese_descriptions_are_not_reused() -> None:
    assert llm.PROMPT_VERSION != "suggest-v1"


@pytest.mark.parametrize("language", ["en", "vi"])
def test_chinese_description_is_rejected_for_english_and_vietnamese(language: str) -> None:
    raw = json.dumps({"description": "本文件规定了费用报销流程。", "tags": ["expenses"]})
    with pytest.raises(ValueError):
        llm.parse_output(raw, set(), language)


def test_chinese_tag_is_rejected_too() -> None:
    raw = json.dumps({"description": "Expense policy.", "tags": ["expenses", "报销"]})
    with pytest.raises(ValueError):
        llm.parse_output(raw, set(), "en")


def test_chinese_proposed_category_is_rejected_too() -> None:
    raw = json.dumps({"description": "Expense policy.", "proposed_category_name": "财务",
                      "tags": []})
    with pytest.raises(ValueError):
        llm.parse_output(raw, set(), "en")


def test_chinese_is_accepted_when_the_language_is_unknown() -> None:
    raw = json.dumps({"description": "本文件规定了费用报销流程。", "tags": ["报销"]})
    assert llm.parse_output(raw, set(), None).description == "本文件规定了费用报销流程。"


def test_vietnamese_diacritics_are_not_mistaken_for_cjk() -> None:
    raw = json.dumps({"description": "Quy trình mua sắm thiết bị văn phòng.", "tags": ["mua sắm"]})
    assert llm.parse_output(raw, set(), "vi").tags == ["mua sắm"]
