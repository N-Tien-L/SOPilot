import json

import pytest

from sopilot_eval.dataset import fingerprint_test_split, freeze, sha256, validate_retrieval

TEXT = "Quy trình A. Thời hạn lưu là 3 năm.\nProcedure B. Retain records for five years.\n"


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _span(sid, quote):
    start = TEXT.index(quote)
    return {
        "span_id": sid,
        "doc_id": "d1",
        "section_id": "s",
        "start_char": start,
        "end_char": start + len(quote),
        "quote": quote,
        "quote_sha": sha256(quote),
    }


def _question(qid, split, span, answer):
    return {
        "id": qid,
        "intent_id": qid,
        "policy_family_id": qid,
        "leakage_group_id": qid,
        "split": split,
        "question": f"question {qid}?",
        "lang": "vi",
        "corpus_lang": "vi",
        "cross_lingual": False,
        "answerable": True,
        "evidence_sets": [[span]],
        "reference_answer": answer,
        "query_types": ["fact"],
        "review_status": "reviewed",
        "label_version": "v1",
    }


@pytest.fixture
def dataset(tmp_path):
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "d1.md").write_bytes(TEXT.encode("utf-8"))
    manifest = {
        "corpus_version": "cv1",
        "normalization_version": "n1",
        "docproc": {"commit": "abc", "docproc_dirty": False},
        "frozen": False,
        "documents": [
            {"doc_id": "d1", "path": "corpus/d1.md", "lang": "vi", "sha256": sha256(TEXT),
             "source": "x", "license": "y"}
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_jsonl(tmp_path / "evidence.jsonl", [_span("a", "Thời hạn lưu là 3 năm."),
                                               _span("b", "Retain records for five years.")])
    _write_jsonl(tmp_path / "questions.master.jsonl",
                 [_question("dev1", "dev", "a", "3 năm"), _question("test1", "test", "b", "five years")])
    _write_jsonl(tmp_path / "review.jsonl", [
        {"question_id": qid, "decision": "reviewed", "reviewer_id": "owner", "reviewed_at": "t",
         "notes": "ok", "label_version": "v1", "corpus_version": "cv1"} for qid in ("dev1", "test1")
    ])
    return tmp_path


def _edit(path, fn):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    _write_jsonl(path, [fn(r) for r in rows])


def test_freeze_records_hash_and_validates(dataset):
    result = freeze(dataset, "owner", "2026-11-04T00:00:00+00:00")
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["frozen"] is True and result["frozen"] is True
    assert manifest["test_sha256"] == result["test_sha256"]
    assert manifest["frozen_docproc_commit"] == "abc" and manifest["frozen_corpus_version"] == "cv1"
    with pytest.raises(ValueError, match="already frozen"):
        freeze(dataset, "owner", "later")


def test_fingerprint_ignores_dev_and_review_metadata(dataset):
    freeze(dataset, "owner", "t")
    _edit(dataset / "questions.master.jsonl",
          lambda q: q | {"question": "changed dev?"} if q["split"] == "dev" else q | {"drafted_by": "x"})
    assert validate_retrieval(dataset)["frozen"] is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda q: q | {"reference_answer": "six years"} if q["id"] == "test1" else q,
        lambda q: q | {"question": "other?"} if q["id"] == "test1" else q,
        lambda q: q | {"split": "test", "policy_family_id": "test1", "leakage_group_id": "test1",
                       "intent_id": "test1"} if q["id"] == "dev1" else q,
    ],
)
def test_changed_test_split_fails(dataset, mutate):
    freeze(dataset, "owner", "t")
    _edit(dataset / "questions.master.jsonl", mutate)
    with pytest.raises(ValueError, match="frozen test split|dev/test leakage"):
        validate_retrieval(dataset)


def test_dev_question_moved_to_test_changes_hash(dataset):
    freeze(dataset, "owner", "t")
    _edit(dataset / "questions.master.jsonl", lambda q: q | {"split": "test"})
    with pytest.raises(ValueError, match="test_sha256"):
        validate_retrieval(dataset)


def test_unreviewed_test_question_fails_even_without_require_reviewed(dataset):
    freeze(dataset, "owner", "t")
    _edit(dataset / "questions.master.jsonl",
          lambda q: q | {"review_status": "draft"} if q["id"] == "test1" else q)
    with pytest.raises(ValueError, match="not reviewed"):
        validate_retrieval(dataset)


def test_rebuilt_canonical_from_other_commit_fails(dataset):
    freeze(dataset, "owner", "t")
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest["docproc"]["commit"] = "def"
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="docproc commit"):
        validate_retrieval(dataset)


def test_freeze_refuses_dirty_docproc(dataset):
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest["docproc"]["docproc_dirty"] = True
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="uncommitted"):
        freeze(dataset, "owner", "t")


def test_fingerprint_is_order_independent():
    spans = {"b": _span("b", "Retain records for five years.")}
    q = _question("t1", "test", "b", "five years")
    q2 = _question("t2", "test", "b", "five years")
    assert fingerprint_test_split([q, q2], spans) == fingerprint_test_split([q2, q], spans)
