"""V2-10 mốc 4: answer-level harness (coverage, citation precision, refusals, faithfulness).

Retrieval is BM25 or dense over a hash embedder and the LLM is a function, so nothing here needs a
model download or an endpoint. The numbers of a real run come from ``sopilot_eval.answers``.
"""
from __future__ import annotations

import pytest
from sopilot_ai.retrieval.context import ContextConfig

from sopilot_eval.answers import (
    Setup,
    answer_one,
    answers_report,
    coverage_report,
    fixed_subset,
    judge_messages,
    parse_verdict,
    retrieve,
)
from sopilot_eval.corpus import Chunk
from sopilot_eval.embedders import HashEmbedder
from sopilot_eval.retrievers import Index

SECTION = ("1. Nghỉ phép",)
NOT_FOUND = "Không tìm thấy thông tin này trong các tài liệu hiện có."


def chunk(doc: str, start: int, text: str, kind: str = "PROSE", section=SECTION) -> Chunk:
    return Chunk(doc=f"{doc}.md", page=1, text=text, index_text=text, char_start=start,
                 char_end=start + len(text), page_end=1, lang="vi", kind=kind,
                 section_path=section, doc_id=doc)


LEAD = chunk("qt01", 0, "Quy định nghỉ phép năm của công ty cho nhân viên chính thức", "SECTION")
RULE = chunk("qt01", 100, "Nhân viên được nghỉ phép mười hai ngày mỗi năm khi đủ điều kiện")
EXCEPTION = chunk("qt01", 200, "Ngoại lệ: nhân viên thử việc không được nghỉ phép năm")
OTHER = chunk("qt02", 0, "Quy trình mua hàng cần trưởng phòng duyệt trong hai ngày",
              section=("1. Mua hàng",))
SPANS = {
    "rule": {"span_id": "rule", "doc_id": "qt01", "start_char": 100,
             "end_char": 100 + len(RULE.text)},
    "exception": {"span_id": "exception", "doc_id": "qt01", "start_char": 200,
                  "end_char": 200 + len(EXCEPTION.text)},
    "buy": {"span_id": "buy", "doc_id": "qt02", "start_char": 0, "end_char": len(OTHER.text)},
}


def setup(retriever: str = "bm25", thresholds=None, **context) -> Setup:
    chunks = [LEAD, RULE, EXCEPTION, OTHER]
    return Setup(chunks, Index(chunks, HashEmbedder()), {"retriever": retriever, "k": 1},
                 thresholds or {}, ContextConfig(**context), lambda t: len(t.split()), SPANS)


def question(qid="q1", text="nhân viên được nghỉ phép mười hai ngày", sets=(("rule", "exception"),),
             answerable=True, types=("condition_exception",)) -> dict:
    return {"id": qid, "question": text, "lang": "vi", "answerable": answerable,
            "evidence_sets": [list(s) for s in sets] if answerable else [],
            "query_types": list(types), "expected": []}


# -- coverage -----------------------------------------------------------------------------------

def test_expanding_the_section_brings_in_the_exception_the_hit_alone_misses() -> None:
    report = coverage_report(setup(), [question()])
    on, off = report["by_expand"]["on"]["all"], report["by_expand"]["off"]["all"]
    assert on["full"] == 1.0 and off["full"] == 0.0  # both spans needed; the hit holds one
    assert off["span_recall"] == 0.5 and on["span_recall"] == 1.0
    assert on["context_tokens"] > off["context_tokens"]


def test_groups_are_reported_apart_and_unanswerable_questions_are_left_out() -> None:
    qs = [question("a", types=("condition_exception", "multi_passage")),
          question("b", "trưởng phòng duyệt mua hàng", (("buy",),), types=("fact",)),
          question("c", "thời tiết hôm nay", answerable=False)]
    report = coverage_report(setup(), qs)
    on = report["by_expand"]["on"]
    assert report["n_questions"] == 2 and on["all"]["n"] == 2
    assert set(on) == {"all", "condition_exception", "multi_passage"}
    assert on["multi_passage"]["n"] == 1


