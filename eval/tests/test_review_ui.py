from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "review_ui"))

from apply_review import REVIEWED_VERSION, apply  # noqa: E402

DRAFT = {
    "doc_id": "d1", "annotation_scope": "selected_pages", "annotated_pages": [4],
    "headings": [{"text": "A", "level": 1, "page": 4}, {"text": "B", "level": 2, "page": 4}],
    "tables": [{"page": 4, "rows": 2, "cols": 3, "column_titles": ["x"], "cell_spans": []}],
    "furniture": [{"page": 4, "text": "HEADER"}],
    "metadata": {"doc_code": "QT-01"}, "cross_references": [],
    "review_status": "draft", "label_version": "pilot-draft-v1", "drafted_by": "Codex",
}
OTHER = {**DRAFT, "doc_id": "d2"}


def _review(**over):
    doc = {
        "finished": True, "notes": "checked p4", "metadata_decision": "ok",
        "metadata": {"doc_code": "QT-01"}, "cross_references": [],
        "headings": [{"text": "A", "level": 1, "page": 4, "decision": "ok", "added": False},
                     {"text": "B", "level": 2, "page": 4, "decision": "reject", "added": False},
                     {"text": "C", "level": 2, "page": 4, "decision": "edit", "added": True}],
        "tables": [{"page": 4, "rows": 2, "cols": 3, "column_titles": ["x"], "cell_spans": [],
                    "decision": "ok"}],
        "furniture": [{"page": 4, "text": "HEADER", "decision": "ok"}],
    }
    doc.update(over)
    return {"reviewer_id": "owner", "exported_at": "2026-10-26T01:00:00Z", "docs": {"d1": doc}}


def test_finished_doc_drops_rejected_keeps_edits_and_records_reviewer():
    merged, done = apply(_review(), [DRAFT, OTHER])
    assert done == ["d1"]
    d1 = merged[0]
    assert [h["text"] for h in d1["headings"]] == ["A", "C"]
    assert all("decision" not in h and "added" not in h for h in d1["headings"])
    assert d1["review_status"] == "reviewed" and d1["reviewer_id"] == "owner"
    assert d1["reviewed_at"] == "2026-10-26T01:00:00Z"
    assert d1["label_version"] == REVIEWED_VERSION and d1["review_notes"] == "checked p4"


def test_unfinished_and_unlisted_docs_stay_draft():
    merged, done = apply(_review(finished=False), [DRAFT, OTHER])
    assert done == [] and merged == [DRAFT, OTHER]
    assert merged[1]["review_status"] == "draft"


def test_rejected_metadata_is_emptied():
    merged, _ = apply(_review(metadata_decision="reject"), [DRAFT])
    assert merged[0]["metadata"] == {}


def test_inputs_are_not_mutated():
    before = dict(DRAFT)
    apply(_review(), [DRAFT])
    assert DRAFT == before
