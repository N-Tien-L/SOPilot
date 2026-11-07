from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sopilot_eval.extraction import evaluate, evaluate_selected_pages


def _dataset(tmp_path: Path, *, status: str = "reviewed", scope: str = "selected_pages") -> Path:
    root = tmp_path / "ds"
    (root / "corpus").mkdir(parents=True)
    pdf = root / "corpus" / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    (root / "manifest.json").write_text(json.dumps({
        "corpus_version": "t",
        "documents": [{"doc_id": "a", "path": "corpus/a.pdf", "lang": "vi", "family": "f",
                       "source": "s", "license": "l",
                       "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}]}), encoding="utf-8")
    gold = {"doc_id": "a", "annotation_scope": scope, "annotated_pages": [2],
            "headings": [{"text": "1. Mục đích", "level": 1, "page": 2}],
            "tables": [{"page": 2, "rows": 2, "cols": 2, "column_titles": ["A", "B"],
                        "cell_spans": [{"row": 0, "col": 0, "rowspan": 1, "colspan": 2}]}],
            "furniture": [{"page": 2, "text": "CÔNG TY"}], "metadata": {"doc_code": "X"},
            "cross_references": [], "review_status": status}
    if status == "reviewed":
        gold.update(reviewer_id="r", reviewed_at="2026-10-26", label_version="v1")
    (root / "annotations.jsonl").write_text(json.dumps(gold, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    return root


def _predictions(root: Path, **over) -> Path:
    row = {"doc_id": "a",
           "headings": [{"text": "1. Mục đích", "level": 1, "page": 2},
                        {"text": "Unlabelled page", "level": 1, "page": 5}],
           "tables": [{"page": 2, "rows": 2, "cols": 2, "column_titles": ["A", "B"],
                       "cell_spans": [{"row": 0, "col": 0, "rowspan": 1, "colspan": 2}]},
                      {"page": 7, "rows": 9, "cols": 3, "column_titles": [], "cell_spans": []}],
           "metadata": {}, "canonical_markdown": "", "page_markdown": {"2": "body CÔNG TY text"}}
    row.update(over)
    path = root / "pred.jsonl"
    path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def test_predictions_outside_labelled_pages_are_ignored(tmp_path):
    root = _dataset(tmp_path)
    result = evaluate_selected_pages(root, _predictions(root))
    group = result["by_family_language"]["family=f;lang=vi"]
    assert group["headings_precision"] == 1.0 and group["headings_recall"] == 1.0
    assert group["tables_precision"] == 1.0 and group["merged_cells_recall"] == 1.0
    assert result["by_document"]["a"]["furniture_leaked"] == 1  # header text leaked into page 2
    assert "metadata_accuracy" not in result["by_document"]["a"]


def test_wrong_level_is_a_miss_not_a_pass(tmp_path):
    root = _dataset(tmp_path)
    bad = [{"text": "1. Mục đích", "level": 2, "page": 2}]
    result = evaluate_selected_pages(root, _predictions(root, headings=bad))
    assert result["by_family_language"]["family=f;lang=vi"]["headings_recall"] == 0.0


def test_unreviewed_labels_are_excluded_and_strict_evaluate_still_refuses_partial(tmp_path):
    root = _dataset(tmp_path, status="draft")
    result = evaluate_selected_pages(root, _predictions(root))
    assert result["scored"] == [] and result["excluded"] == {"a": "labels not reviewed"}
    root2 = _dataset(tmp_path / "x")
    with pytest.raises(ValueError, match="partial extraction"):
        evaluate(root2, _predictions(root2))


def test_scored_document_without_prediction_fails_loudly(tmp_path):
    root = _dataset(tmp_path)
    empty = root / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="predictions missing"):
        evaluate_selected_pages(root, empty)
