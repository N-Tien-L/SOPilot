"""QueryFrame, number/date check, self-refusal detection, citation cleanup (V2-10, milestone 1)."""
from __future__ import annotations

from uuid import uuid4

import pytest

from sopilot_ai.qa import values
from sopilot_ai.qa.checks import check_numbers, is_generator_not_found
from sopilot_ai.qa.citations import build_citations, clean_markers
from sopilot_ai.qa.query_frame import build_query_frame, detect_lang
from sopilot_ai.retrieval.context import ChunkInfo, build_sources

# --- QueryFrame ------------------------------------------------------------------------------


@pytest.mark.parametrize("text, lang", [
    ("Quy trình xin nghỉ phép gồm những bước nào?", "vi"),
    ("quy trinh nghi phep la gi", "vi"),
    ("How many days of annual leave do I get?", "en"),
    ("QT-MH-01", "en"),
])
def test_language_is_detected_by_rule(text, lang):
    assert detect_lang(text) == lang


def test_request_language_overrides_detection():
    assert detect_lang("How many days of leave?", "vi") == "vi"
    assert detect_lang("Nghỉ phép mấy ngày?", "en") == "en"
    assert detect_lang("Nghỉ phép mấy ngày?", None) == "vi"


def test_frame_collects_codes_dates_amounts_and_tokens():
    f = build_query_frame("QT-MH-01 ngày 01/03/2026 đơn 50 triệu cần ai duyệt", lang=None)
    assert f.doc_codes == {"QT-MH-01"}
    assert f.dates == ("2026-03-01",)
    assert f.amounts == ("50000000",)
    assert f.lang == "vi"
    assert len(f.tokens) == 13


@pytest.mark.parametrize("text", [
    "So sánh quy trình mua hàng và quy trình thanh toán",
    "khác nhau giữa QT-MH-01 và QT-TT-02",
    "QT-MH-01 QT-TT-02 khác gì nhau",
    "Compare the leave and expense policies",
    "what is the difference between A and B",
    "đơn vs hợp đồng",
    "QT-MH-01 và QT-TT-02 áp dụng thế nào",   # two document codes alone
])
def test_comparison_signal_is_recorded(text):
    assert build_query_frame(text).comparison is True


def test_comparison_signal_is_not_set_for_a_plain_question():
    f = build_query_frame("Quy trình mua hàng gồm mấy bước", lang=None)
    assert f.comparison is False
    assert f.signals() == {"comparison": False, "followup": False}


@pytest.mark.parametrize("text, marker, short", [
    ("vậy còn đơn dưới 10 triệu thì sao", True, False),
    ("thế còn nhân viên thử việc", True, False),
    ("what about contractors", True, True),
    ("quy trình đó có bao nhiêu bước", True, False),
    ("ai duyệt", False, True),
    ("quy trình mua hàng gồm mấy bước", False, False),
    ("do đó anh ấy nghỉ", True, False),
])
def test_followup_signals(text, marker, short):
    f = build_query_frame(text, followup_max_tokens=4)
    assert (f.followup_marker, f.short) == (marker, short)


def test_known_terms_and_lexicon_make_tokens_meaningful():
    f = build_query_frame("asdf lương zzz quy trình", known_terms={"lương"})
    kept = {f.tokens[i].raw for i in f.meaningful}
    assert kept == {"lương", "quy", "trình"}
    assert f.meaningful_count(removed={f.tokens[1].index}) == 2


# --- values ----------------------------------------------------------------------------------


@pytest.mark.parametrize("a, b", [
    ("50 triệu", "50.000.000"),
    ("50tr", "50.000.000"),
    ("1,5 tỷ", "1.500.000.000"),
    ("500k", "500.000"),
])
def test_amounts_compare_by_value(a, b):
    left = values.extract(a)
    right = values.extract(b)
    assert left.amount_keys() & (right.number_keys() | right.amount_keys())


def test_dates_are_normalized_to_iso():
    got = values.extract("hiệu lực 01/03/2026, hết hạn ngày 5 tháng 4 năm 2027 và 2026-12-31")
    assert got.date_keys() == {"2026-03-01", "2027-04-05", "2026-12-31"}


def test_numbers_inside_dates_and_citation_markers_are_not_plain_numbers():
    got = values.extract("Từ 01/03/2026 trong 5 ngày [1] [2, 3]")
    assert [f.key for f in got.numbers] == ["5"]


# --- check_numbers --------------------------------------------------------------------------

SOURCE = ("Đơn dưới 50.000.000 đồng do trưởng phòng duyệt trong 2 ngày làm việc. "
          "Quy trình có hiệu lực từ 01/03/2026. Lãi suất 7,5%.")


def test_values_found_in_the_sources_raise_no_warning():
    answer = ("Đơn dưới 50 triệu do trưởng phòng duyệt trong 2 ngày [1]. "
              "Hiệu lực từ ngày 1 tháng 3 năm 2026. Lãi suất 7,5%.")
    assert check_numbers(answer, [SOURCE]).values == ()


