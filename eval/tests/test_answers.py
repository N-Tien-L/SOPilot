"""V2-10 mốc 4: answer-level harness (coverage, citation precision, refusals, faithfulness).

Retrieval is BM25 or dense over a hash embedder and the LLM is a function, so nothing here needs a
model download or an endpoint. The numbers of a real run come from ``sopilot_eval.answers``.
"""
from __future__ import annotations

import threading
import time

import pytest
from sopilot_ai.retrieval.context import ContextConfig

from sopilot_eval.answers import (
    Setup,
    answer_one,
    answers_report,
    correctness_messages,
    coverage_report,
    fixed_subset,
    judge_messages,
    parse_correctness,
    parse_verdict,
    relax_client_limits,
    retrieve,
    run_ordered,
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


# -- concurrency (V2-40, ADR-011 §2.2) ----------------------------------------------------------

def test_results_keep_the_input_order_when_calls_finish_in_another_order() -> None:
    finished: list[int] = []

    def slow_first(i: int) -> int:
        time.sleep((5 - i) * 0.02)  # the later the item, the sooner it finishes
        finished.append(i)
        return i * 10

    assert run_ordered(slow_first, list(range(6)), 6) == [0, 10, 20, 30, 40, 50]
    assert finished != sorted(finished)  # the completion order really was shuffled


def test_a_concurrent_run_writes_the_same_report_and_rows_as_a_sequential_one() -> None:
    qs = [question(f"q{i}") for i in range(3)]
    sequential, seq_rows = answers_report(setup(), qs, say("Được nghỉ [1]."), None, [])
    barrier = threading.Barrier(3, timeout=10)  # passes only if 3 requests are in flight together

    def together(messages):
        barrier.wait()
        return "Được nghỉ [1]."

    concurrent, con_rows = answers_report(setup(), qs, together, None, [], concurrency=3)
    assert [r["id"] for r in con_rows] == ["q0", "q1", "q2"] * 2  # expand on, then off
    assert con_rows == seq_rows
    assert {**concurrent, "concurrency": 1} == sequential and concurrent["concurrency"] == 3


def test_a_failure_stops_the_calls_that_have_not_started() -> None:
    started: list[int] = []

    def fail_on_first(i: int) -> int:
        started.append(i)
        time.sleep(0.05)
        if i == 0:
            raise RuntimeError("endpoint down")
        return i

    with pytest.raises(RuntimeError, match="endpoint down"):
        run_ordered(fail_on_first, list(range(50)), 2)
    assert len(started) < 50


def test_a_failure_late_in_the_list_stops_the_queue_while_an_earlier_call_is_still_running() -> None:
    started: list[int] = []

    def work(i: int) -> int:
        started.append(i)
        if i == 0:
            time.sleep(0.5)  # the head of the list is slow, the failure comes from item 1
            return 0
        if i == 1:
            raise RuntimeError("endpoint down")
        time.sleep(0.05)
        return i

    with pytest.raises(RuntimeError, match="endpoint down"):
        run_ordered(work, list(range(40)), 2)
    assert len(started) < 40


def test_a_concurrent_run_raises_the_client_limits_but_never_lowers_them() -> None:
    raw = {"llm": {"generate": {"timeout_s": 2000, "chain": [{"rpm": "60", "tpm": "200000"},
                                                              {"rpm": 9999, "tpm": 5}]}}}
    out = relax_client_limits(raw, "generate")["llm"]["generate"]
    assert out["timeout_s"] == 2000 and [e["rpm"] for e in out["chain"]] == [600, 9999]
    assert [e["tpm"] for e in out["chain"]] == [10_000_000, 10_000_000]
    assert raw["llm"]["generate"]["chain"][0]["rpm"] == "60"  # the input is not changed


def test_concurrency_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        run_ordered(lambda i: i, [1], 0)


# -- correctness against the reference answer and citation recall (V2-37 E) ------------------------

REFERENCE = "Nhân viên được nghỉ mười hai ngày mỗi năm, trừ nhân viên thử việc."


def graded_question(qid: str = "q1") -> dict:
    return {**question(qid), "reference_answer": REFERENCE}


@pytest.mark.parametrize("raw, expected", [
    ('{"correctness": "correct"}', "correct"),
    ('```json\n{"correctness": "partial"}\n```', "partial"),
    ('{"correctness": "Wrong"}', None),
    ('{"verdict": "supported"}', None),
    ("correct", None),
    ("", None),
])
def test_the_correctness_reply_is_parsed_strictly(raw, expected) -> None:
    assert parse_correctness(raw) == expected


def test_the_correctness_judge_sees_the_reference_and_is_told_to_ignore_wording() -> None:
    system, user = correctness_messages("câu hỏi?", REFERENCE, "Được nghỉ [1].")
    assert "wording" in system["content"] and "[1]" in system["content"]
    assert REFERENCE in user["content"] and "Được nghỉ [1]." in user["content"]


def test_correctness_is_graded_next_to_faithfulness_and_refusals_are_not_correct() -> None:
    qs = [graded_question("a"), graded_question("b")]
    asked: list[str] = []

    def judge(messages):
        asked.append(messages[0]["content"])
        return ('{"correctness": "correct"}' if "reference answer" in messages[0]["content"]
                else '{"verdict": "supported"}')

    report, rows = answers_report(setup(), qs, say("Được nghỉ mười hai ngày [1]."), judge, ["a"])
    total = report["by_expand"]["on"]["all"]
    assert total["correctness"] == 1.0 and total["correctness_judged"] == 1
    assert total["correct_end_to_end"] == 1.0  # only "a" is in the judged subset
    assert len(asked) == 4  # two calls per judged answer, expand on and off
    assert {r["id"]: r["in_judged_subset"] for r in rows if r["expand"]} == {"a": True, "b": False}

    refusing, _ = answers_report(setup(), qs, say(NOT_FOUND), judge, ["a"])
    off = refusing["by_expand"]["on"]["all"]
    assert off["correctness_judged"] == 0 and off["correct_end_to_end"] == 0.0


def test_a_correctness_reply_that_does_not_parse_is_counted_and_is_not_correct() -> None:
    def judge(messages):
        return "no idea" if "reference answer" in messages[0]["content"] else '{"verdict": "supported"}'

    report, _ = answers_report(setup(), [graded_question()], say("Được nghỉ [1]."), judge, ["q1"])
    total = report["by_expand"]["on"]["all"]
    assert total["correctness_unparsed"] == 1 and total["correctness_judged"] == 0
    assert total["correct_end_to_end"] == 0.0


def test_correctness_can_be_switched_off_and_needs_a_reference() -> None:
    calls: list[str] = []

    def judge(messages):
        calls.append(messages[0]["content"])
        return '{"verdict": "supported"}'

    report, _ = answers_report(setup(), [graded_question()], say("Được nghỉ [1]."), judge, ["q1"],
                               grade_correctness=False)
    assert len(calls) == 2 and report["by_expand"]["on"]["all"]["correctness_judged"] == 0
    calls.clear()
    no_reference = {**question(), "reference_answer": "  "}
    answers_report(setup(), [no_reference], say("Được nghỉ [1]."), judge, ["q1"])
    assert len(calls) == 2  # faithfulness only: nothing to compare with


def test_citation_recall_counts_the_gold_spans_that_a_cited_source_covers() -> None:
    # Gold needs both the rule and the exception; a hit on the rule alone cites only the rule.
    row, _, _ = answer_one(setup(), question(), say("Được nghỉ mười hai ngày [1]."), expand=False)
    assert row.cite_recall == 0.5 and row.cite_set_complete is False
    # With the section expanded the cited source holds both spans.
    row, _, _ = answer_one(setup(), question(), say("Được nghỉ mười hai ngày [1]."), expand=True)
    assert row.cite_recall == 1.0 and row.cite_set_complete is True


def test_citation_recall_takes_the_best_evidence_set_and_is_zero_without_citation() -> None:
    q = question(sets=(("buy",), ("rule",)))
    row, _, _ = answer_one(setup(), q, say("Được nghỉ mười hai ngày [1]."), expand=False)
    assert row.cite_recall == 1.0  # the second set is fully cited
    row, _, _ = answer_one(setup(), question(), say("Được nghỉ mười hai ngày."), expand=True)
    assert row.cite_recall == 0.0 and row.cited == 0


def test_summary_reports_citation_recall_over_answered_answerable_questions() -> None:
    qs = [question("a"), question("b", answerable=False)]
    report, _ = answers_report(setup(), qs, say("Được nghỉ mười hai ngày [1]."), None, [])
    total = report["by_expand"]["on"]["all"]
    assert total["citation_recall"] == 1.0 and total["citation_set_complete"] == 1.0
    assert total["correctness"] is None and total["correct_end_to_end"] is None


def test_dump_context_keeps_what_a_hand_grader_needs_and_is_off_by_default() -> None:
    q = graded_question()
    _, plain = answers_report(setup(), [q], say("Được nghỉ [1]."), None, [])
    assert all(r["context"] is None for r in plain)
    _, dumped = answers_report(setup(), [q], say("Được nghỉ [1]."), None, [], dump_context=True)
    ctx = dumped[0]["context"]
    assert ctx["question"] == q["question"] and ctx["reference_answer"] == REFERENCE
    assert ctx["sources"] and '<source n="1"' in ctx["sources"][0]


# -- judge context budget and judge failures ------------------------------------------------------

def _texts(n: int, size: int) -> list:
    from sopilot_ai.qa import prompt as qa_prompt

    return [qa_prompt.SourceText(n=i, text="x" * size, title=f"doc{i}", page=1) for i in range(1, n + 1)]


def test_the_judge_reads_the_cited_sources_first_and_the_cut_is_reported() -> None:
    from sopilot_eval.answers import judge_sources

    texts = _texts(4, 6000)
    rendered, cut = judge_sources(texts, "Câu trả lời [3].", max_chars=13000)
    assert cut is True and 'n="3"' in rendered[0] and len(rendered) == 2
    rendered, cut = judge_sources(_texts(2, 100), "Không trích dẫn.", max_chars=13000)
    assert cut is False and len(rendered) == 2


def test_a_single_oversized_source_is_cut_not_dropped() -> None:
    from sopilot_eval.answers import judge_sources

    rendered, cut = judge_sources(_texts(1, 50_000), "[1]", max_chars=16_000)
    assert cut is True and len(rendered) == 1 and len(rendered[0]) == 16_000


def test_a_failed_judge_call_is_counted_and_does_not_lose_the_run() -> None:
    from sopilot_ai.providers.llm import LLMError

    def judge(messages):
        raise LLMError("LLM_UNAVAILABLE")

    report, rows = answers_report(setup(), [graded_question()], say("Được nghỉ [1]."), judge, ["q1"])
    total = report["by_expand"]["on"]["all"]
    assert total["judge_errors"] == 1 and total["judge_unparsed"] == 0 and total["judged"] == 0
    assert rows[0]["judge_error"] == "LLM_UNAVAILABLE"