def test_the_token_cap_keeps_the_top_source() -> None:
    capped = coverage_report(setup(max_tokens=3), [question()])
    assert capped["by_expand"]["on"]["all"]["sources"] == 1.0


# -- answers ------------------------------------------------------------------------------------

def say(text: str):
    calls: list[list[dict]] = []

    def generate(messages):
        calls.append(list(messages))
        return text

    generate.calls = calls  # type: ignore[attr-defined]
    return generate


def test_a_cited_source_that_holds_gold_counts_as_precise() -> None:
    row, sources, _ = answer_one(setup(), question(), say("Được nghỉ mười hai ngày [1]."),
                                 expand=True)
    assert row.outcome == "ANSWERED" and (row.cited, row.cited_correct) == (1, 1)
    assert sources and row.llm_calls == 1 and row.context_tokens > 0


def test_a_citation_to_the_wrong_document_is_not_precise() -> None:
    q = question("q2", "nhân viên được nghỉ phép mười hai ngày", (("buy",),))  # gold elsewhere
    row, _, _ = answer_one(setup(), q, say("Được nghỉ [1]."), expand=True)
    assert (row.cited, row.cited_correct) == (1, 0)


def test_an_unknown_marker_is_dropped_so_it_cannot_inflate_precision() -> None:
    row, _, _ = answer_one(setup(), question(), say("Được nghỉ [1] và [9]."), expand=True)
    assert row.cited == 1 and "[9]" not in row.answer


def test_the_models_own_refusal_is_kept_apart_from_the_gate() -> None:
    row, _, _ = answer_one(setup(), question(), say(NOT_FOUND + " Tài liệu không nêu."),
                           expand=True)
    assert row.outcome == "GENERATOR_NOT_FOUND" and row.cited == 0 and row.llm_calls == 1


def test_below_the_gate_nothing_is_generated() -> None:
    s = setup("dense", {"dense": 2.0})  # cosine never reaches 2
    generate = say("never called")
    row, sources, _ = answer_one(s, question(), generate, expand=True)
    assert row.outcome == "NO_EVIDENCE" and row.llm_calls == 0 and sources == []
    assert generate.calls == []  # type: ignore[attr-defined]
    assert retrieve(s, question()).passed is False


def test_summary_separates_gate_and_generator_refusals_by_answerability() -> None:
    qs = [question("a1"), question("a2"), question("u1", "thời tiết hôm nay", answerable=False)]
    replies = iter(["Được nghỉ [1].", NOT_FOUND, NOT_FOUND] * 2)  # in question order, twice

    report, per_q = answers_report(setup(), qs, lambda messages: next(replies), None, [])
    total = report["by_expand"]["on"]["all"]
    assert total["answerable"] == {"answered": 0.5, "false_refusal_gate": 0.0,
                                   "false_refusal_generator": 0.5}
    assert total["unanswerable"]["correct_refusal_generator"] == 1.0
    assert total["unanswerable"]["false_answer"] == 0.0
    assert total["citation_precision"] == 1.0 and len(per_q) == 6  # 3 questions x expand on/off


# -- faithfulness -------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ('{"verdict": "supported"}', "supported"),
    ('Here you go: {"verdict": "partial"} thanks', "partial"),
    ('{"verdict": "great"}', None), ("no json", None), ('{"verdict": ', None), ("[1, 2]", None),
])
def test_the_judge_reply_is_parsed_strictly(raw, expected) -> None:
    assert parse_verdict(raw) == expected


def test_the_subset_is_stable_whatever_the_order_and_changes_with_the_seed() -> None:
    ids = [f"q{i}" for i in range(40)]
    a = fixed_subset(ids, 10, "seed")
    assert a == fixed_subset(list(reversed(ids)), 10, "seed") and len(set(a)) == 10
    assert a != fixed_subset(ids, 10, "other-seed")