def test_values_missing_from_the_sources_are_flagged_not_fixed():
    answer = "Duyệt trong 3 ngày, hiệu lực từ 15/04/2026, hạn mức 70 triệu."
    result = check_numbers(answer, [SOURCE])
    assert result.values == ("15/04/2026", "70 triệu", "3")
    assert result.warnings() == [{"code": "NUMBER_NOT_IN_SOURCES",
                                  "values": ["15/04/2026", "70 triệu", "3"]}]
    assert result.to_checks() == ["15/04/2026", "70 triệu", "3"]


def test_citation_markers_and_list_numbers_are_not_checked():
    answer = "1. Lập đề nghị [1]\n2. Trưởng phòng duyệt [2]"
    assert check_numbers(answer, [SOURCE]).values == ()


def test_a_value_in_the_prompt_attributes_counts_as_held():
    texts = [SOURCE, '<source code="QT-MH-01" rev="03" effective="2026-03-01">']
    assert check_numbers("Mã QT-MH-01, lần ban hành 03.", texts).values == ()


def test_a_date_without_a_year_matches_any_year_of_the_source():
    assert check_numbers("Hiệu lực từ 1 tháng 3.", [SOURCE]).values == ()


def test_numbers_the_user_wrote_count_as_held_when_the_caller_passes_the_question():
    question = "Đơn 80 triệu trưởng phòng duyệt trong bao lâu?"
    answer = "Với đơn 80 triệu, trưởng phòng duyệt trong 2 ngày [1]."
    assert check_numbers(answer, [SOURCE]).values == ("80 triệu",)
    assert check_numbers(answer, [SOURCE, question]).values == ()


def test_an_answer_without_numbers_has_nothing_to_flag():
    assert check_numbers("Trưởng phòng duyệt đơn.", []).warned is False


# --- is_generator_not_found --------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "Không tìm thấy thông tin này trong các tài liệu hiện có.",
    "  không tìm thấy thông tin này trong các tài liệu hiện có",
    "**Không tìm thấy thông tin này trong các tài liệu hiện có.** Bạn thử hỏi lại.",
    "> Không tìm thấy thông tin này trong các tài liệu hiện có. Tài liệu gần nhất là...",
    "I could not find this in the available documents.",
    "i could not find this in the available documents. See ...",
    '"I could not find this in the available documents"',
    "KHÔNG  TÌM  THẤY thông tin này trong các tài liệu hiện có.",
])
def test_the_fixed_opening_is_recognised_in_both_languages(text):
    assert is_generator_not_found(text) is True


@pytest.mark.parametrize("text", [
    "Theo quy trình, đơn do trưởng phòng duyệt [1].",
    "Tài liệu nói rằng không tìm thấy thông tin này trong các tài liệu hiện có.",
    "Có. Không tìm thấy thông tin này trong các tài liệu hiện có.",
    "",
])
def test_normal_answers_are_not_self_refusals(text):
    assert is_generator_not_found(text) is False


# --- clean_markers / build_citations ---------------------------------------------------------


def test_markers_without_a_source_are_removed():
    text, used = clean_markers("Duyệt trong 2 ngày [1]. Gửi hồ sơ [4] cho phòng [2].", {1, 2})
    assert text == "Duyệt trong 2 ngày [1]. Gửi hồ sơ cho phòng [2]."
    assert used == [1, 2]


def test_grouped_markers_keep_only_their_valid_numbers():
    text, used = clean_markers("Hai điều kiện [1, 3] và [2;9].", {1, 2})
    assert text == "Hai điều kiện [1] và [2]."
    assert used == [1, 2]


def test_text_with_no_markers_is_untouched():
    text = "Không có trích dẫn. a [x] b."
    assert clean_markers(text, {1}) == (text, [])


def _chunk(ordinal, *, doc, ver, section=("5", "5.1"), kind="PROSE", tokens=100, page=1):
    return ChunkInfo(uuid4(), doc, ver, ordinal, kind, section, page, ordinal * 1000,
                     ordinal * 1000 + 500, f"nội dung {ordinal}", tokens)


def test_each_valid_marker_maps_to_document_page_and_snippet():
    doc, ver = uuid4(), uuid4()
    hit = _chunk(2, doc=doc, ver=ver, kind="PROCEDURE_STEP", page=3)
    sources = build_sources([hit], {(ver, hit.section_path): [_chunk(1, doc=doc, ver=ver), hit]})
    cites = build_citations(sources, [1, 7])
    assert len(cites) == 1  # 7 has no source
    c = cites[0]
    assert (c.n, c.chunk_id, c.document_id, c.version_id) == (1, hit.chunk_id, doc, ver)
    assert (c.char_start, c.char_end) == (2000, 2500)
    assert c.snippet == "nội dung 2"
    assert c.page_start == 3  # the page of the hit, not of the lead paragraph on page 1
