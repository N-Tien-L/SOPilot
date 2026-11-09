import json
import shutil
from pathlib import Path

import pytest
from sopilot_eval.dataset import project_expected, read_jsonl, validate_retrieval
from sopilot_eval.extraction import evaluate, score_document, validate_extraction
from sopilot_eval.plan_check import validate_plan

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def save_rows(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def dataset(tmp_path):
    target = tmp_path / "dataset"
    shutil.copytree(ROOT / "datasets/annotation-example", target)
    return target


def test_annotation_draft_passes_structure_but_not_review_gate(dataset):
    # Arrange / Act
    result = validate_retrieval(dataset)
    # Assert
    assert result["questions"] == 5
    with pytest.raises(ValueError, match="human review"):
        validate_retrieval(dataset, require_reviewed=True)


def test_annotation_offset_drift_is_rejected(dataset):
    # Arrange
    spans = read_jsonl(dataset / "evidence.jsonl")
    spans[0]["start_char"] += 1
    save_rows(dataset / "evidence.jsonl", spans)
    # Act / Assert
    with pytest.raises(ValueError, match="quote/offset/hash"):
        validate_retrieval(dataset)


def test_annotation_bilingual_intent_cannot_cross_split(dataset):
    # Arrange
    questions = read_jsonl(dataset / "questions.master.jsonl")
    questions[1]["split"] = "test"
    save_rows(dataset / "questions.master.jsonl", questions)
    # Act / Assert
    with pytest.raises(ValueError, match="leakage"):
        validate_retrieval(dataset)


def test_annotation_or_sets_derive_proxy_without_changing_gold(dataset):
    # Arrange
    questions = read_jsonl(dataset / "questions.master.jsonl")
    spans = {row["span_id"]: row for row in read_jsonl(dataset / "evidence.jsonl")}
    docs = {"leave": {"path": "corpus/leave.md"}}
    question = {**questions[0], "evidence_sets": [["s-days"], ["s-notice"]]}
    # Act
    proxy = project_expected(question, spans, docs)
    # Assert
    assert proxy == [{"doc": "leave.md"}]
    assert question["evidence_sets"] == [["s-days"], ["s-notice"]]


def test_dataset_paths_cannot_escape_root(dataset):
    # Arrange
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest["documents"][0]["path"] = "../outside.md"
    (dataset / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Act / Assert
    with pytest.raises(ValueError, match="inside the dataset"):
        validate_retrieval(dataset)


def test_extraction_example_scores_by_family_and_leaves_measurements_unknown():
    # Arrange
    root = REPO / "datasets/extraction/example"
    # Act
    result = evaluate(root, root / "predictions.example.jsonl")
    # Assert
    assert len(result["by_family_language"]) == 2
    assert result["by_document"]["vi-policy"]["headings"]["recall"] == 1
    assert result["by_document"]["vi-policy"]["elapsed_ms"] is None
    with pytest.raises(ValueError, match="human review"):
        validate_extraction(root, require_reviewed=True)


def test_extraction_heading_order_and_merged_cells_are_scored():
    # Arrange
    gold = {
        "headings": [
            {"text": "A", "level": 1, "page": 1},
            {"text": "B", "level": 2, "page": 1},
        ],
        "tables": [
            {
                "page": 1,
                "rows": 2,
                "cols": 2,
                "column_titles": ["Step", "Owner"],
                "cell_spans": [{"row": 0, "col": 1, "rowspan": 2, "colspan": 1}],
            }
        ],
        "furniture": [{"text": "Confidential"}],
        "metadata": {"code": "QT-01"},
    }
    output = {
        **gold,
        "headings": list(reversed(gold["headings"])),
        "tables": [{**gold["tables"][0], "cell_spans": []}],
        "canonical_markdown": "Confidential\nTheo mục 5.3 và QT-05.",
        "metadata": {},
        "page_count": 2,
        "elapsed_ms": 20,
        "peak_ram_mb": 100,
    }
    # Act
    result = score_document(gold, output)
    # Assert
    assert result["headings"]["recall"] == 0.5
    assert result["merged_cells"]["recall"] == 0
    assert result["furniture_leaked"] == 1
    assert result["elapsed_ms_per_page"] == 10
    assert result["cross_references"] == {"within_document": 1, "between_documents": 1}


def test_v2_plan_all_frontmatter_counters_dag_and_handover_match():
    # Arrange / Act
    result = validate_plan(REPO)
    # Assert
    assert result["tickets"] == 34
    assert result["acyclic"] and result["handover_covers_all_tickets"]
