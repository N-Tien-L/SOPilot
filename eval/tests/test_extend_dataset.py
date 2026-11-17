"""sop-main-v2 builder: base questions kept, new drafts added, base freeze recorded, reviews protected."""
import json

import pytest
from test_dataset_freeze import _write_jsonl, dataset  # noqa: F401  (fixture)

from sopilot_eval.analyze_v2_07 import _ci, paired
from sopilot_eval.dataset import freeze, read_jsonl, validate_retrieval
from sopilot_eval.extend_dataset import build, lexical_overlap

SEED = [
    {"id": "v2-retain", "split": "test", "family": "fam-new", "corpus_lang": "en",
     "query_types": ["number_deadline"], "tags": ["no_doc_name"],
     "questions": [{"lang": "en", "question": "How long are records kept?", "answer": "Five years."},
                   {"lang": "vi", "question": "Hồ sơ giữ bao lâu theo SOP 12?", "answer": "5 năm."}],
     "evidence": [[{"doc": "d1", "quote": "Retain records for five years."}]]},
    {"id": "v2-neg", "split": "test", "family": "fam-neg", "corpus_lang": "vi", "query_types": ["fact"],
     "tags": ["near_miss"], "negative_reason": "not in corpus", "search_terms": ["phí"],
     "questions": [{"lang": "vi", "question": "Phí lưu hồ sơ là bao nhiêu?"}]},
]


@pytest.fixture
def base_and_target(dataset, tmp_path_factory):  # noqa: F811
    (dataset / "page-map.json").write_text("{}", encoding="utf-8")
    _write_jsonl(dataset / "negative-audit.draft.jsonl", [])
    freeze(dataset, "owner", "2026-11-04T00:00:00+00:00")
    target = tmp_path_factory.mktemp("v2")
    (target / "seed").mkdir()
    (target / "seed" / "01.json").write_text(json.dumps(SEED, ensure_ascii=False), encoding="utf-8")
    return dataset, target


def test_build_adds_drafts_and_keeps_base_untouched(base_and_target):
    # Arrange
    base, target = base_and_target
    before = (base / "questions.master.jsonl").read_bytes()
    # Act
    result = build(base, target)
    # Assert
    assert (base / "questions.master.jsonl").read_bytes() == before
    validate_retrieval(base, require_reviewed=True)
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is False and manifest["derived_from"]["test_sha256"]
    rows = {q["id"]: q for q in read_jsonl(target / "questions.master.jsonl")}
    assert rows["test1"]["subset"] == "v1" and rows["test1"]["review_status"] == "reviewed"
    vi = rows["v2-retain-vi"]
    assert vi["review_status"] == "draft" and vi["cross_lingual"] and "names_doc_code" in vi["tags"]
    assert not rows["v2-neg-vi"]["answerable"] and result["new_questions"] == 3


def test_build_refuses_after_owner_review(base_and_target):
    base, target = base_and_target
    build(base, target)
    rows = read_jsonl(target / "questions.master.jsonl")
    _write_jsonl(target / "questions.master.jsonl",
                 [r | {"review_status": "reviewed"} if r["id"] == "v2-retain-en" else r for r in rows])
    with pytest.raises(SystemExit, match="already reviewed"):
        build(base, target)


def test_lexical_overlap_folds_diacritics():
    assert lexical_overlap("Thời hạn lưu tài liệu?", ["thoi han luu la 3 nam"]) == pytest.approx(0.6)
    assert lexical_overlap("ai?", ["x"]) == 0.0


def test_cluster_bootstrap_is_wider_for_correlated_twins():
    values = [1.0, 1.0, 0.0, 0.0] * 3
    clusters = ["a", "a", "b", "b", "c", "c", "d", "d", "e", "e", "f", "f"]
    _, lo_q, hi_q = _ci(values)
    _, lo_c, hi_c = _ci(values, clusters)
    assert hi_c - lo_c > hi_q - lo_q


def test_paired_counts_wins_and_losses():
    a = [{"id": i, "answerable": True, "cross_lingual": False, "lang": "vi", "query_types": [], "m": v}
         for i, v in (("q1", 1.0), ("q2", 0.0), ("q3", 1.0))]
    b = [r | {"m": 0.5} for r in a]
    res = paired(a, b, "m")
    assert (res["better"], res["worse"], res["n"]) == (2, 1, 3)


# --- V2-45: added documents (sop-main-v3) ---

GL_TEXT = "# Expenses\n\nReceipts must be submitted within 30 days of purchase.\n\nPhí lưu hồ sơ không được nêu.\n"


