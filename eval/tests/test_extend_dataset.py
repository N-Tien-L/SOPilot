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