def test_only_the_subset_is_judged_and_flagged_numbers_are_compared() -> None:
    qs = [question("in"), question("out")]
    judged: list[str] = []

    def judge(messages):
        judged.append(messages[1]["content"])
        return '{"verdict": "partial"}'

    report, _ = answers_report(setup(), qs, say("Được nghỉ 99 ngày [1]."), judge, ["in"])
    total = report["by_expand"]["on"]["all"]
    assert len(judged) == 2 and total["judged"] == 1  # one question, expand on and off
    assert total["faithfulness"] == 0.5
    assert total["n_number_flagged"] == 1 and total["faithfulness_number_clean"] is None


def test_the_judge_sees_sources_and_is_told_to_ignore_its_own_knowledge() -> None:
    row, _, texts = answer_one(setup(), question(), say("Được nghỉ [1]."), expand=True)
    system, user = judge_messages("câu hỏi?", texts, row.answer)
    assert "never from your own knowledge" in system["content"]
    assert '<source n="1"' in user["content"] and "câu hỏi?" in user["content"]


# -- review fixes (milestone 4) -------------------------------------------------------------------

def test_token_counts_are_those_of_index_text_like_the_service_stores_them() -> None:
    titled = Chunk(doc="qt03.md", page=1, text="một hai", index_text="Tiêu đề dài | một hai",
                   char_start=0, char_end=7, page_end=1, lang="vi", kind="PROSE",
                   section_path=("1.",), doc_id="qt03")
    s = Setup([titled], Index([titled], HashEmbedder()), {"retriever": "bm25", "k": 1}, {},
              ContextConfig(), lambda t: len(t.split()), {})
    assert s.infos[0].token_count == len(["Tiêu", "đề", "dài", "|", "một", "hai"])  # not len("một hai")


def test_source_level_precision_accepts_a_cited_section_that_holds_the_gold_beyond_the_hit() -> None:
    # The hit is the rule chunk; the gold is the exception in the same (expanded) source.
    q = question("q3", sets=(("exception",),))
    row, _, _ = answer_one(setup(), q, say("Được nghỉ [1]."), expand=True)
    assert (row.cited, row.cited_correct, row.cited_correct_source) == (1, 0, 1)


def test_citations_on_unanswerable_questions_are_counted_apart_from_precision() -> None:
    qs = [question("a"), question("u", "nhân viên được nghỉ phép mười hai ngày", answerable=False)]
    report, _ = answers_report(setup(), qs, say("Được nghỉ [1]."), None, [])
    total = report["by_expand"]["on"]["all"]
    assert total["citations"] == 1 and total["citations_on_unanswerable"] == 1
    assert total["citation_precision"] == 1.0  # the unanswerable one is not pooled in


def test_a_judge_reply_that_does_not_parse_is_counted_not_dropped() -> None:
    report, _ = answers_report(setup(), [question("in")], say("Được nghỉ [1]."),
                               lambda m: "I cannot decide", ["in"])
    total = report["by_expand"]["on"]["all"]
    assert total["judged"] == 0 and total["judge_unparsed"] == 1 and total["faithfulness"] is None


def test_faithfulness_is_also_reported_on_the_questions_judged_in_both_modes() -> None:
    qs = [question("in")]
    report, _ = answers_report(setup(), qs, say("Được nghỉ [1]."),
                               lambda m: '{"verdict": "supported"}', ["in"])
    assert report["faithfulness_common"] == {"n": 1, "on": 1.0, "off": 1.0}


def test_coverage_says_how_many_questions_the_gate_lets_through() -> None:
    s = setup("dense", {"dense": 2.0})  # nothing passes
    report = coverage_report(s, [question()])
    assert report["gate_pass_rate"] == 0.0 and report["n_questions"] == 1  # coverage ignores it