def _extra_dir(tmp_path, version="cv2", doc_id="gl-exp"):
    from sopilot_eval.dataset import sha256

    extra = tmp_path / "extra"
    (extra / "corpus").mkdir(parents=True)
    (extra / "corpus" / f"{doc_id}.md").write_bytes(GL_TEXT.encode("utf-8"))
    manifest = {"corpus_version": version, "normalization_version": "n1", "models": {"translate": "haiku"},
                "documents": [{"doc_id": doc_id, "path": f"corpus/{doc_id}.md", "lang": "en",
                               "sha256": sha256(GL_TEXT), "source": "https://example.test/gl", "license": "CC BY-SA 4.0"}]}
    (extra / "manifest.extra.json").write_text(json.dumps(manifest), encoding="utf-8")
    (extra / "page-map.extra.json").write_text("{}", encoding="utf-8")
    return extra


V3_SEED = [
    {"id": "v3-receipts", "split": "test", "family": "gl-expenses", "corpus_lang": "en",
     "query_types": ["number_deadline"], "tags": ["no_doc_name"],
     "questions": [{"lang": "en", "question": "How soon must receipts be filed?", "answer": "Within 30 days."},
                   {"lang": "vi", "question": "Biên lai phải nộp trong bao lâu?", "answer": "Trong 30 ngày."}],
     "evidence": [[{"doc": "gl-exp", "quote": "Receipts must be submitted within 30 days of purchase."}]]},
]


def test_extra_corpus_adds_docs_rebases_reviews_and_marks_v3(base_and_target, tmp_path):
    # Arrange
    base, target = base_and_target
    (target / "seed" / "01.json").write_text(json.dumps(V3_SEED, ensure_ascii=False), encoding="utf-8")
    extra = _extra_dir(tmp_path)
    # Act
    result = build(base, target, extra=extra)
    # Assert
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["corpus_version"] == "cv2" and manifest["derived_from"]["dataset"] == base.name
    assert {d["doc_id"] for d in manifest["documents"]} == {"d1", "gl-exp"}
    rows = {q["id"]: q for q in read_jsonl(target / "questions.master.jsonl")}
    assert rows["v3-receipts-vi"]["subset"] == "v3" and rows["v3-receipts-vi"]["cross_lingual"]
    assert rows["test1"]["subset"] == "v1"
    reviews = read_jsonl(target / "review.jsonl")
    assert reviews and all(r["corpus_version"] == "cv2" and r["rebased_from"]["corpus_version"] == "cv1"
                           for r in reviews)
    assert result["new_questions"] == 2


def test_extra_corpus_finds_old_negative_that_new_pages_may_answer(base_and_target, tmp_path):
    # Arrange: a base near-miss negative whose search term "phí" now appears in an added page
    base, target = base_and_target
    rows = read_jsonl(base / "questions.master.jsonl")
    neg = rows[0] | {"id": "oldneg-vi", "intent_id": "oldneg", "answerable": False, "evidence_sets": [],
                     "expected": [], "reference_answer": ""}
    _write_jsonl(base / "questions.master.jsonl", [*rows, neg])
    _write_jsonl(base / "review.jsonl", [*read_jsonl(base / "review.jsonl"),
                                         {"question_id": "oldneg-vi", "decision": "reviewed", "reviewer_id": "o",
                                          "reviewed_at": "2026-11-04", "label_version": "v1", "corpus_version": "cv1",
                                          "unanswerable_audit": {"reason": "r", "search_terms": ["phí"],
                                                                 "candidate_sections": {}, "conclusion": "c"}}])
    (target / "seed" / "01.json").write_text("[]", encoding="utf-8")
    # Act
    result = build(base, target, force=True, extra=_extra_dir(tmp_path))
    # Assert
    recheck = json.loads((target / "negative-recheck.json").read_text(encoding="utf-8"))
    assert result["negative_recheck_hits"] == 1
    assert recheck["with_hits"][0]["question_id"] == "oldneg-vi"
    assert recheck["with_hits"][0]["hits"] == {"gl-exp": {"phí": 1}}


def test_extra_corpus_rejects_same_version_and_duplicate_doc(base_and_target, tmp_path):
    base, target = base_and_target
    (target / "seed" / "01.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="new corpus_version"):
        build(base, target, extra=_extra_dir(tmp_path, version="cv1"))
    with pytest.raises(ValueError, match="already in the base corpus"):
        build(base, target, extra=_extra_dir(tmp_path / "again", doc_id="d1"))
