"""Metadata suggestions, pure part (V2-25): rules, prompt budget, output validation, cache key."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from sopilot_ai.suggest import llm, rules

CATS = [{"id": "11111111-1111-1111-1111-111111111111", "name": "Mua sắm"},
        {"id": "22222222-2222-2222-2222-222222222222", "name": "Nhân sự"}]
SOP = """# Quy trình mua hàng

## 1. Mục đích

Quy định cách đặt mua hàng cho các phòng ban trong công ty và cách kiểm tra hàng.

| Bước | Ai |
|---|---|
| 1 | Trưởng phòng |

Nhân viên gửi đề nghị mua hàng qua cổng nội bộ, kèm báo giá từ ít nhất hai nhà cung cấp.
"""


def test_title_is_the_first_heading_not_the_file_name() -> None:
    assert rules.title_candidate(SOP, "procurement.pdf") == "Quy trình mua hàng"


def test_title_falls_back_to_file_title_without_heading() -> None:
    plain = "Plain text only, no heading here at all."
    assert rules.title_candidate(plain, " Laptop.md ") == "Laptop.md"


def test_title_is_never_empty_and_capped() -> None:
    assert rules.title_candidate("", "") == "Untitled"
    assert len(rules.title_candidate("# " + "x" * 500, "f")) == 200


def test_paragraphs_skip_headings_and_table_rows() -> None:
    paras = rules.representative_paragraphs(SOP)
    assert paras == [
        "Quy định cách đặt mua hàng cho các phòng ban trong công ty và cách kiểm tra hàng.",
        "Nhân viên gửi đề nghị mua hàng qua cổng nội bộ, kèm báo giá từ ít nhất hai nhà cung cấp.",
    ]


def test_outline_lists_headings_in_order() -> None:
    assert rules.headings(SOP) == ["# Quy trình mua hàng", "## 1. Mục đích"]


def test_prompt_respects_the_input_budget() -> None:
    huge = "# T\n\n" + ("Đoạn văn dài. " * 2000)
    msgs = llm.build_messages("T", huge, CATS, ["mua sắm"], max_input_tokens=200)
    # the system prompt is counted separately from the input budget
    assert sum(len(m["content"]) for m in msgs) <= 200 * 4 + 50
    assert CATS[0]["id"] in msgs[1]["content"]  # the category list survives the cut


def test_valid_output_is_kept() -> None:
    raw = json.dumps({"description": " Quy trình mua hàng. ", "category_id": CATS[0]["id"],
                      "proposed_category_name": None, "tags": ["Mua Sắm", "kiểm tra"]})
    s = llm.parse_output(raw, {c["id"] for c in CATS})
    assert s.description == "Quy trình mua hàng."
    assert s.category_id == CATS[0]["id"]
    assert s.tags == ["mua sắm", "kiểm tra"]


def test_unknown_category_id_is_dropped_and_name_proposed() -> None:
    raw = json.dumps({"description": "d", "category_id": str(uuid4()),
                      "proposed_category_name": "Pháp chế", "tags": []})
    s = llm.parse_output(raw, {c["id"] for c in CATS})
    assert s.category_id is None
    assert s.proposed_category_name == "Pháp chế"


def test_proposed_name_is_ignored_when_a_category_is_chosen() -> None:
    raw = json.dumps({"category_id": CATS[1]["id"], "proposed_category_name": "Khác"})
    s = llm.parse_output(raw, {c["id"] for c in CATS})
    assert s.category_id == CATS[1]["id"] and s.proposed_category_name is None


def test_reasoning_block_and_code_fence_are_stripped() -> None:
    raw = "<think>nghĩ nhiều</think>\n```json\n{\"description\": \"ok\", \"tags\": []}\n```"
    assert llm.parse_output(raw, set()).description == "ok"


def test_tags_are_deduplicated_and_capped() -> None:
    raw = json.dumps({"tags": [f"t{i}" for i in range(20)] + ["T1", " "]})
    s = llm.parse_output(raw, set())
    assert len(s.tags) == llm.TAGS_MAX
    assert len(set(s.tags)) == len(s.tags)


@pytest.mark.parametrize("raw", ["no json here", "{not json}", "[1, 2]", "{\"a\": 1"])
def test_unreadable_output_raises_so_the_caller_can_retry(raw: str) -> None:
    with pytest.raises(ValueError):
        llm.parse_output(raw, set())


def test_cache_key_is_per_workspace_and_per_category_list() -> None:
    ws1, ws2 = uuid4(), uuid4()
    base = llm.cache_key(ws1, "ab" * 32, "m", CATS)
    assert base == llm.cache_key(ws1, "ab" * 32, "m", list(reversed(CATS)))  # order-insensitive
    assert base != llm.cache_key(ws2, "ab" * 32, "m", CATS)
    assert base != llm.cache_key(ws1, "ab" * 32, "m", CATS[:1])
    assert base != llm.cache_key(ws1, "cd" * 32, "m", CATS)
    assert base != llm.cache_key(ws1, "ab" * 32, "other-model", CATS)
