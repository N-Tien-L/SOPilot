"""V2-45 helpers: handbook source records and the negative recheck."""
import json

import pytest

from sopilot_eval.extra_corpus import (
    handbook_source_record,
    rebase_reviews,
    recheck_negatives,
)


def _root(tmp_path, entries):
    (tmp_path / "acquisition" / "raw").mkdir(parents=True)
    (tmp_path / "acquisition" / "translated").mkdir()
    (tmp_path / "acquisition" / "sources.json").write_text(json.dumps({"documents": entries}), encoding="utf-8")
    return tmp_path


def test_english_page_is_read_from_raw_and_vietnamese_from_translated(tmp_path):
    # Arrange
    root = _root(tmp_path, [
        {"doc_id": "gl-a", "lang": "en", "url": "u1", "commit": "c", "license": "CC BY-SA 4.0", "section": "finance"},
        {"doc_id": "gl-b", "lang": "vi", "url": "u2", "commit": "c", "license": "CC BY-SA 4.0",
         "translated_from": {"url": "u2", "sha256": "x", "model": "haiku"}}])
    (root / "acquisition" / "raw" / "gl-a.md").write_text("a", encoding="utf-8")
    (root / "acquisition" / "translated" / "gl-b.md").write_text("b", encoding="utf-8")
    # Act
    path_a, meta_a = handbook_source_record(root, "gl-a")
    path_b, meta_b = handbook_source_record(root, "gl-b")
    # Assert
    assert path_a.parent.name == "raw" and meta_a["family"] == "finance" and "translated_from" not in meta_a
    assert path_b.parent.name == "translated" and meta_b["translated_from"]["model"] == "haiku"


def test_vietnamese_page_without_translation_record_is_rejected(tmp_path):
    root = _root(tmp_path, [{"doc_id": "gl-c", "lang": "vi", "url": "u", "commit": "c", "license": "l"}])
    with pytest.raises(ValueError, match="translated_from"):
        handbook_source_record(root, "gl-c")


def test_recheck_counts_terms_in_new_documents_only_and_flags_questions_without_terms():
    result = recheck_negatives({"q1": ["30 ngày"], "q2": ["xyz"], "q3": []}, {"n1": "Hạn là 30 NGÀY.", "n2": "khác"})
    assert [h["question_id"] for h in result["with_hits"]] == ["q1"]
    assert result["with_hits"][0]["hits"] == {"n1": {"30 ngày": 1}}
    assert result["without_search_terms"] == ["q3"]


def test_rebase_keeps_history_and_drops_excluded_questions():
    reviews = [{"question_id": "a", "corpus_version": "v1"},
               {"question_id": "b", "corpus_version": "v1", "rebased_from": {"corpus_version": "v0"}},
               {"question_id": "c", "corpus_version": "v1"}]
    out = rebase_reviews(reviews, "v1", "v2", "2026-11-17", excluded={"c"})
    assert [r["question_id"] for r in out] == ["a", "b"]
    assert out[1]["rebased_from_prev"]["corpus_version"] == "v0" and out[1]["rebased_from"]["corpus_version"] == "v1"
    assert all(r["corpus_version"] == "v2" for r in out)
