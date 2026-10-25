import io
import json
import shutil
from pathlib import Path
from typing import ClassVar

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from sopilot_eval.acquire import acquire_one, digest, probe_pdf
from sopilot_eval.extraction import evaluate, validate_extraction
from sopilot_eval.prepare_pilot import save_deterministic, select_sections


class Response(io.BytesIO):
    url = "https://example.org/source"
    headers: ClassVar[dict[str, str]] = {"Content-Type": "application/pdf"}


def test_acquisition_changed_remote_hash_does_not_write_bytes(tmp_path, monkeypatch):
    # Arrange
    source = {"doc_id": "sop", "path": "local/source.pdf", "url": Response.url}
    previous = {**source, "sha256": digest(b"%PDF-original")}
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: Response(b"%PDF-replaced")
    )
    # Act
    result = acquire_one(tmp_path, source, previous, offline=False)
    # Assert
    assert result["status"] == "failed"
    assert "hash changed" in result["error"]
    assert not (tmp_path / source["path"]).exists()


def test_acquisition_offline_detects_corruption_without_overwriting(tmp_path):
    # Arrange
    path = tmp_path / "source.pdf"
    path.write_bytes(b"%PDF-local-corruption")
    source = {"doc_id": "sop", "path": path.name, "url": Response.url}
    previous = {**source, "sha256": digest(b"%PDF-original")}
    # Act
    result = acquire_one(tmp_path, source, previous, offline=True)
    # Assert
    assert result["status"] == "failed"
    assert path.read_bytes() == b"%PDF-local-corruption"


@pytest.mark.parametrize("path", ["../escape.pdf", "../../escape.md"])
def test_acquisition_path_escape_rejected_before_network(tmp_path, monkeypatch, path):
    # Arrange
    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    source = {"doc_id": "sop", "path": path, "url": Response.url}
    # Act
    result = acquire_one(tmp_path, source, {}, offline=False)
    # Assert
    assert result["status"] == "failed"
    assert "inside dataset" in result["error"]


def test_acquisition_html_error_page_cannot_become_pdf(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: Response(b"<html>Access denied</html>"),
    )
    source = {"doc_id": "sop", "path": "source.pdf", "url": Response.url}
    # Act
    result = acquire_one(tmp_path, source, {}, offline=False)
    # Assert
    assert result["status"] == "failed"
    assert not (tmp_path / "source.pdf").exists()


def test_probe_mixed_pdf_preserves_physical_page_numbers_without_ocr(tmp_path):
    # Arrange: a text page followed by a genuinely empty page.
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 10 Td (hello) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "mixed.pdf"
    writer.write(path)
    # Act
    result = probe_pdf(path)
    # Assert
    assert result["classification"] == "mixed"
    assert result["pages_without_text"] == [2]
    assert result["pages"][0]["non_whitespace_characters"] == 5
    assert result["ocr_enabled"] is False


def test_probe_no_text_pdf_does_not_invent_content(tmp_path):
    # Arrange
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    path = tmp_path / "blank.pdf"
    writer.write(path)
    # Act
    result = probe_pdf(path)
    # Assert
    assert result["classification"] == "no_text"
    assert result["pages_without_text"] == [1]


@pytest.mark.parametrize("kind", ["partial", "rejection"])
def test_extraction_incomplete_or_rejected_documents_cannot_inflate_metrics(
    tmp_path, kind
):
    # Arrange
    original = Path(__file__).resolve().parents[2] / "datasets/extraction/example"
    root = tmp_path / "example"
    shutil.copytree(original, root)
    path = root / "annotations.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if kind == "partial":
        rows[0]["annotation_scope"] = "selected_pages"
    else:
        rows[0]["expected_outcome"] = "FAILED"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    # Act / Assert
    validate_extraction(root)
    with pytest.raises(ValueError, match="partial extraction|rejection fixtures"):
        evaluate(root, root / "predictions.example.jsonl")


def test_pilot_rebuild_preserves_human_edits(tmp_path):
    # Arrange
    path = tmp_path / "questions.master.jsonl"
    path.write_bytes(b"human-reviewed-content")
    # Act / Assert
    with pytest.raises(ValueError, match="refusing to overwrite"):
        save_deterministic(path, b"regenerated-draft")
    assert path.read_bytes() == b"human-reviewed-content"


def test_section_selection_keeps_caveat_and_excludes_email_template():
    # Arrange
    raw = "## Criteria\nIdeal criteria. Not always possible.\n<details>Private example email</details>\n## Other\nExcluded\n"
    # Act
    selected = select_sections(raw, ["Criteria"])
    # Assert
    assert "Not always possible" in selected
    assert "example email" not in selected
    assert "Excluded" not in selected
