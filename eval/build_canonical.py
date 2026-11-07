"""Build the V2-06 retrieval corpus from the ai-service ``docproc`` pipeline (owner decision 2026-11-01).

Run with the ai-service environment so the canonical text is exactly what ai-service indexes:

    uv run --project services/ai-service --extra pdf python eval/build_canonical.py \
        --dataset eval/datasets/sop-main --extraction-dataset datasets/extraction/pilot \
        --pilot-dataset eval/datasets/sop-pilot

``<dataset>/selection.json`` lists the documents (``doc_id``, ``source_dataset`` = ``extraction``
or ``pilot``). For each one: ``extract`` -> ``clean_document`` -> ``render``; the rendered Markdown
is written to ``corpus/<doc_id>.md`` (NFC, LF), its page index to ``page-map.json`` (code-point
offsets, ``end_char`` exclusive) and a manifest entry with hashes and versions. Output holds no
document text outside ``corpus/``. Existing corpus files are only overwritten with ``--force``,
because spans and reviews point at their offsets.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

from sopilot_ai.docproc import NORMALIZER_VERSION, clean_document, extract, render

ROOT = Path(__file__).resolve().parents[1]


def say(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_state() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()

    dirty = run("status", "--porcelain", "--", "services/ai-service/src/sopilot_ai/docproc")
    return {"commit": run("rev-parse", "HEAD"), "docproc_dirty": bool(dirty)}


def source_record(sel: dict, extraction: Path, pilot: Path) -> tuple[Path, dict]:
    if sel["source_dataset"] == "extraction":
        manifest = json.loads((extraction / "manifest.json").read_text(encoding="utf-8"))
        sources = json.loads((extraction / "sources.json").read_text(encoding="utf-8"))
        doc = next(d for d in manifest["documents"] if d["doc_id"] == sel["doc_id"])
        src = next(d for d in sources["documents"] if d["doc_id"] == sel["doc_id"])
        return extraction / doc["path"], {
            "lang": doc["lang"],
            "family": doc.get("family"),
            "source": doc["source"],
            "license": doc["license"],
            "redistribution": src.get("redistribution"),
            "source_commit": None,
        }
    if sel["source_dataset"] == "pilot":
        manifest = json.loads((pilot / "manifest.json").read_text(encoding="utf-8"))
        doc = next(d for d in manifest["documents"] if d["doc_id"] == sel["doc_id"])
        return pilot / doc["path"], {
            "lang": doc["lang"],
            "family": "employee_handbook",
            "source": doc["source"],
            "license": doc["license"],
            "redistribution": doc.get("redistribution"),
            "source_commit": doc.get("source_commit"),
        }
    raise ValueError(f"unknown source_dataset: {sel['source_dataset']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--extraction-dataset", type=Path, required=True)
    ap.add_argument("--pilot-dataset", type=Path, required=True)
    ap.add_argument("--force", action="store_true", help="overwrite existing corpus files")
    args = ap.parse_args()
    root: Path = args.dataset
    selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    (root / "corpus").mkdir(parents=True, exist_ok=True)
    page_map, documents = {}, []
    for sel in selection["documents"]:
        path, meta = source_record(sel, args.extraction_dataset, args.pilot_dataset)
        out = root / "corpus" / f"{sel['doc_id']}.md"
        raw = path.read_bytes()
        rendered = render(clean_document(extract(raw, path.name)).document)
        text = unicodedata.normalize("NFC", rendered.markdown.replace("\r\n", "\n"))
        if text != rendered.markdown:
            raise ValueError(f"{sel['doc_id']}: docproc output is not NFC/LF; offsets would drift")
        data = text.encode("utf-8")
        if out.exists() and out.read_bytes() != data and not args.force:
            raise SystemExit(f"{out} differs from a fresh build; rerun with --force only if spans are rebased")
        out.write_bytes(data)
        if rendered.page_index:
            page_map[sel["doc_id"]] = [
                {"page": p.page, "start_char": p.char_start, "end_char": p.char_end} for p in rendered.page_index
            ]
        documents.append(
            {
                "doc_id": sel["doc_id"],
                "path": f"corpus/{sel['doc_id']}.md",
                **meta,
                "sha256": sha256(data),
                "sha256_raw": sha256(raw),
                "chars": len(text),
            }
        )
        say(f"{sel['doc_id']}: {len(text)} chars, {len(rendered.page_index)} page spans")
    manifest = {
        "corpus_version": selection["corpus_version"],
        "normalization_version": f"docproc-render-{NORMALIZER_VERSION}+docling-{importlib.metadata.version('docling')}",
        "docproc": git_state(),
        "purpose": "retrieval-eval-dev-test",
        "frozen": False,
        "production_docproc": True,
        "documents": documents,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "page-map.json").write_text(json.dumps(page_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
