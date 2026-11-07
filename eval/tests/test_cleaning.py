from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sopilot_eval.cleaning import contains, evaluate_cleaning, flat, score_cleaning

GOLD = {
    "doc_id": "a",
    "headings": [{"text": "1. Mục đích", "level": 1, "page": 2},
                 {"text": "2. Phạm vi", "level": 1, "page": 2},
                 {"text": "3. Không trích được", "level": 1, "page": 3}],
    "tables": [{"page": 2, "rows": 1, "cols": 2, "column_titles": ["TT", "Trách nhiệm"],
                "cell_spans": []}],
    "furniture": [{"page": 2, "text": "SỞ XÂY DỰNG"}, {"page": 2, "text": "Mã hiệu: QT-01"},
                  {"page": 2, "text": "2/9"}],
    "metadata": {},
}

RAW_PAGE = ("| SỞ XÂY DỰNG | Mã hiệu: QT-01 |\n| --- | --- |\n\n# 1. Mục đích\n\n"
            "Nội dung.\n\n# 2. Phạm vi\n\n| TT | Trách nhiệm |\n| --- | --- |\n| 1 | A |\n\n2/9")


def _pred(page2: str, boilerplate=None) -> dict:
    row = {"doc_id": "a", "headings": [], "tables": [], "metadata": {},
           "canonical_markdown": page2, "page_markdown": {"2": page2, "3": ""}}
    if boilerplate is not None:
        row["boilerplate"] = boilerplate
    return row


def test_flat_drops_markdown_table_and_heading_syntax():
    assert flat("# 1. Mục Đích\n| A | B \\| C |\n| --- | --- |") == "1. mục đích a b c"


def test_contains_needs_a_word_boundary():
    assert contains("tt trách nhiệm", "tt")
    assert not contains("trách nhiệm mattt", "tt")
    assert not contains("12/9 trang", "2/9")
    assert not contains("anything", "")


def test_clean_output_without_frame_and_with_body_scores_zero_leak_and_zero_deletion():
    clean_page = RAW_PAGE.replace("| SỞ XÂY DỰNG | Mã hiệu: QT-01 |\n| --- | --- |\n\n", "")
    clean_page = clean_page.replace("\n\n2/9", "")
    score = score_cleaning(GOLD, _pred(RAW_PAGE), _pred(clean_page, [
        {"kind": "header", "page": 2, "text": "SỞ XÂY DỰNG | Mã hiệu: QT-01"},
        {"kind": "footer", "page": 2, "text": "2/9"}]))
    assert score["furniture_gold"] == 3
    assert score["furniture_present_raw"] == 3
    assert score["furniture_leaked"] == 0
    assert score["furniture_removed"] == 3
    # heading 3 sits on a page the extractor returned empty: a miss, not a deletion
    assert score["content_units_missing_raw"] == 1
    assert score["content_units_present_raw"] == 4
    assert score["content_deleted"] == 0
    assert score["removed_blocks_confirmed"] == 2
    assert score["removed_blocks_unconfirmed"] == 0


def test_removed_heading_and_kept_frame_are_listed_as_cases():
    clean_page = RAW_PAGE.replace("# 2. Phạm vi\n\n", "")
    score = score_cleaning(GOLD, _pred(RAW_PAGE), _pred(clean_page, [
        {"kind": "signature", "page": 2, "text": "2. Phạm vi"}]))
    assert score["furniture_leaked"] == 3
    assert [c["text"] for c in score["deleted_cases"]] == ["2. Phạm vi"]
    assert score["content_deleted"] == 1
    assert score["unconfirmed_removals"] == [
        {"kind": "signature", "page": 2, "chars": 10, "text": "2. Phạm vi"}]


def test_frame_on_another_page_does_not_count_for_this_page():
    gold = {**GOLD, "furniture": [{"page": 3, "text": "SỞ XÂY DỰNG"}]}
    score = score_cleaning(gold, _pred(RAW_PAGE), _pred(RAW_PAGE, []))
    assert score["furniture_present_raw"] == 0 and score["furniture_leaked"] == 0
    assert score["furniture_leaked_whole_doc"] == 1  # the existing whole-document check


def test_markdown_without_pages_uses_the_whole_file():
    gold = {**GOLD, "headings": [{"text": "Intro", "level": 1, "page": None}], "tables": [],
            "furniture": [{"page": None, "text": "weight:"}]}
    raw = {"doc_id": "a", "headings": [], "tables": [], "metadata": {},
           "canonical_markdown": "weight: 10\n\n# Intro", "page_markdown": {}}
    clean = {**raw, "canonical_markdown": "# Intro", "boilerplate": []}
    score = score_cleaning(gold, raw, clean)
    assert score["furniture_present_raw"] == 1 and score["furniture_leaked"] == 0
    assert score["content_deleted"] == 0 and score["content_units_present_raw"] == 1


def test_evaluate_groups_by_family_and_language_and_skips_rejection_fixtures(tmp_path: Path):
    root = tmp_path / "ds"
    (root / "c").mkdir(parents=True)
    docs = []
    for doc_id in ("a", "scan"):
        pdf = root / "c" / f"{doc_id}.pdf"
        pdf.write_bytes(b"%PDF " + doc_id.encode())
        docs.append({"doc_id": doc_id, "path": f"c/{doc_id}.pdf", "lang": "vi",
                     "family": "iso_9001", "source": "s", "license": "l",
                     "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()})
    (root / "manifest.json").write_text(json.dumps({"corpus_version": "t", "documents": docs}),
                                        encoding="utf-8")
    common = {"cross_references": [], "review_status": "reviewed"}
    rows = [{**GOLD, **common},
            {"doc_id": "scan", "headings": [], "tables": [], "furniture": [], "metadata": {},
             "expected_outcome": "FAILED", **common}]
    (root / "annotations.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    raw_path, clean_path = tmp_path / "raw.jsonl", tmp_path / "clean.jsonl"
    raw_path.write_text(json.dumps(_pred(RAW_PAGE), ensure_ascii=False) + "\n", encoding="utf-8")
    clean_path.write_text(json.dumps(_pred(RAW_PAGE, []), ensure_ascii=False) + "\n",
                          encoding="utf-8")
    result = evaluate_cleaning(root, raw_path, clean_path)
    assert result["excluded"] == {"scan": "rejection fixture"}
    group = result["by_family_language"]["family=iso_9001;lang=vi"]
    assert group["documents"] == 1
    assert group["furniture_leakage_rate"] == 1.0
    assert group["content_deletion_rate"] == 0.0
    assert result["by_family_language"]["lang=vi"]["furniture_gold"] == 3
    assert len(result["cases"]["leaked"]) == 3
